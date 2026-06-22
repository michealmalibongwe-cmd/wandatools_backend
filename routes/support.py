"""
Support Routes
Contact form, FAQ, and support ticket endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from db import get_db
from schemas import ContactSubmission, ContactResponse
from models import Notification, NotificationType
from routes.auth import get_current_user
from models import User

router = APIRouter(prefix="/support", tags=["support"])


# ═══ Contact Submission ═══

@router.post("/contact", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def submit_contact_form(
    contact: ContactSubmission,
    db: Session = Depends(get_db)
):
    """
    Submit a contact form
    
    No authentication required for public support inquiries
    """
    # In production, you would:
    # 1. Save to database
    # 2. Send email to support team
    # 3. Create support ticket in external system
    
    # For now, we'll create a notification for logged-in users
    # and return success
    
    return ContactResponse(
        id=1,
        status="received",
        message="Thank you for contacting WandaTools. We'll get back to you within 24 hours at " + contact.email
    )


# ═══ FAQ Endpoints ═══

@router.get("/faq")
async def get_faq(
    search: str = None,
    category: str = None
):
    """
    Get FAQ items
    
    Optional filters:
    - **search**: Search FAQ by keyword
    - **category**: Filter by category (security, billing, technical, general)
    """
    faqs = [
        {
            "id": 1,
            "category": "security",
            "question": "Is my financial data secure?",
            "answer": "Yes. WandaTools uses bank-level encryption (AES-256) to protect all your data. We comply with POPIA, South Africa's privacy law, and never share your information with third parties."
        },
        {
            "id": 2,
            "category": "billing",
            "question": "How much does WandaTools cost?",
            "answer": "WandaTools is free to start. You get access to Transactions, Dashboard, Documents, and WandaAI at no cost. Premium features are coming soon with flexible pricing."
        },
        {
            "id": 3,
            "category": "technical",
            "question": "Can I export my data?",
            "answer": "Absolutely. You can export your transaction history as CSV and generate professional PDF reports (Audit, Loan, Investment) at any time."
        },
        {
            "id": 4,
            "category": "security",
            "question": "Is WandaAI trained on my personal data?",
            "answer": "No. WandaAI uses your data only to give you personalised insights. We don't use your financial information to train our AI model."
        },
        {
            "id": 5,
            "category": "technical",
            "question": "Can I integrate WandaTools with my accounting software?",
            "answer": "We're building integrations with popular SA accounting tools. For now, you can export CSV files and import into QuickBooks, Xero, or Pastel. APIs coming in Q3 2025."
        },
        {
            "id": 6,
            "category": "general",
            "question": "How do I delete my account?",
            "answer": "You can delete your account anytime from your Profile settings. All your data will be permanently removed within 30 days. No questions asked."
        },
        {
            "id": 7,
            "category": "billing",
            "question": "What payment methods do you accept?",
            "answer": "When premium features launch, we'll accept all major credit cards, EFT transfers, and mobile payment methods with monthly and annual options."
        },
        {
            "id": 8,
            "category": "general",
            "question": "Can I use WandaTools for my non-profit?",
            "answer": "Yes! We offer discounted pricing for registered NGOs and non-profits. Email support@wandatools.com with your registration details."
        }
    ]
    
    # Apply filters
    if search:
        search_lower = search.lower()
        faqs = [
            faq for faq in faqs
            if search_lower in faq["question"].lower() or search_lower in faq["answer"].lower()
        ]
    
    if category:
        faqs = [faq for faq in faqs if faq["category"] == category]
    
    return {
        "faq_items": faqs,
        "total": len(faqs)
    }


# ═══ Support Status ═══

@router.get("/status")
async def get_support_status():
    """Get support system status and support hours"""
    return {
        "status": "operational",
        "support_hours": {
            "monday_friday": "09:00 - 17:00 SAST",
            "saturday": "10:00 - 14:00 SAST",
            "sunday": "Closed"
        },
        "response_time": "24 hours",
        "contact_methods": [
            {
                "method": "email",
                "address": "support@wandatools.com",
                "response_time": "24 hours"
            },
            {
                "method": "phone",
                "number": "+27 (0) 76 469 3531",
                "response_time": "During business hours"
            },
            {
                "method": "live_chat",
                "status": "Coming soon"
            }
        ]
    }


# ═══ Authenticated User Support ═══

@router.get("/tickets")
async def get_support_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get support tickets for current user"""
    # In production, query actual support tickets table
    return {
        "tickets": [],
        "message": "You have no open support tickets"
    }


@router.post("/tickets")
async def create_support_ticket(
    subject: str,
    message: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a support ticket (authenticated users only)"""
    # In production, create actual ticket in database
    return {
        "ticket_id": 1,
        "status": "open",
        "created_at": datetime.utcnow(),
        "message": "Support ticket created successfully"
    }


# ═══ Feedback ═══

@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback_text: str,
    category: str = "general",
    rating: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback about WandaTools
    
    - **feedback_text**: Your feedback message
    - **category**: Type of feedback (bug, feature_request, general, praise)
    - **rating**: 1-5 star rating (optional)
    """
    if rating and not (1 <= rating <= 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5"
        )
    
    # In production, save feedback to database
    
    return {
        "message": "Thank you for your feedback!",
        "feedback_id": 1,
        "created_at": datetime.utcnow()
    }


# ═══ System Health ═══

@router.get("/health")
async def get_system_health(db: Session = Depends(get_db)):
    """
    Get system health status
    Includes database connectivity, API status, etc.
    """
    # Test database connection
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except:
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "api": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }
