"""
WandaTools — routes/auth.py
Location: routes/ folder

Authentication routes: register, login, refresh, logout, profile management.

Imports:
  - DB session     → db.py
  - Models         → main.py  (User, RefreshToken)
  - Security       → main.py  (hash_password, verify_password, JWT functions)
  - Email          → services/email.py  (EmailService)
  - Notifications  → notifications.py  (NotificationService)

Endpoints:
  POST   /api/v1/auth/register         — create account
  POST   /api/v1/auth/login            — sign in, get token pair
  POST   /api/v1/auth/refresh          — swap refresh token for new pair
  POST   /api/v1/auth/logout           — revoke refresh token server-side
  GET    /api/v1/auth/me               — get own profile
  PUT    /api/v1/auth/profile          — update name / timezone / currency
  POST   /api/v1/auth/change-password  — change password (needs current password)
  DELETE /api/v1/auth/account          — permanently delete account + all data
"""

import logging
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from db import get_db
from main import (
    User,
    RefreshToken,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    REFRESH_TOKEN_DAYS,
    ACCESS_TOKEN_MINUTES,
    SUPPORTED_CURRENCIES,
    DEFAULT_CURRENCY,
)
from notifications import NotificationService
from services.email import EmailService

log    = logging.getLogger("wandatools.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ─────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name:          str
    email:         EmailStr
    password:      str
    business_type: str | None = None
    timezone:      str        = "Africa/Johannesburg"
    currency:      str        = DEFAULT_CURRENCY

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("currency")
    @classmethod
    def currency_supported(cls, v: str) -> str:
        v = v.upper()
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency must be one of: {', '.join(SUPPORTED_CURRENCIES)}")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ProfileUpdateRequest(BaseModel):
    name:          str | None = None
    timezone:      str | None = None
    currency:      str | None = None
    business_type: str | None = None

    @field_validator("currency")
    @classmethod
    def currency_supported(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency must be one of: {', '.join(SUPPORTED_CURRENCIES)}")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str


# ─────────────────────────────────────────────────────────────
# PASSWORD VALIDATION
# ─────────────────────────────────────────────────────────────

def validate_password(password: str) -> None:
    """
    Enforce strong password rules.
    Raises HTTPException 422 if any rule fails.
    Rules: 8+ chars, uppercase, lowercase, digit, special character.
    """
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one number")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-]", password):
        errors.append("Password must contain at least one special character (!@#$%^&* etc.)")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Password does not meet security requirements", "errors": errors},
        )


# ─────────────────────────────────────────────────────────────
# SHARED DEPENDENCY — get logged-in user from Authorization header
# ─────────────────────────────────────────────────────────────

def get_current_user(
    authorization: str     = Header(default=None),
    db:            Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — validates the JWT access token and returns the User row.
    Import this into any route file that needs the authenticated user:
        from routes.auth import get_current_user
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing. Format: 'Bearer <access_token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token   = authorization[7:]
    payload = decode_access_token(token)
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists — please register again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _build_token_response(user: User, db: Session) -> dict:
    """Create access + refresh token pair, persist refresh token, return response dict."""
    access_token  = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)

    db.add(RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
    ))
    db.commit()

    return {
        "access_token":       access_token,
        "refresh_token":      refresh_token,
        "token_type":         "bearer",
        "access_expires_in":  ACCESS_TOKEN_MINUTES * 60,
        "refresh_expires_in": REFRESH_TOKEN_DAYS * 86400,
        "user": {
            "id":            user.id,
            "name":          user.name,
            "email":         user.email,
            "currency":      user.currency,
            "business_type": user.business_type,
            "timezone":      user.timezone,
        },
    }


# ─────────────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new WandaTools account.
    Password is bcrypt-hashed. Returns a JWT access + refresh token pair.
    """
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{body.email}' already exists",
        )

    validate_password(body.password)

    try:
        user = User(
            name=body.name,
            email=body.email,
            password=hash_password(body.password),
            business_type=body.business_type,
            timezone=body.timezone,
            currency=body.currency.upper(),
        )
        db.add(user)
        db.flush()

        # _build_token_response adds the refresh token and calls db.commit() internally,
        # which also commits the flushed user row. No second commit needed here.
        response = _build_token_response(user, db)

        # Send welcome email — wrapped so email failure never blocks registration
        try:
            EmailService.send_welcome_email(user.email, user.name, user.currency)
        except Exception as email_exc:
            log.warning(f"⚠️  Welcome email failed for {user.email}: {email_exc}")

        log.info(f"✅ New user registered: {user.id} ({user.email})")
        return {**response, "message": "✅ Account created successfully!"}

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"register error for {body.email}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed — please try again: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Sign in with email + password.
    Returns a new JWT access token (30 min) + refresh token (7 days).
    Same error for wrong email or wrong password — prevents user enumeration.
    """
    user = db.query(User).filter(User.email == body.email).first()

    if not user or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = _build_token_response(user, db)
        log.info(f"✅ Login: user {user.id} ({user.email})")
        return {**response, "message": "✅ Login successful!"}

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"login error for {body.email}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed — server error: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# REFRESH TOKEN
# ─────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    The old refresh token is revoked immediately (token rotation).
    """
    payload = decode_refresh_token(body.refresh_token)
    user_id = int(payload["sub"])

    stored = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token   == body.refresh_token,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,          # noqa: E712
        )
        .first()
    )

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or does not exist — please log in again",
        )

    if stored.expires_at < datetime.utcnow():
        stored.revoked = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired — please log in again",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account no longer exists",
        )

    try:
        stored.revoked = True
        response = _build_token_response(user, db)
        log.info(f"🔄 Token rotated for user {user.id}")
        return response

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"refresh error for user {user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    body:         RefreshRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Logout by revoking the refresh token in the database.
    The access token expires naturally (max 30 min).
    """
    stored = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token   == body.refresh_token,
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False,          # noqa: E712
        )
        .first()
    )

    if stored:
        stored.revoked = True
        db.commit()
        log.info(f"🚪 User {current_user.id} logged out — refresh token revoked")

    return {"message": "✅ Logged out successfully. Session has been revoked."}


# ─────────────────────────────────────────────────────────────
# GET OWN PROFILE
# ─────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's full profile."""
    return {
        "id":            current_user.id,
        "name":          current_user.name,
        "email":         current_user.email,
        "account_type":  current_user.business_type or "Individual",
        "business_type": current_user.business_type,
        "timezone":      current_user.timezone,
        "currency":      current_user.currency,
        "created_at":    current_user.created_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# UPDATE PROFILE
# ─────────────────────────────────────────────────────────────

@router.put("/profile")
async def update_profile(
    body:         ProfileUpdateRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Update name, timezone, currency, or business type. Only include fields to change."""
    changed = False

    if body.name is not None:
        name = body.name.strip()
        if len(name) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name must be at least 2 characters",
            )
        current_user.name = name
        changed = True

    if body.timezone is not None:
        current_user.timezone = body.timezone
        changed = True

    if body.currency is not None:
        current_user.currency = body.currency.upper()
        changed = True

    if body.business_type is not None:
        current_user.business_type = body.business_type
        changed = True

    if not changed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided to update",
        )

    try:
        db.commit()
        db.refresh(current_user)
        log.info(f"✏️  Profile updated for user {current_user.id}")
        return {
            "id":            current_user.id,
            "name":          current_user.name,
            "email":         current_user.email,
            "business_type": current_user.business_type,
            "timezone":      current_user.timezone,
            "currency":      current_user.currency,
            "created_at":    current_user.created_at.isoformat(),
            "message":       "✅ Profile updated!",
        }
    except Exception as exc:
        db.rollback()
        log.error(f"profile update error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update profile: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# CHANGE PASSWORD
# ─────────────────────────────────────────────────────────────

@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    body:         ChangePasswordRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Change the logged-in user's password.
    Requires the current password. Revokes all refresh tokens on all devices.
    """
    if not verify_password(body.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be different from your current password",
        )

    validate_password(body.new_password)

    try:
        current_user.password = hash_password(body.new_password)

        # Revoke ALL refresh tokens — forces re-login on all devices
        db.query(RefreshToken).filter(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False,          # noqa: E712
        ).update({"revoked": True})

        db.commit()

        # Notify user their password was changed
        NotificationService.notify_password_changed(db=db, user_id=current_user.id)

        log.info(f"🔑 Password changed for user {current_user.id} — all sessions revoked")
        return {
            "message": (
                "✅ Password changed successfully. "
                "You have been logged out of all other devices."
            )
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"change-password error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not change password: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# DELETE ACCOUNT
# ─────────────────────────────────────────────────────────────

@router.delete("/account", status_code=status.HTTP_200_OK)
async def delete_account(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Permanently delete the authenticated user's account and all associated data.
    Includes all transactions, refresh tokens, and notifications (cascade delete).
    This action cannot be undone.
    """
    user_id    = current_user.id
    user_email = current_user.email

    try:
        db.delete(current_user)
        db.commit()
        log.warning(f"🗑️  Account deleted: user {user_id} ({user_email})")
        return {"message": "✅ Your account and all associated data have been permanently deleted."}

    except Exception as exc:
        db.rollback()
        log.error(f"delete-account error for user {user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete account: {exc}",
        )