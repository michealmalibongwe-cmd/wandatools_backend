"""
WandaTools Database Models
User, authentication, transaction, and security-related tables
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


# ═══ Enums ═══
class UserRole(str, enum.Enum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    ADMIN = "admin"


class LoginStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    LOCKED = "locked"
    MFA_REQUIRED = "mfa_required"


# ═══ Core Models ═══
class User(Base):
    __tablename__ = "users"

    # Basic info
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)

    # Account type
    role = Column(SQLEnum(UserRole), default=UserRole.INDIVIDUAL, nullable=False)

    # Business info (if role == BUSINESS)
    business_name = Column(String(255), nullable=True)
    business_type = Column(String(100), nullable=True)
    business_email = Column(String(255), unique=True, nullable=True)
    business_registration = Column(String(255), nullable=True)  # Encrypted
    phone = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)

    # Security
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)

    # MFA
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_type = Column(String(20), nullable=True)  # totp, email
    totp_secret = Column(String(255), nullable=True)  # Encrypted

    # Account lockout
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    last_ip = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    login_logs = relationship("LoginLog", back_populates="user", cascade="all, delete-orphan")
    email_tokens = relationship("EmailVerificationToken", back_populates="user", cascade="all, delete-orphan")
    password_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    mfa_otps = relationship("MFAOtp", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role.value,
            "business_name": self.business_name,
            "business_type": self.business_type,
            "phone": self.phone,
            "country": self.country,
            "is_verified": self.is_verified,
            "mfa_enabled": self.mfa_enabled,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None
        }


class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    ip_address = Column(String(50), nullable=False)
    status = Column(SQLEnum(LoginStatus), nullable=False)
    reason = Column(String(255), nullable=True)  # e.g., "Invalid password", "Account locked"
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="login_logs")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # income, expense
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="transactions")


class RefreshTokenBlacklist(Base):
    """Track revoked refresh tokens"""
    __tablename__ = "refresh_token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    token_jti = Column(String(255), unique=True, nullable=False)  # JWT ID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)


# ═══ Extra Security Models ═══
class EmailVerificationToken(Base):
    """Email verification tokens"""
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="email_tokens")


class PasswordResetToken(Base):
    """Password reset tokens"""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="password_tokens")


class MFAOtp(Base):
    """MFA OTP tokens"""
    __tablename__ = "mfa_otps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    otp = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="mfa_otps")
