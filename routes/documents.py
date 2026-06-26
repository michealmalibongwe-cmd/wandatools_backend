"""
WandaTools — routes/documents.py
Location: routes/ folder

Document generation endpoints — stub until Document model is added to main.py.

When ready to activate:
  1. Add Document model to main.py
  2. Add to User relationships: documents = relationship("Document", ...)
  3. Import in main.py: from routes.documents import Document
  4. Replace stub responses below with real logic
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import get_db
from main import User
from routes.auth import get_current_user

log    = logging.getLogger("wandatools.documents")
router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

VALID_DOC_TYPES = {
    "audit_report", "loan_application", "investment_report",
    "monthly_summary", "cash_flow", "tax_summary",
}

# ─────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────

class DocumentCreateRequest(BaseModel):
    type:         str
    period_start: Optional[str] = None
    period_end:   Optional[str] = None

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        if v not in VALID_DOC_TYPES:
            raise ValueError(f"type must be one of: {', '.join(VALID_DOC_TYPES)}")
        return v


# ─────────────────────────────────────────────────────────────
# STUB RESPONSE — used until Document model is added
# ─────────────────────────────────────────────────────────────

_STUB = {
    "message":    "Document generation is coming soon.",
    "status":     "not_implemented",
    "doc_types":  list(VALID_DOC_TYPES),
    "hint":       "Add the Document model to main.py to activate this feature.",
}


# ─────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def generate_document(
    body:         DocumentCreateRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Generate a financial document/report.
    Returns a stub response until the Document model is added to main.py.
    """
    log.info(f"📄 Document request: user={current_user.id} type={body.type} [STUB]")
    return {
        **_STUB,
        "requested_type": body.type,
        "user_id":        current_user.id,
        "requested_at":   datetime.utcnow().isoformat(),
    }


@router.get("")
async def list_documents(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
    skip:         int     = Query(0,  ge=0),
    limit:        int     = Query(10, ge=1, le=100),
):
    """List all documents for the authenticated user."""
    return {**_STUB, "items": [], "total": 0, "page": 1}


@router.get("/{document_id}")
async def get_document(
    document_id:  int,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Get a specific document by ID."""
    return {**_STUB, "document_id": document_id}


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id:  int,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Delete a document by ID."""
    return {**_STUB, "document_id": document_id}


@router.get("/types/list")
async def list_document_types(current_user: User = Depends(get_current_user)):
    """List all supported document types."""
    return {
        "doc_types": [
            {"id": "audit_report",      "name": "Audit Report",         "description": "Full audit-ready financial report"},
            {"id": "loan_application",  "name": "Loan Application",     "description": "Bank loan application package"},
            {"id": "investment_report", "name": "Investment Report",    "description": "Investment summary for stakeholders"},
            {"id": "monthly_summary",   "name": "Monthly Summary",      "description": "Monthly income and expense breakdown"},
            {"id": "cash_flow",         "name": "Cash Flow Analysis",   "description": "Detailed cash flow statement"},
            {"id": "tax_summary",       "name": "Tax Summary",          "description": "Annual tax-ready summary"},
        ]
    }