"""
Authentication routes with security best practices
"""

from fastapi import APIRouter, HTTPException, Request, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr, field_validator
import os

from config import get_settings
from security import (
    hash_password, verify_password, check_password_strength,
    create_access_token, create_refresh_token, verify_token,
    generate_totp_secret, generate_totp_qr, verify_totp,
    generate_otp, PasswordStrength
)
from models import User, LoginLog, LoginStatus, UserRole
from db import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()

# ═══════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════

class PasswordCheckRequest(BaseModel):
    password: str

class PasswordCheckResponse(BaseModel):
    score: int
    feedback: list[str]
    is_strong: bool
    message: str

class IndividualSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    password_confirm: str
    
    @field_validator("name")
    def validate_name(cls, v):
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v
    
    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        return v

class BusinessSignupRequest(BaseModel):
    # Personal
    name: str
    email: EmailStr
    password: str
    password_confirm: str
    phone: str
    
    # Business
    business_name: str
    business_type: str
    business_email: EmailStr
    business_registration: str  # Will be encrypted
    country: str
    
    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class MFASetupRequest(BaseModel):
    mfa_type: str  # totp or email
    token: str = None  # For verification

class MFAVerifyRequest(BaseModel):
    token: str  # 6-digit OTP or TOTP token

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

# ═══════════════════════════════════════════════════════════
# RATE LIMITING
# ═══════════════════════════════════════════════════════════

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

def check_login_attempts(db: Session, email: str, ip: str):
    """Check if user is locked out"""
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        return True  # User doesn't exist, allow attempt
    
    # Check if locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = (user.locked_until - datetime.utcnow()).total_seconds() / 60
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked. Try again in {int(remaining)} minutes."
        )
    
    # Check recent failed attempts
    recent_logs = db.query(LoginLog).filter(
        LoginLog.email == email,
        LoginLog.created_at > datetime.utcnow() - timedelta(minutes=5),
        LoginLog.status == LoginStatus.FAILED
    ).count()
    
    if recent_logs >= settings.RATE_LIMIT_LOGIN_ATTEMPTS:
        # Lock account
        lock_until = datetime.utcnow() + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
        user.locked_until = lock_until
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Account locked for {settings.ACCOUNT_LOCKOUT_MINUTES} minutes."
        )
    
    return True

# ═══════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════

@router.post("/check-password")
async def check_password(request: PasswordCheckRequest) -> PasswordCheckResponse:
    """Check password strength"""
    strength = check_password_strength(request.password)
    
    return PasswordCheckResponse(
        score=strength.score,
        feedback=strength.feedback,
        is_strong=strength.is_strong,
        message="✅ Strong password" if strength.is_strong else "⚠️ Weak password"
    )

@router.post("/signup/individual")
async def signup_individual(
    req: IndividualSignupRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Sign up as individual"""
    
    # Validate passwords match
    if req.password != req.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    # Check password strength
    strength = check_password_strength(req.password)
    if not strength.is_strong:
        raise HTTPException(
            status_code=400,
            detail=f"Password is too weak. {', '.join(strength.feedback)}"
        )
    
    # Check if email exists
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # Create user
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
        role=UserRole.INDIVIDUAL,
        last_ip=request.client.host
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    
    # Log successful registration
    log = LoginLog(
        user_id=user.id,
        email=user.email,
        ip_address=request.client.host,
        status=LoginStatus.SUCCESS,
        reason="Account created"
    )
    db.add(log)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_dict(),
        "message": "✅ Account created successfully!"
    }

@router.post("/signup/business")
async def signup_business(
    req: BusinessSignupRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Sign up as business"""
    
    # Validate passwords match
    if req.password != req.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    # Check password strength
    strength = check_password_strength(req.password)
    if not strength.is_strong:
        raise HTTPException(status_code=400, detail="Password is too weak")
    
    # Check if emails exist
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    
    if db.query(User).filter(User.business_email == req.business_email).first():
        raise HTTPException(status_code=409, detail="Business email already registered")
    
    # Create user
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
        role=UserRole.BUSINESS,
        business_name=req.business_name,
        business_type=req.business_type,
        business_email=req.business_email,
        business_registration=req.business_registration,  # TODO: Encrypt
        phone=req.phone,
        country=req.country,
        last_ip=request.client.host
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    
    # Log
    log = LoginLog(
        user_id=user.id,
        email=user.email,
        ip_address=request.client.host,
        status=LoginStatus.SUCCESS,
        reason="Business account created"
    )
    db.add(log)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_dict(),
        "message": "✅ Business account created!"
    }

@router.post("/login")
@limiter.limit("10/minute")
async def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Login user"""
    
    # Get client IP
    ip = request.client.host
    
    # Check if user is locked
    check_login_attempts(db, req.email, ip)
    
    # Find user
    user = db.query(User).filter(User.email == req.email).first()
    
    if not user or not verify_password(req.password, user.password_hash):
        # Log failed attempt
        log = LoginLog(
            email=req.email,
            ip_address=ip,
            status=LoginStatus.FAILED,
            reason="Invalid credentials",
            user_id=user.id if user else None
        )
        db.add(log)
        
        # Increment failed attempts
        if user:
            user.failed_login_attempts += 1
            db.merge(user)
        
        db.commit()
        
        # Generic error (don't reveal if email exists)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    
    # Check if MFA is enabled
    if user.mfa_enabled:
        # Generate OTP
        otp = generate_otp()
        # TODO: Send OTP via email
        # send_email(user.email, f"Your WandaTools OTP: {otp}")
        
        return {
            "mfa_required": True,
            "mfa_type": user.mfa_type,
            "message": "✅ MFA verification required",
            "note": "Check your email for OTP"
        }
    
    # Reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    user.last_ip = ip
    
    # Create tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    
    # Log successful login
    log = LoginLog(
        user_id=user.id,
        email=user.email,
        ip_address=ip,
        status=LoginStatus.SUCCESS
    )
    db.add(log)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_dict(),
        "message": "✅ Login successful!"
    }

@router.post("/mfa/setup")
async def setup_mfa(
    req: MFASetupRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Setup MFA for user"""
    
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if req.mfa_type == "totp":
        # Generate secret
        secret = generate_totp_secret()
        
        # Generate QR code
        qr_code = generate_totp_qr(user.email, secret)
        
        return {
            "mfa_type": "totp",
            "secret": secret,
            "qr_code": qr_code,
            "message": "✅ Scan QR code with authenticator app"
        }
    
    elif req.mfa_type == "email":
        # Send OTP to email
        otp = generate_otp()
        # TODO: send_email(user.email, f"Your MFA code: {otp}")
        
        return {
            "mfa_type": "email",
            "message": "✅ Verification code sent to your email"
        }

@router.post("/mfa/verify")
async def verify_mfa(
    req: MFAVerifyRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Verify MFA setup"""
    
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.mfa_type == "totp":
        if not verify_totp(user.totp_secret, req.token):
            raise HTTPException(status_code=401, detail="Invalid token")
    
    # TODO: Verify email OTP
    
    user.mfa_enabled = True
    db.commit()
    
    return {"message": "✅ MFA enabled successfully"}

@router.get("/me")
async def get_current_user_info(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user info"""
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()

@router.post("/refresh")
async def refresh_access_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """Refresh access token"""
    
    token_data = verify_token(refresh_token)
    if not token_data or token_data.token_type != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Check if token is blacklisted
    # TODO: Check refresh_token_blacklist
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    new_access_token = create_access_token(user.id, user.email)
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/logout")
async def logout(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout user - blacklist refresh token"""
    # TODO: Add to blacklist
    return {"message": "✅ Logged out successfully"}

# ═══════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════

def get_current_user(authorization: str = None):
    """Dependency to get current user from JWT"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization[7:]
    token_data = verify_token(token)
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token_data

# ═══════════════════════════════════════════════════════════
# ADDITIONAL IMPORTS
# ═══════════════════════════════════════════════════════════

from services.email import EmailService
from models import EmailVerificationToken, PasswordResetToken, MFAOtp
import secrets
from sqlalchemy import and_

# ═══════════════════════════════════════════════════════════
# EMAIL VERIFICATION
# ═══════════════════════════════════════════════════════════

def generate_verification_token() -> str:
    """Generate secure token"""
    return secrets.token_urlsafe(32)

@router.post("/send-verification-email")
async def send_verification_email(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send verification email"""
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_verified:
        raise HTTPException(status_code=400, detail="User already verified")
    
    # Generate token
    token = generate_verification_token()
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Save token
    verification = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(verification)
    db.commit()
    
    # Send email
    email_sent = EmailService.send_verification_email(
        user.email,
        token,
        user.name
    )
    
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send email")
    
    return {
        "message": "✅ Verification email sent",
        "expires_in_hours": 24
    }

@router.post("/verify-email")
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """Verify email with token"""
    
    # Find token
    verification = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token == token
    ).first()
    
    if not verification:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    
    # Check expiry
    if verification.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification token expired")
    
    # Check if already used
    if verification.used_at:
        raise HTTPException(status_code=400, detail="Token already used")
    
    # Mark as verified
    user = verification.user
    user.is_verified = True
    user.email_verified_at = datetime.utcnow()
    
    verification.used_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "✅ Email verified successfully",
        "user": user.to_dict()
    }

# ═══════════════════════════════════════════════════════════
# FORGOT PASSWORD
# ═══════════════════════════════════════════════════════════

@router.post("/forgot-password")
async def forgot_password(
    email: EmailStr,
    db: Session = Depends(get_db)
):
    """Request password reset"""
    
    # Find user (don't reveal if exists)
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Return generic response to prevent email enumeration
        return {
            "message": "✅ If email exists, password reset link sent"
        }
    
    # Generate reset token
    token = generate_verification_token()
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    # Invalidate previous tokens
    db.query(PasswordResetToken).filter(
        and_(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at == None
        )
    ).update({"used_at": datetime.utcnow()})
    
    # Save new token
    reset = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(reset)
    db.commit()
    
    # Send email
    EmailService.send_password_reset_email(
        user.email,
        token,
        user.name
    )
    
    # Generic response
    return {
        "message": "✅ If email exists, password reset link sent"
    }

@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    """Reset password with token"""
    
    # Validate password strength
    strength = check_password_strength(new_password)
    if not strength.is_strong:
        raise HTTPException(
            status_code=400,
            detail="Password is too weak"
        )
    
    # Find token
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()
    
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    
    # Check expiry
    if reset.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token expired")
    
    # Check if already used
    if reset.used_at:
        raise HTTPException(status_code=400, detail="Token already used")
    
    # Update password
    user = reset.user
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    
    reset.used_at = datetime.utcnow()
    
    db.commit()
    
    # Log password change
    log = LoginLog(
        user_id=user.id,
        email=user.email,
        ip_address="system",
        status=LoginStatus.SUCCESS,
        reason="Password reset"
    )
    db.add(log)
    db.commit()
    
    return {
        "message": "✅ Password reset successfully"
    }

# ═══════════════════════════════════════════════════════════
# MFA WITH EMAIL OTP
# ═══════════════════════════════════════════════════════════

@router.post("/mfa/send-otp")
async def send_mfa_otp(
    email: EmailStr,
    db: Session = Depends(get_db)
):
    """Send MFA OTP to email"""
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.mfa_type != "email":
        raise HTTPException(status_code=400, detail="User not set up for email MFA")
    
    # Generate OTP
    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Save OTP
    mfa_otp = MFAOtp(
        user_id=user.id,
        otp=otp,
        expires_at=expires_at
    )
    db.add(mfa_otp)
    db.commit()
    
    # Send email
    EmailService.send_mfa_otp(user.email, otp, user.name)
    
    return {
        "message": "✅ OTP sent to email",
        "expires_in_minutes": 10
    }

@router.post("/mfa/verify-otp")
async def verify_mfa_otp(
    email: EmailStr,
    otp: str,
    db: Session = Depends(get_db)
):
    """Verify MFA OTP"""
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Find recent OTP
    mfa_otp = db.query(MFAOtp).filter(
        and_(
            MFAOtp.user_id == user.id,
            MFAOtp.verified_at == None,
            MFAOtp.expires_at > datetime.utcnow()
        )
    ).order_by(MFAOtp.created_at.desc()).first()
    
    if not mfa_otp:
        raise HTTPException(status_code=400, detail="No valid OTP found")
    
    # Check attempts
    if mfa_otp.attempts >= 3:
        raise HTTPException(status_code=429, detail="Too many failed attempts")
    
    # Verify OTP
    if mfa_otp.otp != otp:
        mfa_otp.attempts += 1
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid OTP")
    
    # Mark as verified
    mfa_otp.verified_at = datetime.utcnow()
    
    # Reset failed login attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    
    db.commit()
    
    # Create tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "message": "✅ MFA verified successfully"
    }