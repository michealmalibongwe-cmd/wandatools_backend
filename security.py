"""
WandaTools — security.py
Password hashing, JWT tokens, password strength scoring, MFA/TOTP, and OTP utilities.

IMPORTANT — source of truth:
  Core JWT functions (create_access_token, create_refresh_token,
  decode_access_token, decode_refresh_token, hash_password, verify_password)
  are defined in main.py and RE-EXPORTED here so route files can import
  from either place without duplication or conflict.

  Everything in this file that is NOT already in main.py is additive:
    - check_password_strength()   — detailed scoring with feedback
    - validate_password_strength()— simple pass/fail for registration
    - MFA/TOTP functions          — authenticator app support
    - generate_otp()              — 6-digit email OTP

New pip dependencies needed:
    pip install pyotp qrcode[pil]
Add to requirements.txt:
    pyotp
    qrcode[pil]
"""

import base64
import random
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional

import pyotp
import qrcode
from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────
# RE-EXPORT from main.py — single source of truth
# Route files can import from security.py OR main.py — both work.
# ─────────────────────────────────────────────────────────────
from main import (
    # Password
    hash_password,
    verify_password,
    pwd_ctx,
    # JWT core
    JWT_SECRET,
    JWT_REFRESH_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_MINUTES,
    REFRESH_TOKEN_DAYS,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)

# Config — reads TOTP_ISSUER, PASSWORD_REQUIRE_NUMBERS, etc.
from config import get_settings

settings = get_settings()


# ─────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    """Decoded JWT token payload — used by route files that need typed access."""
    sub:     Optional[str]      = None
    user_id: Optional[int]      = None
    email:   str
    exp:     datetime
    iat:     Optional[datetime] = None
    type:    str                        # "access" or "refresh"


class PasswordStrength(BaseModel):
    """Result of password strength evaluation."""
    score:     int         # 0 – 5
    feedback:  list[str]  # tips for improvement
    is_strong: bool        # True if score >= 4


# ─────────────────────────────────────────────────────────────
# PASSWORD STRENGTH
# ─────────────────────────────────────────────────────────────

def check_password_strength(password: str) -> PasswordStrength:
    """
    Score a password from 0–5 and return improvement feedback.
    Used on the frontend to show a strength bar in real time.

    Scoring:
      +1  ≥ 8 characters
      +1  ≥ 12 characters
      +1  contains uppercase
      +1  contains lowercase
      +1  contains digit
      +1  contains special character
    Max score is capped at 5.
    """
    score    = 0
    feedback = []

    if len(password) >= 8:
        score += 1
    else:
        feedback.append("Password should be at least 8 characters")

    if len(password) >= 12:
        score += 1
    else:
        feedback.append("Using 12+ characters makes your password much stronger")

    if re.search(r"[A-Z]", password):
        score += 1
    else:
        feedback.append("Add at least one uppercase letter (A–Z)")

    if re.search(r"[a-z]", password):
        score += 1
    else:
        feedback.append("Add at least one lowercase letter (a–z)")

    if re.search(r"\d", password):
        score += 1
    else:
        feedback.append("Add at least one number (0–9)")

    if re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]", password):
        score += 1
    else:
        feedback.append("Add at least one special character (!@#$%^&*)")

    score = min(score, 5)

    return PasswordStrength(
        score=score,
        feedback=feedback,
        is_strong=score >= 4,
    )


def validate_password_strength(password: str) -> dict:
    """
    Simple pass/fail password validation used during registration
    and password change. Reads rules from config settings.

    Returns:
        {"valid": True, "errors": []}          — password is acceptable
        {"valid": False, "errors": [...]}       — password is too weak
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    # These two rules can be toggled in config
    if getattr(settings, "PASSWORD_REQUIRE_NUMBERS", True):
        if not re.search(r"\d", password):
            errors.append("Password must contain at least one number")

    if getattr(settings, "PASSWORD_REQUIRE_SPECIAL", True):
        if not re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]", password):
            errors.append("Password must contain at least one special character (!@#$%^&*)")

    return {"valid": len(errors) == 0, "errors": errors}


# ─────────────────────────────────────────────────────────────
# JWT HELPERS — typed wrappers around main.py functions
# ─────────────────────────────────────────────────────────────

def verify_token(token: str) -> Optional[TokenData]:
    """
    Decode a JWT (access or refresh) and return a typed TokenData object.
    Returns None if the token is invalid — does NOT raise an exception.
    Use this when you want to inspect a token without hard-failing.
    For protected endpoints use decode_access_token() from main.py instead.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        # Try the refresh secret as a fallback
        try:
            payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
        except JWTError:
            return None

    try:
        return TokenData(
            sub=payload.get("sub"),
            user_id=int(payload["sub"]) if payload.get("sub") else None,
            email=payload.get("email", ""),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc) if payload.get("iat") else None,
            type=payload.get("type", "access"),
        )
    except Exception:
        return None


def verify_token_type(payload: dict, expected_type: str = "access") -> bool:
    """Check that a decoded payload's 'type' field matches expected_type."""
    return payload.get("type") == expected_type


def get_user_id_from_token(payload: dict) -> Optional[int]:
    """Safely extract the integer user_id from a decoded token payload."""
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        return None


def is_token_expired(payload: dict) -> bool:
    """
    Return True if the token's 'exp' claim is in the past.
    Safe to call on any decoded payload dict.
    """
    try:
        exp = payload.get("exp")
        if exp is None:
            return True
        return datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(tz=timezone.utc)
    except Exception:
        return True


def decode_token(token: str) -> Optional[dict]:
    """
    Decode any JWT (tries access secret, then refresh secret).
    Returns the raw payload dict or None — does NOT raise.
    Used by auth.py's get_current_user dependency.
    """
    for secret in (JWT_SECRET, JWT_REFRESH_SECRET):
        try:
            return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        except JWTError:
            continue
    return None


# ─────────────────────────────────────────────────────────────
# MFA / TOTP — Authenticator App Support
# Requires: pip install pyotp qrcode[pil]
# ─────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    """
    Generate a random TOTP secret key.
    Store this on the User model (e.g. user.totp_secret) when MFA is enabled.
    Never expose this secret in API responses after setup.
    """
    return pyotp.random_base32()


def generate_totp_qr(email: str, secret: str) -> str:
    """
    Generate a QR code for TOTP authenticator app setup.
    Returns a base64-encoded PNG image string (data:image/png;base64,...).
    Show this on the MFA setup page — user scans it with Google Authenticator etc.

    Args:
        email:  The user's email (shown as account name in the authenticator app)
        secret: The user's TOTP secret from generate_totp_secret()
    """
    issuer = getattr(settings, "TOTP_ISSUER", "WandaTools")
    totp   = pyotp.TOTP(secret)
    uri    = totp.provisioning_uri(name=email, issuer_name=issuer)

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)

    img    = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def verify_totp(secret: str, token: str) -> bool:
    """
    Verify a 6-digit TOTP token from the user's authenticator app.
    Allows a ±1 window (30 seconds either side) to account for clock drift.

    Args:
        secret: The stored TOTP secret for this user
        token:  The 6-digit code the user entered
    """
    return pyotp.TOTP(secret).verify(token, valid_window=1)


# ─────────────────────────────────────────────────────────────
# EMAIL OTP — 6-digit one-time password for email verification
# ─────────────────────────────────────────────────────────────

def generate_otp() -> str:
    """
    Generate a cryptographically random 6-digit OTP for email verification
    or SMS-based MFA. Uses secrets.randbelow for better randomness than random.

    Returns:
        A zero-padded 6-digit string e.g. "048271"
    """
    import secrets as _secrets
    return str(_secrets.randbelow(900000) + 100000)   # always 6 digits, never < 100000


def generate_otp_expiry(minutes: int = 10) -> datetime:
    """Return a UTC datetime N minutes from now — store alongside the OTP."""
    return datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)


def is_otp_expired(expiry: datetime) -> bool:
    """Check whether a stored OTP expiry datetime has passed."""
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc) > expiry