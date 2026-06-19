"""
Authentication Routes
Handles user registration, login, and token management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from db import get_db
from models import User, UserPreference
from schemas import UserCreate, UserLogin, UserResponse, TokenData, TokenRefresh, UserUpdate, UserDetailResponse
from security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
    get_user_id_from_token,
    is_token_expired
)

router = APIRouter(prefix="/auth", tags=["authentication"])


# ═══ Dependency Functions ═══
def get_current_user(token: str, db: Session = Depends(get_db)) -> User:
    """
    Get current authenticated user from JWT token
    
    Usage: user: User = Depends(get_current_user)
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token from "Bearer <token>" format
    try:
        if token.startswith("Bearer "):
            token = token[7:]
    except:
        pass
    
    payload = decode_token(token)
    if payload is None or is_token_expired(payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token type
    if not verify_token_type(payload, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = get_user_id_from_token(payload)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_from_header(
    authorization: str = None,
    db: Session = Depends(get_db)
) -> User:
    """Alternative way to get current user from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    return get_current_user(authorization, db)


# ═══ Endpoints ═══

@router.post("/register", response_model=TokenData, status_code=status.HTTP_201_CREATED)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user
    
    - **email**: User email (must be unique)
    - **password**: At least 8 characters
    - **name**: User's full name
    - **business_type**: Optional business type
    """
    # Validate email uniqueness
    existing_user = db.query(User).filter(User.email == user_create.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Validate password strength
    pwd_validation = validate_password_strength(user_create.password)
    if not pwd_validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(pwd_validation["errors"])
        )
    
    # Create new user
    hashed_password = hash_password(user_create.password)
    new_user = User(
        name=user_create.name,
        email=user_create.email,
        password_hash=hashed_password,
        business_type=user_create.business_type,
        timezone=user_create.timezone,
        is_active=True,
        is_verified=False
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create default preferences
    preferences = UserPreference(user_id=new_user.id)
    db.add(preferences)
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(new_user.id, new_user.email)
    refresh_token = create_refresh_token(new_user.id, new_user.email)
    
    return TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=60 * 60 * 24  # 24 hours in seconds
    )


@router.post("/login", response_model=TokenData)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login user with email and password
    
    - **email**: User email
    - **password**: User password
    """
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    
    return TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=60 * 60 * 24
    )


@router.post("/refresh", response_model=TokenData)
async def refresh_access_token(token_refresh: TokenRefresh, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Valid refresh token
    """
    payload = decode_token(token_refresh.refresh_token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Verify token type
    if not verify_token_type(payload, "refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    # Check expiration
    if is_token_expired(payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )
    
    user_id = get_user_id_from_token(payload)
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new access token
    access_token = create_access_token(user.id, user.email)
    
    return TokenData(
        access_token=access_token,
        refresh_token=token_refresh.refresh_token,  # Return same refresh token
        expires_in=60 * 60 * 24
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user (invalidates token on client)
    Token is still valid on backend until expiration
    (In production, implement token blacklist)
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserDetailResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information
    """
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile information
    """
    # Update fields
    if user_update.name:
        current_user.name = user_update.name
    if user_update.phone:
        current_user.phone = user_update.phone
    if user_update.timezone:
        current_user.timezone = user_update.timezone
    if user_update.business_type:
        current_user.business_type = user_update.business_type
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user's password
    """
    # Verify current password
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    pwd_validation = validate_password_strength(new_password)
    if not pwd_validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(pwd_validation["errors"])
        )
    
    # Update password
    current_user.password_hash = hash_password(new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}


@router.delete("/account", status_code=status.HTTP_200_OK)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete user account and all associated data
    """
    db.delete(current_user)
    db.commit()
    
    return {"message": "Account deleted successfully"}
