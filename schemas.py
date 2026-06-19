"""
Pydantic Schemas
Request/Response validation models
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


# ═══ User Schemas ═══
class UserBase(BaseModel):
    """Base user schema"""
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    business_type: Optional[str] = None
    timezone: str = "Africa/Johannesburg"


class UserCreate(UserBase):
    """User registration schema"""
    password: str = Field(..., min_length=8, max_length=255)


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """User profile update schema"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = None
    timezone: Optional[str] = None
    business_type: Optional[str] = None


class UserResponse(UserBase):
    """User response schema"""
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Detailed user response with related data"""
    updated_at: datetime
    role: str


# ═══ Authentication Schemas ═══
class TokenData(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenRefresh(BaseModel):
    """Refresh token request"""
    refresh_token: str


# ═══ Transaction Schemas ═══
class TransactionBase(BaseModel):
    """Base transaction schema"""
    type: str = Field(..., pattern="^(income|expense|transfer)$")
    amount: float = Field(..., gt=0)
    category: str
    description: str = Field(..., min_length=1, max_length=500)
    transaction_date: datetime


class TransactionCreate(TransactionBase):
    """Create transaction schema"""
    reference_id: Optional[str] = None
    recipient_or_payer: Optional[str] = None
    notes: Optional[str] = None
    is_recurring: Optional[str] = None
    tax_deductible: Optional[str] = None


class TransactionUpdate(BaseModel):
    """Update transaction schema"""
    type: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    category: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class TransactionResponse(TransactionBase):
    """Transaction response schema"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    reference_id: Optional[str] = None
    recipient_or_payer: Optional[str] = None
    notes: Optional[str] = None
    is_recurring: Optional[str] = None
    tax_deductible: Optional[str] = None
    
    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    """List transactions response"""
    items: List[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DashboardSummary(BaseModel):
    """Dashboard summary schema"""
    total_income: float
    total_expenses: float
    net_profit: float
    transaction_count: int
    month: str
    income_by_category: dict
    expense_by_category: dict


# ═══ Document Schemas ═══
class DocumentCreate(BaseModel):
    """Create document schema"""
    type: str = Field(..., pattern="^(audit_report|loan_application|investment_report|monthly_summary|cash_flow|tax_summary)$")
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class DocumentResponse(BaseModel):
    """Document response schema"""
    id: int
    user_id: int
    type: str
    status: str
    filename: str
    file_url: Optional[str] = None
    created_at: datetime
    downloaded_at: Optional[datetime] = None
    total_revenue: Optional[float] = None
    total_expenses: Optional[float] = None
    net_profit: Optional[float] = None
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """List documents response"""
    items: List[DocumentResponse]
    total: int


# ═══ Notification Schemas ═══
class NotificationResponse(BaseModel):
    """Notification response schema"""
    id: int
    user_id: int
    type: str
    status: str
    title: str
    message: str
    icon: Optional[str] = None
    action_url: Optional[str] = None
    created_at: datetime
    is_important: bool
    
    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """List notifications response"""
    items: List[NotificationResponse]
    total: int
    unread_count: int


# ═══ Support/Contact Schemas ═══
class ContactSubmission(BaseModel):
    """Contact form submission"""
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = None
    subject: str = Field(..., min_length=5, max_length=255)
    message: str = Field(..., min_length=10, max_length=5000)


class ContactResponse(BaseModel):
    """Contact submission response"""
    id: int
    status: str = "received"
    message: str = "Your message has been received. We'll get back to you within 24 hours."


# ═══ AI/WandaAI Schemas ═══
class AIQuery(BaseModel):
    """WandaAI query schema"""
    question: str = Field(..., min_length=5, max_length=1000)
    mode: str = Field(default="insights", pattern="^(insights|recommendations|business)$")


class AIResponse(BaseModel):
    """WandaAI response schema"""
    response: str
    mode: str
    confidence: float = Field(..., ge=0, le=1)
    insights: Optional[dict] = None
    recommendations: Optional[List[str]] = None


# ═══ Error Response ═══
class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    details: Optional[str] = None
    status_code: int


# ═══ Pagination ═══
class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
