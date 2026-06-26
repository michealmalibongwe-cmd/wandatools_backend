"""
WandaTools — notifications.py
Location: ROOT folder (same level as main.py)

Contains:
  - NotificationType, NotificationStatus enums
  - Notification model
  - NotificationLog model
  - NotificationService class
"""

import enum
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SQLEnum,
    ForeignKey, Index, Integer, String, Text
)
from sqlalchemy.orm import Session, relationship

from main import Base, User

log = logging.getLogger("wandatools.notifications")


# ─────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────

class NotificationType(str, enum.Enum):
    ALERT    = "alert"
    INSIGHT  = "insight"
    REMINDER = "reminder"
    SUCCESS  = "success"
    WARNING  = "warning"
    ERROR    = "error"
    INFO     = "info"


class NotificationStatus(str, enum.Enum):
    UNREAD   = "unread"
    READ     = "read"
    ARCHIVED = "archived"


class DeliveryMethod(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL  = "email"
    SMS    = "sms"
    PUSH   = "push"


class DeliveryStatus(str, enum.Enum):
    SENT      = "sent"
    DELIVERED = "delivered"
    FAILED    = "failed"
    BOUNCED   = "bounced"


# ─────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    type        = Column(SQLEnum(NotificationType),   nullable=False, index=True)
    status      = Column(SQLEnum(NotificationStatus), nullable=False,
                         default=NotificationStatus.UNREAD, index=True)
    title       = Column(String(255), nullable=False)
    message     = Column(Text,        nullable=False)
    description = Column(Text,        nullable=True)

    icon        = Column(String(50),  nullable=True)
    action_url  = Column(String(500), nullable=True)
    action_text = Column(String(100), nullable=True)

    related_type = Column(String(50),  nullable=True)
    related_id   = Column(Integer,     nullable=True)

    is_important = Column(Boolean, default=False, nullable=False)
    send_email   = Column(Boolean, default=False, nullable=False)
    send_sms     = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at    = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="notifications")
    logs = relationship("NotificationLog", back_populates="notification",
                        cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_notifications_user_status",  "user_id", "status"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user_id={self.user_id}, type='{self.type}')>"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def mark_as_read(self) -> None:
        self.status  = NotificationStatus.READ
        self.read_at = datetime.utcnow()


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id", ondelete="SET NULL"),
                             nullable=True, index=True)

    method        = Column(SQLEnum(DeliveryMethod), nullable=False)
    status        = Column(SQLEnum(DeliveryStatus), nullable=False)
    recipient     = Column(String(255), nullable=True)
    error_message = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at    = Column(DateTime, nullable=True)

    user         = relationship("User",         back_populates="notification_logs")
    notification = relationship("Notification", back_populates="logs")

    def __repr__(self) -> str:
        return f"<NotificationLog(id={self.id}, method='{self.method}', status='{self.status}')>"


# ─────────────────────────────────────────────────────────────
# NOTIFICATION SERVICE
# ─────────────────────────────────────────────────────────────

class NotificationService:
    """
    Central service for creating and managing notifications.
    All methods are static. Errors are logged but never crash the caller.

    Usage:
        from notifications import NotificationService
        NotificationService.create(db, user_id=user.id, ...)
    """

    _DEFAULT_ICONS: dict = {
        NotificationType.ALERT:    "warning",
        NotificationType.INSIGHT:  "lightbulb",
        NotificationType.REMINDER: "schedule",
        NotificationType.SUCCESS:  "check_circle",
        NotificationType.WARNING:  "error_outline",
        NotificationType.ERROR:    "cancel",
        NotificationType.INFO:     "info",
    }

    @staticmethod
    def create(
        db:               Session,
        user_id:          int,
        type:             NotificationType,
        title:            str,
        message:          str,
        description:      Optional[str] = None,
        icon:             Optional[str] = None,
        action_url:       Optional[str] = None,
        action_text:      Optional[str] = None,
        related_type:     Optional[str] = None,
        related_id:       Optional[int] = None,
        is_important:     bool          = False,
        send_email:       bool          = False,
        expires_in_hours: Optional[int] = None,
    ) -> Optional[Notification]:
        try:
            expires_at = (
                datetime.utcnow() + timedelta(hours=expires_in_hours)
                if expires_in_hours else None
            )
            notif = Notification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                description=description,
                icon=icon or NotificationService._DEFAULT_ICONS.get(type, "notifications"),
                action_url=action_url,
                action_text=action_text,
                related_type=related_type,
                related_id=related_id,
                is_important=is_important,
                send_email=send_email,
                expires_at=expires_at,
            )
            db.add(notif)
            db.flush()

            NotificationService._log(
                db=db, user_id=user_id, notification_id=notif.id,
                method=DeliveryMethod.IN_APP, status=DeliveryStatus.DELIVERED,
            )

            if send_email:
                NotificationService._send_email_notification(
                    db=db, user_id=user_id,
                    notification_id=notif.id,
                    title=title, message=message,
                )

            db.commit()
            log.info(f"🔔 Notification: user={user_id} type={type} title='{title}'")
            return notif

        except Exception as exc:
            db.rollback()
            log.error(f"NotificationService.create failed for user {user_id}: {exc}")
            return None

    @staticmethod
    def get_unread(db: Session, user_id: int) -> list:
        try:
            return (
                db.query(Notification)
                .filter(Notification.user_id == user_id,
                        Notification.status  == NotificationStatus.UNREAD)
                .order_by(Notification.created_at.desc())
                .all()
            )
        except Exception as exc:
            log.error(f"get_unread failed for user {user_id}: {exc}")
            return []

    @staticmethod
    def get_all(db: Session, user_id: int, skip: int = 0,
                limit: int = 20, status: Optional[NotificationStatus] = None):
        try:
            query = db.query(Notification).filter(Notification.user_id == user_id)
            if status:
                query = query.filter(Notification.status == status)
            total = query.count()
            items = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
            return items, total
        except Exception as exc:
            log.error(f"get_all failed for user {user_id}: {exc}")
            return [], 0

    @staticmethod
    def mark_read(db: Session, notification_id: int, user_id: int) -> bool:
        try:
            notif = (
                db.query(Notification)
                .filter(Notification.id == notification_id,
                        Notification.user_id == user_id)
                .first()
            )
            if not notif:
                return False
            notif.mark_as_read()
            db.commit()
            return True
        except Exception as exc:
            db.rollback()
            log.error(f"mark_read failed (notif={notification_id}): {exc}")
            return False

    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        try:
            count = (
                db.query(Notification)
                .filter(Notification.user_id == user_id,
                        Notification.status  == NotificationStatus.UNREAD)
                .update({"status": NotificationStatus.READ, "read_at": datetime.utcnow()})
            )
            db.commit()
            return count
        except Exception as exc:
            db.rollback()
            log.error(f"mark_all_read failed for user {user_id}: {exc}")
            return 0

    @staticmethod
    def unread_count(db: Session, user_id: int) -> int:
        try:
            return (
                db.query(Notification)
                .filter(Notification.user_id == user_id,
                        Notification.status  == NotificationStatus.UNREAD)
                .count()
            )
        except Exception as exc:
            log.error(f"unread_count failed for user {user_id}: {exc}")
            return 0

    @staticmethod
    def delete_expired(db: Session) -> int:
        try:
            count = (
                db.query(Notification)
                .filter(Notification.expires_at != None,         # noqa: E711
                        Notification.expires_at <  datetime.utcnow())
                .delete(synchronize_session=False)
            )
            db.commit()
            return count
        except Exception as exc:
            db.rollback()
            log.error(f"delete_expired failed: {exc}")
            return 0

    # ── Pre-built shortcuts ───────────────────────────────────

    @staticmethod
    def notify_transaction_created(db: Session, user_id: int,
                                   amount: float, currency: str,
                                   txn_type: str, txn_id: int) -> None:
        emoji = "💰" if txn_type == "income" else "💸"
        verb  = "Income" if txn_type == "income" else "Expense"
        NotificationService.create(
            db=db, user_id=user_id,
            type=NotificationType.SUCCESS if txn_type == "income" else NotificationType.INFO,
            title=f"{emoji} {verb} Recorded",
            message=f"{currency} {amount:,.2f} {verb.lower()} has been saved.",
            action_url=f"/tools/transactions/{txn_id}",
            action_text="View Transaction",
            related_type="transaction",
            related_id=txn_id,
            expires_in_hours=72,
        )

    @staticmethod
    def notify_low_balance_warning(db: Session, user_id: int,
                                   net_profit: float, currency: str) -> None:
        NotificationService.create(
            db=db, user_id=user_id,
            type=NotificationType.WARNING,
            title="⚠️ Cash Flow Alert",
            message=f"Your net position is {currency} {net_profit:,.2f}. Expenses exceed income.",
            action_url="/wandaai?mode=recommendations",
            action_text="Get Recommendations",
            is_important=True, send_email=True, expires_in_hours=168,
        )

    @staticmethod
    def notify_password_changed(db: Session, user_id: int) -> None:
        NotificationService.create(
            db=db, user_id=user_id,
            type=NotificationType.ALERT,
            title="🔑 Password Changed",
            message="Your WandaTools password was changed. If this wasn't you, contact support.",
            action_url="/support/contact",
            action_text="Contact Support",
            is_important=True, send_email=True, expires_in_hours=168,
        )

    @staticmethod
    def notify_wandaai_insight(db: Session, user_id: int, insight_summary: str) -> None:
        NotificationService.create(
            db=db, user_id=user_id,
            type=NotificationType.INSIGHT,
            title="🤖 New WandaAI Insight",
            message=insight_summary[:200],
            action_url="/wandaai",
            action_text="View Full Insight",
            expires_in_hours=48,
        )

    # ── Internal helpers ─────────────────────────────────────

    @staticmethod
    def _log(db: Session, user_id: int, method: DeliveryMethod,
             status: DeliveryStatus, notification_id: Optional[int] = None,
             recipient: Optional[str] = None, error_message: Optional[str] = None) -> None:
        try:
            db.add(NotificationLog(
                user_id=user_id,
                notification_id=notification_id,
                method=method, status=status,
                recipient=recipient,
                error_message=error_message,
                sent_at=datetime.utcnow() if status == DeliveryStatus.SENT else None,
            ))
        except Exception as exc:
            log.error(f"NotificationLog write failed: {exc}")

    @staticmethod
    def _send_email_notification(db: Session, user_id: int,
                                  notification_id: int,
                                  title: str, message: str) -> None:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return
            from services.email import EmailService
            html = f"""
            <html><body style="font-family:Arial,sans-serif;color:#333;padding:24px">
              <h2 style="color:#007BFF">🔔 {title}</h2>
              <p style="font-size:15px;line-height:1.6">{message}</p>
              <p style="margin-top:24px;color:#888;font-size:12px">— The WandaTools Team 🇸🇿</p>
            </body></html>
            """
            sent = EmailService.send_email(user.email, f"WandaTools: {title}", html)
            NotificationService._log(
                db=db, user_id=user_id, notification_id=notification_id,
                method=DeliveryMethod.EMAIL,
                status=DeliveryStatus.SENT if sent else DeliveryStatus.FAILED,
                recipient=user.email,
                error_message=None if sent else "SMTP send failed",
            )
        except Exception as exc:
            log.error(f"_send_email_notification failed for user {user_id}: {exc}")