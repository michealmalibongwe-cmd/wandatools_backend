"""
User Model
Represents users in the WandaTools system
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from db import Base


class UserRole(str, enum.Enum):
    """User roles in the system"""
    USER = "user"
    BUSINESS = "business"
    ADMIN = "admin"


class User(Base):
    """
    User model for authentication and profile management
    """
    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Personal information
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    business_type = Column(
        String(100),
        nullable=True,
        comment="Sole Trader, Small Business, Freelancer, Non-Profit, etc."
    )
    phone = Column(String(20), nullable=True)
    timezone = Column(String(50), default="Africa/Johannesburg")
    
    # Account status
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreference", uselist=False, back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', name='{self.name}')>"


class UserPreference(Base):
    """
    User preferences and settings
    """
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    
    # Notification preferences
    email_notifications = Column(Boolean, default=True)
    sms_alerts = Column(Boolean, default=False)
    weekly_reports = Column(Boolean, default=True)
    
    # Privacy
    allow_analytics = Column(Boolean, default=True)
    allow_feedback = Column(Boolean, default=False)
    
    # Settings
    currency = Column(String(10), default="ZAR")
    language = Column(String(10), default="en")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="preferences")
    
    def __repr__(self):
        return f"<UserPreference(user_id={self.user_id})>"
