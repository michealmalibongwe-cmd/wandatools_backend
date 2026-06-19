"""
Security Module
Handles password hashing, JWT token generation, and authentication
"""

from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
from config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ═══ Password Functions ═══
def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hash
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> dict:
    """
    Validate password strength
    
    Args:
        password: Password to validate
        
    Returns:
        dict with 'valid' (bool) and 'errors' (list of error messages)
    """
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if settings.PASSWORD_REQUIRE_NUMBERS and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")
    
    if settings.PASSWORD_REQUIRE_SPECIAL and not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in password):
        errors.append("Password must contain at least one special character")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


# ═══ JWT Token Functions ═══
class TokenData(BaseModel):
    """JWT token payload"""
    sub: str  # Subject (user ID)
    email: str
    exp: datetime
    iat: datetime
    type: str = "access"  # access or refresh


def create_access_token(user_id: int, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        user_id: User ID to encode
        email: User email
        expires_delta: Token expiration time
        
    Returns:
        Encoded JWT token
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    to_encode = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int, email: str) -> str:
    """
    Create a JWT refresh token
    
    Args:
        user_id: User ID to encode
        email: User email
        
    Returns:
        Encoded JWT refresh token
    """
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token
    
    Args:
        token: JWT token to decode
        
    Returns:
        Token payload as dict, or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_token_type(payload: dict, expected_type: str = "access") -> bool:
    """
    Verify token type matches expected type
    
    Args:
        payload: Decoded token payload
        expected_type: Expected token type (access or refresh)
        
    Returns:
        True if type matches, False otherwise
    """
    return payload.get("type") == expected_type


# ═══ Helper Functions ═══
def get_user_id_from_token(payload: dict) -> Optional[int]:
    """
    Extract user ID from token payload
    
    Args:
        payload: Decoded token payload
        
    Returns:
        User ID or None if not found
    """
    try:
        return int(payload.get("sub"))
    except (ValueError, TypeError):
        return None


def is_token_expired(payload: dict) -> bool:
    """
    Check if token is expired
    
    Args:
        payload: Decoded token payload
        
    Returns:
        True if expired, False otherwise
    """
    try:
        exp = payload.get("exp")
        if exp is None:
            return True
        return datetime.utcfromtimestamp(exp) < datetime.utcnow()
    except:
        return True
