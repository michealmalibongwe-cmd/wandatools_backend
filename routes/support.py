"""
WandaTools — routes/support.py
Support, FAQ, feedback and system health endpoints.

Note on Notification model:
  The original support.py referenced a Notification model — this does
  not exist in main.py yet. All notification references are removed.
  Ticket and notification features are stubbed until the model is added.

Endpoints:
  POST  /api/v1/support/contact    — submit contact form (saves to DB + sends email)
  GET   /api/v1/support/faq        — get FAQ items (filterable by search/category)
  GET   /api/v1/support/status     — support hours and contact info
  GET   /api/v1/support/health     — system/DB health check
  GET   /api/v1/support/tickets    — list support tickets (stub, auth required)
  POST  /api/v1/support/tickets    — create support ticket (stub, auth required)
  POST  /api/v1/support/feedback   — submit feedback (auth required)
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from services.email import EmailService

from db import get_db
from main import (
    ContactMessage,
    send_email,
    _contact_email_html,
    _contact_confirm_html,
    SUPPORT_EMAIL,
)
from routes.auth import get_current_user
from main import User

log = logging.getLogger("wandatools.support")

router = APIRouter(prefix="/api/v1/support", tags=["Support"])


# ─────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────

class ContactRequest(BaseModel):
    name:    str
    email:   EmailStr
    message: str
    subject: str = "WandaTools Support Request"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("message")
    @classmethod
    def message_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Message must be at least 10 characters")
        return v


class FeedbackRequest(BaseModel):
    feedback_text: str
    category:      str = "general"
    rating:        int | None = None

    @field_validator("feedback_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Feedback must be at least 5 characters")
        return v

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: str) -> str:
        valid = {"bug", "feature_request", "general", "praise"}
        v = v.lower().strip()
        if v not in valid:
            raise ValueError(f"category must be one of: {', '.join(valid)}")
        return v

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 5):
            raise ValueError("rating must be between 1 and 5")
        return v


class TicketRequest(BaseModel):
    subject: str
    message: str

    @field_validator("subject")
    @classmethod
    def subject_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Subject must be at least 3 characters")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Message must be at least 10 characters")
        return v


# ─────────────────────────────────────────────────────────────
# FAQ DATA
# ─────────────────────────────────────────────────────────────

_FAQ_ITEMS = [
    {
        "id": 1,
        "category": "security",
        "question": "Is my financial data secure?",
        "answer": (
            "Yes. WandaTools uses bcrypt password hashing and bank-level encryption "
            "to protect all your data. We comply with POPIA and never share your "
            "information with third parties."
        ),
    },
    {
        "id": 2,
        "category": "billing",
        "question": "How much does WandaTools cost?",
        "answer": (
            "WandaTools is free to start. You get access to Transactions, Dashboard, "
            "Documents, and WandaAI at no cost. Premium features are coming soon."
        ),
    },
    {
        "id": 3,
        "category": "technical",
        "question": "Can I export my data?",
        "answer": (
            "Yes. You can export your transaction history as CSV and generate "
            "professional PDF reports (Audit, Loan, Investment) at any time."
        ),
    },
    {
        "id": 4,
        "category": "security",
        "question": "Is WandaAI trained on my personal data?",
        "answer": (
            "No. WandaAI uses your data only to give you personalised insights. "
            "We do not use your financial information to train our AI models."
        ),
    },
    {
        "id": 5,
        "category": "technical",
        "question": "What currency does WandaTools use?",
        "answer": (
            "The default currency is Emalangeni (E) for Eswatini. You can set your "
            "preferred currency (E, ZAR, USD, GBP, EUR) when registering or per transaction."
        ),
    },
    {
        "id": 6,
        "category": "general",
        "question": "How do I delete my account?",
        "answer": (
            "You can delete your account from your profile settings using the "
            "DELETE /api/v1/auth/account endpoint. All data is permanently removed immediately."
        ),
    },
    {
        "id": 7,
        "category": "security",
        "question": "How long does my login session last?",
        "answer": (
            "Your access token lasts 30 minutes. Your device automatically refreshes it "
            "using a 7-day refresh token — so you stay logged in without re-entering your password."
        ),
    },
    {
        "id": 8,
        "category": "technical",
        "question": "Can I integrate WandaTools with my accounting software?",
        "answer": (
            "We are building integrations with popular accounting tools. For now, "
            "you can export CSV files and import into QuickBooks, Xero, or Pastel."
        ),
    },
    {
        "id": 9,
        "category": "general",
        "question": "Can I use WandaTools for my non-profit?",
        "answer": (
            "Yes! Email admin@wandatools.com with your registration details "
            "to discuss discounted options for registered NGOs and non-profits."
        ),
    },
]


# ─────────────────────────────────────────────────────────────
# CONTACT FORM
# ─────────────────────────────────────────────────────────────

@router.post("/contact", status_code=status.HTTP_201_CREATED)
async def submit_contact(
    body: ContactRequest,
    db:   Session = Depends(get_db),
):
    """
    Submit a support contact form.
    No authentication required — anyone can reach support.
    Saves the message to the contact_messages table.
    Sends an email to the support team and a confirmation to the user.
    """
    db_entry = ContactMessage(
        name=body.name,
        email=str(body.email),
        subject=body.subject,
        message=body.message,
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        msg_id = db_entry.id
        log.info(f"📬 Contact form saved: #{msg_id} from {body.email}")
    except Exception as exc:
        db.rollback()
        log.error(f"contact save error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save your message — please try again: {exc}",
        )

    # Email support team
    team_sent = send_email(
        to=SUPPORT_EMAIL,
        subject=f"[WandaTools Support #{msg_id}] {body.subject}",
        html_body=_contact_email_html(body.name, str(body.email), body.subject, body.message),
    )

    # Confirmation email to sender
    user_sent = send_email(
        to=str(body.email),
        subject="✅ We received your message — WandaTools Support",
        html_body=_contact_confirm_html(body.name),
    )

    email_status = "sent" if (team_sent and user_sent) else "queued"

    return {
        "id":      msg_id,
        "status":  "received",
        "email":   email_status,
        "message": (
            f"Thank you {body.name}! "
            f"We'll reply to {body.email} within 24–48 hours."
        ),
    }


# ─────────────────────────────────────────────────────────────
# FAQ
# ─────────────────────────────────────────────────────────────

@router.get("/faq")
async def get_faq(
    search:   str = Query(None, description="Search FAQ by keyword"),
    category: str = Query(None, description="Filter: security, billing, technical, general"),
):
    """
    Return FAQ items. No authentication required.
    Optional filters: search keyword and/or category.
    """
    valid_categories = {"security", "billing", "technical", "general"}
    if category and category.lower() not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"category must be one of: {', '.join(valid_categories)}",
        )

    items = _FAQ_ITEMS

    if search:
        s = search.lower()
        items = [
            f for f in items
            if s in f["question"].lower() or s in f["answer"].lower()
        ]

    if category:
        items = [f for f in items if f["category"] == category.lower()]

    return {"faq_items": items, "total": len(items)}


# ─────────────────────────────────────────────────────────────
# SUPPORT STATUS
# ─────────────────────────────────────────────────────────────

@router.get("/status")
async def get_support_status():
    """Return support hours and contact methods. No authentication required."""
    return {
        "status": "operational",
        "support_hours": {
            "monday_friday": "09:00 – 17:00 SAST",
            "saturday":      "10:00 – 14:00 SAST",
            "sunday":        "Closed",
        },
        "response_time": "24–48 hours",
        "contact_methods": [
            {
                "method":        "email",
                "address":       "admin@wandatools.com",
                "response_time": "24–48 hours",
            },
            {
                "method":        "phone",
                "number":        "+268 76 469 3531",
                "response_time": "During business hours",
            },
            {
                "method": "live_chat",
                "status": "Coming soon",
            },
        ],
    }


# ─────────────────────────────────────────────────────────────
# SYSTEM HEALTH
# ─────────────────────────────────────────────────────────────

@router.get("/health")
async def get_system_health(db: Session = Depends(get_db)):
    """
    Check system and database health.
    No authentication required — used by uptime monitors.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as exc:
        log.error(f"health check DB error: {exc}")
        db_status = "unhealthy"

    overall = "healthy" if db_status == "healthy" else "degraded"

    return {
        "status":    overall,
        "database":  db_status,
        "api":       "healthy",
        "version":   "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# SUPPORT TICKETS  (stub — no Ticket model yet)
# ─────────────────────────────────────────────────────────────

@router.get("/tickets")
async def get_support_tickets(current_user: User = Depends(get_current_user)):
    """
    List support tickets for the authenticated user.
    Ticket model not yet added to main.py — returns empty list for now.
    """
    return {
        "tickets": [],
        "total":   0,
        "message": "Support ticket system coming soon.",
    }


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_support_ticket(
    body:         TicketRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Create a support ticket for the authenticated user.
    Ticket model not yet in main.py — saves as a ContactMessage for now.
    """
    db_entry = ContactMessage(
        name=current_user.name,
        email=current_user.email,
        subject=body.subject,
        message=body.message,
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except Exception as exc:
        db.rollback()
        log.error(f"create_ticket error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create ticket: {exc}",
        )

    send_email(
        to=SUPPORT_EMAIL,
        subject=f"[WandaTools Ticket] {body.subject} — user {current_user.id}",
        html_body=_contact_email_html(
            current_user.name, current_user.email, body.subject, body.message
        ),
    )

    log.info(f"🎫 Ticket created by user {current_user.id}: {body.subject}")
    return {
        "ticket_id": db_entry.id,
        "status":    "open",
        "subject":   body.subject,
        "created_at": db_entry.created_at.isoformat(),
        "message":   "Support ticket created. We'll respond within 24–48 hours.",
    }


# ─────────────────────────────────────────────────────────────
# FEEDBACK  (auth required)
# ─────────────────────────────────────────────────────────────

@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body:         FeedbackRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Submit feedback about WandaTools.
    Saves as a ContactMessage with the feedback category and rating.
    """
    rating_note = f" | Rating: {body.rating}/5" if body.rating else ""
    full_message = f"[{body.category.upper()}]{rating_note}\n\n{body.feedback_text}"

    db_entry = ContactMessage(
        name=current_user.name,
        email=current_user.email,
        subject=f"Feedback: {body.category}",
        message=full_message,
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except Exception as exc:
        db.rollback()
        log.error(f"feedback error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save feedback: {exc}",
        )

    log.info(
        f"💬 Feedback from user {current_user.id}: "
        f"category={body.category} rating={body.rating}"
    )
    return {
        "feedback_id": db_entry.id,
        "category":    body.category,
        "rating":      body.rating,
        "created_at":  db_entry.created_at.isoformat(),
        "message":     "Thank you for your feedback! It helps us improve WandaTools.",
    }