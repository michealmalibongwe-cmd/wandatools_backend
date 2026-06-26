"""
WandaTools — security.py
Location: ROOT folder (same level as main.py)

Password hashing, JWT tokens, password strength scoring, MFA/TOTP, and OTP utilities.

Source of truth:
  Core functions (hash_password, verify_password, create_access_token,
  create_refresh_token, decode_access_token, decode_refresh_token)
  are defined in main.py and RE-EXPORTED here.
  Route files can import from security.py OR main.py — both work.

Additive features (not in main.py):
  - check_password_strength()    — detailed score + feedback (0-5)
  - validate_password_strength() — simple pass/fail for registration
  - MFA/TOTP functions           — authenticator app support
  - generate_otp()               — 6-digit email OTP
  - generate_otp_expiry()        — expiry datetime for OTPs
  - is_otp_expired()             — check if OTP has passed

New dependencies required:
  pip install pyotp qrcode[pil]
  Add to requirements.txt: pyotp  and  qrcode[pil]
"""

import base64
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
# ─────────────────────────────────────────────────────────────

from main import (
    hash_password,
    verify_password,
    pwd_ctx,
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

from config import get_settings

settings = get_settings()


# ─────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    """Decoded JWT token payload — typed access for route files."""
    sub:     Optional[str]      = None
    user_id: Optional[int]      = None
    email:   str
    exp:     datetime
    iat:     Optional[datetime] = None
    type:    str                        # "access" or "refresh"


class PasswordStrength(BaseModel):
    """Result of password strength evaluation."""
    score:     int         # 0 – 5
    feedback:  list[str]  # improvement tips
    is_strong: bool        # True if score >= 4


# ─────────────────────────────────────────────────────────────
# PASSWORD STRENGTH
# ─────────────────────────────────────────────────────────────

def check_password_strength(password: str) -> PasswordStrength:
    """
    Score a password 0–5 and return improvement feedback.
    Used on the frontend to show a real-time strength bar.

    Scoring:
      +1  >= 8 characters
      +1  >= 12 characters
      +1  contains uppercase
      +1  contains lowercase
      +1  contains digit
      +1  contains special character
    Capped at 5.
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
    return PasswordStrength(score=score, feedback=feedback, is_strong=score >= 4)


def validate_password_strength(password: str) -> dict:
    """
    Simple pass/fail password validation.
    Rules toggled by config settings (PASSWORD_REQUIRE_NUMBERS, PASSWORD_REQUIRE_SPECIAL).
    Returns: {"valid": True/False, "errors": [...]}
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

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
    Decode any JWT and return typed TokenData or None.
    Does NOT raise — use this when you want to inspect without hard-failing.
    For protected endpoints use decode_access_token() from main.py instead.
    """
    for secret in (JWT_SECRET, JWT_REFRESH_SECRET):
        try:
            payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
            return TokenData(
                sub=payload.get("sub"),
                user_id=int(payload["sub"]) if payload.get("sub") else None,
                email=payload.get("email", ""),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc) if payload.get("iat") else None,
                type=payload.get("type", "access"),
            )
        except (JWTError, Exception):
            continue
    return None


def verify_token_type(payload: dict, expected_type: str = "access") -> bool:
    """Check a decoded payload's 'type' matches expected_type."""
    return payload.get("type") == expected_type


def get_user_id_from_token(payload: dict) -> Optional[int]:
    """Safely extract integer user_id from a decoded token payload."""
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        return None


def is_token_expired(payload: dict) -> bool:
    """Return True if the token's 'exp' claim is in the past."""
    try:
        exp = payload.get("exp")
        if exp is None:
            return True
        return datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(tz=timezone.utc)
    except Exception:
        return True


def decode_token(token: str) -> Optional[dict]:
    """
    Decode any JWT — tries access secret then refresh secret.
    Returns raw payload dict or None. Does NOT raise.
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
    Store on the User model (e.g. user.totp_secret) when MFA is enabled.
    """
    return pyotp.random_base32()


def generate_totp_qr(email: str, secret: str) -> str:
    """
    Generate a QR code for TOTP authenticator app setup.
    Returns a base64-encoded PNG (data:image/png;base64,...).
    Show on the MFA setup page — user scans with Google Authenticator etc.
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
    Verify a 6-digit TOTP from the user's authenticator app.
    Allows ±1 window (30 seconds either side) for clock drift.
    """
    return pyotp.TOTP(secret).verify(token, valid_window=1)


# ─────────────────────────────────────────────────────────────
# EMAIL OTP — 6-digit one-time password
# ─────────────────────────────────────────────────────────────

def generate_otp() -> str:
    """
    Generate a cryptographically random 6-digit OTP.
    Always 6 digits, never less than 100000.
    """
    import secrets as _secrets
    return str(_secrets.randbelow(900000) + 100000)


def generate_otp_expiry(minutes: int = 10) -> datetime:
    """Return a UTC datetime N minutes from now — store alongside the OTP."""
    return datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)


def is_otp_expired(expiry: datetime) -> bool:
    """Check whether a stored OTP expiry datetime has passed."""
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc) > expiry