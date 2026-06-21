"""
WandaTools Security Module
Handles password hashing, password strength, JWT token generation/verification, MFA/TOTP, and authentication utilities
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
import pyotp
import qrcode
from io import BytesIO
import base64
import random
from config import get_settings

settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ═══ Models ═══
class TokenData(BaseModel):
    """JWT token payload"""
    sub: Optional[str] = None  # Subject (user ID)
    user_id: Optional[int] = None
    email: str
    exp: datetime
    iat: Optional[datetime] = None
    type: str  # access or refresh


class PasswordStrength(BaseModel):
    score: int  # 0-5
    feedback: list[str]
    is_strong: bool


# ═══ Password Functions ═══
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def check_password_strength(password: str) -> PasswordStrength:
    """Evaluate password strength with scoring"""
    score = 0
    feedback = []

    if len(password) >= 12:
        score += 1
    else:
        feedback.append("Password should be at least 12 characters")

    if len(password) >= 16:
        score += 1

    if any(c.isupper() for c in password):
        score += 1
    else:
        feedback.append("Add uppercase letters")

    if any(c.islower() for c in password):
        score += 1
    else:
        feedback.append("Add lowercase letters")

    if any(c.isdigit() for c in password):
        score += 1
    else:
        feedback.append("Add numbers")

    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        score += 1
    else:
        feedback.append("Add special characters (!@#$%^&*)")

    score = min(score, 5)

    return PasswordStrength(score=score, feedback=feedback, is_strong=score >= 4)


def validate_password_strength(password: str) -> dict:
    """Validate password strength with simple rules"""
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if settings.PASSWORD_REQUIRE_NUMBERS and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")

    if settings.PASSWORD_REQUIRE_SPECIAL and not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in password):
        errors.append("Password must contain at least one special character")

    return {"valid": len(errors) == 0, "errors": errors}


# ═══ JWT Token Functions ═══
def create_access_token(user_id: int, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "sub": str(user_id),
        "user_id": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int, email: str) -> str:
    """Create JWT refresh token"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": str(user_id),
        "user_id": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token"""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def verify_token(token: str) -> Optional[TokenData]:
    """Verify and decode JWT token into TokenData"""
    payload = decode_token(token)
    if not payload:
        return None

    try:
        return TokenData(
            sub=payload.get("sub"),
            user_id=int(payload.get("sub")) if payload.get("sub") else None,
            email=payload.get("email"),
            exp=datetime.fromtimestamp(payload.get("exp")),
            iat=datetime.fromtimestamp(payload.get("iat")) if payload.get("iat") else None,
            type=payload.get("type")
        )
    except Exception:
        return None


def verify_token_type(payload: dict, expected_type: str = "access") -> bool:
    """Verify token type matches expected type"""
    return payload.get("type") == expected_type


def get_user_id_from_token(payload: dict) -> Optional[int]:
    """Extract user ID from token payload"""
    try:
        return int(payload.get("sub"))
    except (ValueError, TypeError):
        return None


def is_token_expired(payload: dict) -> bool:
    """Check if token is expired"""
    try:
        exp = payload.get("exp")
        if exp is None:
            return True
        return datetime.utcfromtimestamp(exp) < datetime.utcnow()
    except:
        return True


# ═══ MFA / OTP Functions ═══
def generate_totp_secret() -> str:
    """Generate TOTP secret for authenticator app"""
    return pyotp.random_base32()


def generate_totp_qr(email: str, secret: str) -> str:
    """Generate QR code for TOTP setup"""
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=email, issuer_name=settings.TOTP_ISSUER)

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


def verify_totp(secret: str, token: str) -> bool:
    """Verify TOTP token from authenticator"""
    return pyotp.TOTP(secret).verify(token)


def generate_otp() -> str:
    """Generate 6-digit OTP for email"""
    return str(random.randint(100000, 999999))
