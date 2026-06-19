"""
Notification Model
Represents in-app notifications and alerts for users
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from db import Base


class NotificationType(str, enum.Enum):
    """Types of notifications"""
    ALERT = "alert"
    INSIGHT = "insight"
    REMINDER = "reminder"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class NotificationStatus(str, enum.Enum):
    """Notification read status"""
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class Notification(Base):
    """
    Notification model for user alerts and insights
    """
    __tablename__ = "notifications"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Notification content
    type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.UNREAD, nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    
    # Icon and action
    icon = Column(String(50), nullable=True, comment="Material icon name")
    action_url = Column(String(500), nullable=True, comment="Link to related resource")
    action_text = Column(String(100), nullable=True, comment="Button text")
    
    # Data context
    related_type = Column(String(50), nullable=True, comment="transaction, document, etc.")
    related_id = Column(Integer, nullable=True, comment="ID of related object")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Priority
    is_important = Column(Boolean, default=False)
    send_email = Column(Boolean, default=False)
    send_sms = Column(Boolean, default=False)
    
    # Relationship
    user = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type='{self.type}', status='{self.status}')>"


class NotificationLog(Base):
    """
    Log of all notifications sent (for audit trail)
    """
    __tablename__ = "notification_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=True)
    
    # Delivery method
    method = Column(String(50), nullable=False, comment="in_app, email, sms, push")
    status = Column(String(50), nullable=False, comment="sent, delivered, failed, bounced")
    
    # Details
    recipient = Column(String(255), nullable=True, comment="email or phone number")
    error_message = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<NotificationLog(id={self.id}, user_id={self.user_id}, method='{self.method}')>"
