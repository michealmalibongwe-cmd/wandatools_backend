"""
WandaTools — routes/users.py
Location: routes/ folder

User profile management endpoints.
Auth (register/login/logout/refresh) stays in routes/auth.py.
This file handles profile viewing and admin-level user management.

Endpoints:
  GET    /api/v1/users/me                  — get own profile (same as /auth/me)
  PUT    /api/v1/users/me                  — update own profile
  GET    /api/v1/users/me/stats            — get own transaction stats
  GET    /api/v1/users/me/notifications    — get own notifications
  POST   /api/v1/users/me/notifications/read-all  — mark all notifications read
  DELETE /api/v1/users/me                  — delete own account
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import get_db
from main import (
    User,
    SUPPORTED_CURRENCIES,
    DEFAULT_CURRENCY,
)
from notifications       import NotificationService, NotificationStatus
from routes.transactions import Transaction, TransactionType
from routes.auth         import get_current_user

log    = logging.getLogger("wandatools.users")
router = APIRouter(prefix="/api/v1/users", tags=["Users"])


# ─────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────

class ProfileUpdateRequest(BaseModel):
    name:          str | None = None
    timezone:      str | None = None
    currency:      str | None = None
    business_type: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("currency")
    @classmethod
    def currency_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency must be one of: {', '.join(SUPPORTED_CURRENCIES)}")
        return v


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _user_dict(user: User) -> dict:
    return {
        "id":            user.id,
        "name":          user.name,
        "email":         user.email,
        "business_type": user.business_type,
        "timezone":      user.timezone,
        "currency":      user.currency,
        "created_at":    user.created_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.get("/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's full profile."""
    return _user_dict(current_user)


@router.put("/me")
async def update_my_profile(
    body:         ProfileUpdateRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Update profile fields. Only include fields you want to change.
    Accepts: name, timezone, currency, business_type.
    """
    changed = False

    if body.name is not None:
        current_user.name = body.name.strip()
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
        return {**_user_dict(current_user), "message": "✅ Profile updated!"}
    except Exception as exc:
        db.rollback()
        log.error(f"profile update error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update profile: {exc}",
        )


@router.get("/me/stats")
async def get_my_stats(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Return a financial stats summary for the authenticated user.
    Total income, expenses, net profit and transaction counts.
    """
    try:
        txns = (
            db.query(Transaction)
            .filter(
                Transaction.user_id    == current_user.id,
                Transaction.is_deleted == False,           # noqa: E712
            )
            .all()
        )

        total_income   = sum(t.amount for t in txns if t.type == TransactionType.INCOME)
        total_expenses = sum(t.amount for t in txns if t.type == TransactionType.EXPENSE)
        net_profit     = total_income - total_expenses
        margin         = (net_profit / total_income * 100) if total_income > 0 else 0.0

        return {
            "user_id":           current_user.id,
            "currency":          current_user.currency,
            "total_income":      total_income,
            "total_expenses":    total_expenses,
            "net_profit":        net_profit,
            "profit_margin":     round(margin, 2),
            "transaction_count": len(txns),
            "income_count":      sum(1 for t in txns if t.type == TransactionType.INCOME),
            "expense_count":     sum(1 for t in txns if t.type == TransactionType.EXPENSE),
            "member_since":      current_user.created_at.isoformat(),
        }
    except Exception as exc:
        log.error(f"get_my_stats error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load stats: {exc}",
        )


@router.get("/me/notifications")
async def get_my_notifications(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
    skip:         int     = Query(0,  ge=0),
    limit:        int     = Query(20, ge=1, le=100),
    unread_only:  bool    = Query(False, description="Return only unread notifications"),
):
    """
    Return paginated notifications for the authenticated user.
    Use unread_only=true to get only unread ones.
    """
    filter_status = NotificationStatus.UNREAD if unread_only else None
    items, total  = NotificationService.get_all(
        db=db, user_id=current_user.id,
        skip=skip, limit=limit, status=filter_status,
    )

    return {
        "items": [
            {
                "id":          n.id,
                "type":        n.type,
                "status":      n.status,
                "title":       n.title,
                "message":     n.message,
                "icon":        n.icon,
                "action_url":  n.action_url,
                "action_text": n.action_text,
                "is_important": n.is_important,
                "created_at":  n.created_at.isoformat(),
                "read_at":     n.read_at.isoformat() if n.read_at else None,
            }
            for n in items
        ],
        "total":        total,
        "unread_count": NotificationService.unread_count(db, current_user.id),
        "page":         (skip // limit) + 1,
        "page_size":    limit,
        "total_pages":  (total + limit - 1) // limit if total > 0 else 1,
    }


@router.post("/me/notifications/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Mark all unread notifications as read for the authenticated user."""
    count = NotificationService.mark_all_read(db=db, user_id=current_user.id)
    return {"message": f"✅ {count} notification(s) marked as read."}


@router.post("/me/notifications/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: int,
    current_user:    User    = Depends(get_current_user),
    db:              Session = Depends(get_db),
):
    """Mark a single notification as read."""
    success = NotificationService.mark_read(
        db=db, notification_id=notification_id, user_id=current_user.id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found or does not belong to you",
        )
    return {"message": "✅ Notification marked as read."}


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Permanently delete the authenticated user's account and all associated data.
    This includes all transactions, refresh tokens, and notifications.
    This action cannot be undone.
    """
    user_id    = current_user.id
    user_email = current_user.email
    try:
        db.delete(current_user)
        db.commit()
        log.warning(f"🗑️  Account deleted: user {user_id} ({user_email})")
        return {"message": "✅ Your account and all data have been permanently deleted."}
    except Exception as exc:
        db.rollback()
        log.error(f"delete account error for user {user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete account: {exc}",
        )