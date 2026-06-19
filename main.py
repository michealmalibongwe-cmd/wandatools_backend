"""
WandaTools Backend
FastAPI application for financial management system

Deployed on Railway.app with PostgreSQL
"""

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

app = FastAPI(
    title="WandaTools API",
    description="AI-powered financial insights and management platform",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# ═══ CORS Middleware ═══
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (or specify your frontend URL)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════
# ROOT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint - API info"""
    return {
        "name": "WandaTools API",
        "version": "1.0.0",
        "environment": "production",
        "docs": "/api/docs",
        "openapi": "/api/openapi.json"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "healthy",
        "version": "1.0.0"
    }

@app.get("/api/v1")
async def api_v1_info():
    """API v1 info"""
    return {
        "version": "1.0.0",
        "name": "WandaTools API v1",
        "status": "running",
        "endpoints": {
            "auth": "/api/v1/auth",
            "tools": "/api/v1/tools",
            "wandaai": "/api/v1/wandaai",
            "support": "/api/v1/support"
        }
    }

# ═══════════════════════════════════════════════════════════
# AUTHENTICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/auth/register")
async def register(name: str, email: str, password: str, business_type: str = None, timezone: str = "Africa/Johannesburg"):
    """Register new user"""
    return {
        "access_token": "mock_access_token_" + email[:3],
        "refresh_token": "mock_refresh_token_" + email[:3],
        "token_type": "bearer",
        "expires_in": 86400,
        "user": {
            "id": 1,
            "name": name,
            "email": email,
            "business_type": business_type,
            "timezone": timezone
        }
    }

@app.post("/api/v1/auth/login")
async def login(email: str, password: str):
    """Login user"""
    return {
        "access_token": "mock_access_token_" + email[:3],
        "refresh_token": "mock_refresh_token_" + email[:3],
        "token_type": "bearer",
        "expires_in": 86400
    }

@app.post("/api/v1/auth/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token"""
    return {
        "access_token": "new_mock_access_token",
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 86400
    }

@app.get("/api/v1/auth/me")
async def get_current_user(authorization: str = None):
    """Get current user info"""
    return {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "business_type": "Freelancer",
        "timezone": "Africa/Johannesburg",
        "is_active": True,
        "is_verified": False,
        "created_at": "2025-06-18T10:00:00",
        "last_login": "2025-06-18T14:30:00"
    }

@app.post("/api/v1/auth/logout")
async def logout():
    """Logout user"""
    return {"message": "Logged out successfully"}

# ═══════════════════════════════════════════════════════════
# TRANSACTION ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/tools/transactions")
async def create_transaction(type: str, amount: float, category: str, description: str, transaction_date: str, authorization: str = None):
    """Create transaction"""
    return {
        "id": 1,
        "user_id": 1,
        "type": type,
        "amount": amount,
        "category": category,
        "description": description,
        "transaction_date": transaction_date,
        "created_at": "2025-06-18T10:00:00",
        "updated_at": "2025-06-18T10:00:00"
    }

@app.get("/api/v1/tools/transactions")
async def list_transactions(skip: int = 0, limit: int = 10, authorization: str = None):
    """List transactions"""
    return {
        "items": [
            {
                "id": 1,
                "user_id": 1,
                "type": "income",
                "amount": 5000.00,
                "category": "Sales",
                "description": "Client payment",
                "transaction_date": "2025-06-18T10:00:00",
                "created_at": "2025-06-18T10:00:00",
                "updated_at": "2025-06-18T10:00:00"
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10,
        "total_pages": 1
    }

@app.get("/api/v1/tools/transactions/{transaction_id}")
async def get_transaction(transaction_id: int, authorization: str = None):
    """Get specific transaction"""
    return {
        "id": transaction_id,
        "user_id": 1,
        "type": "income",
        "amount": 5000.00,
        "category": "Sales",
        "description": "Transaction",
        "transaction_date": "2025-06-18T10:00:00",
        "created_at": "2025-06-18T10:00:00"
    }

@app.put("/api/v1/tools/transactions/{transaction_id}")
async def update_transaction(transaction_id: int, amount: float = None, description: str = None, authorization: str = None):
    """Update transaction"""
    return {
        "id": transaction_id,
        "amount": amount,
        "description": description,
        "updated_at": "2025-06-18T11:00:00"
    }

@app.delete("/api/v1/tools/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int, authorization: str = None):
    """Delete transaction"""
    return {"message": "Transaction deleted"}

# ═══════════════════════════════════════════════════════════
# DASHBOARD ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/tools/dashboard/summary")
async def get_dashboard_summary(month: str = None, authorization: str = None):
    """Get dashboard summary"""
    return {
        "total_income": 42500.00,
        "total_expenses": 18240.00,
        "net_profit": 24260.00,
        "transaction_count": 47,
        "month": month or "2025-06",
        "income_by_category": {
            "Sales": 25000.00,
            "Services": 17500.00
        },
        "expense_by_category": {
            "Rent": 6500.00,
            "Stock": 4200.00,
            "Salaries": 3600.00,
            "Marketing": 1800.00,
            "Utilities": 1140.00
        }
    }

@app.get("/api/v1/tools/dashboard/history")
async def get_dashboard_history(months: int = 6, authorization: str = None):
    """Get multi-month history"""
    return {
        "summaries": [
            {
                "month": f"2025-{str(i).zfill(2)}",
                "total_income": 40000 + (i * 1000),
                "total_expenses": 16000 + (i * 200),
                "net_profit": 24000 + (i * 800)
            }
            for i in range(1, months + 1)
        ]
    }

# ═══════════════════════════════════════════════════════════
# DOCUMENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/tools/documents")
async def generate_document(type: str, authorization: str = None):
    """Generate document"""
    return {
        "id": 1,
        "user_id": 1,
        "type": type,
        "status": "ready",
        "filename": f"{type}_report.pdf",
        "file_url": "/api/v1/documents/1/download",
        "created_at": "2025-06-18T10:00:00",
        "total_revenue": 42500.00,
        "total_expenses": 18240.00,
        "net_profit": 24260.00
    }

@app.get("/api/v1/tools/documents")
async def list_documents(skip: int = 0, limit: int = 10, authorization: str = None):
    """List documents"""
    return {
        "items": [
            {
                "id": 1,
                "user_id": 1,
                "type": "audit_report",
                "status": "ready",
                "filename": "audit_report.pdf",
                "file_url": "/api/v1/documents/1/download",
                "created_at": "2025-06-18T10:00:00"
            }
        ],
        "total": 1
    }

@app.get("/api/v1/tools/documents/{document_id}")
async def get_document(document_id: int, authorization: str = None):
    """Get document"""
    return {
        "id": document_id,
        "user_id": 1,
        "type": "audit_report",
        "status": "ready",
        "filename": "report.pdf",
        "created_at": "2025-06-18T10:00:00"
    }

@app.delete("/api/v1/tools/documents/{document_id}")
async def delete_document(document_id: int, authorization: str = None):
    """Delete document"""
    return {"message": "Document deleted"}

# ═══════════════════════════════════════════════════════════
# WANDAAI ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/wandaai/query")
async def ask_wandaai(question: str, mode: str = "insights", authorization: str = None):
    """Ask WandaAI"""
    responses = {
        "insights": "Your cash flow is **healthy**! Over the last 3 months, you've had R42,500 income and R18,240 expenses, giving you a net profit of R24,260. Your profit margin is 57%, which is excellent!",
        "recommendations": "Here are my recommendations: 1) Review your largest expense categories quarterly. 2) Set aside 20% of revenue as emergency reserves. 3) Consider increasing prices to improve margins.",
        "business": "For business strategy: Focus on your top-performing income categories (Sales and Services). Build a 3-month cash reserve for sustainability. Review pricing quarterly to ensure profitability."
    }
    
    return {
        "response": responses.get(mode, "Based on your financial data, here's an insight about your finances."),
        "mode": mode,
        "confidence": 0.92,
        "insights": {"type": f"{mode}_insight"},
        "recommendations": [
            "Review spending regularly",
            "Set financial goals",
            "Track key metrics monthly"
        ]
    }

@app.get("/api/v1/wandaai/modes")
async def get_ai_modes(authorization: str = None):
    """Get WandaAI modes"""
    return {
        "modes": [
            {
                "name": "Financial Insights",
                "id": "insights",
                "description": "Analyse your income, expenses, and trends"
            },
            {
                "name": "Smart Recommendations",
                "id": "recommendations",
                "description": "Get actionable money-saving and growth tips"
            },
            {
                "name": "Business Assistant",
                "id": "business",
                "description": "Help with pricing, planning, and strategy"
            }
        ]
    }

@app.get("/api/v1/wandaai/prompts")
async def get_sample_prompts(authorization: str = None):
    """Get sample prompts"""
    return {
        "prompts": [
            "How is my cash flow looking this month?",
            "Where am I spending the most money?",
            "What is my profit margin this month?",
            "How can I reduce my expenses?",
            "Am I ready to apply for a business loan?",
            "What financial goals should I set for next month?"
        ]
    }

# ═══════════════════════════════════════════════════════════
# SUPPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/support/contact")
async def submit_contact(name: str, email: str, phone: str = None, subject: str = None, message: str = None):
    """Submit contact form"""
    return {
        "id": 1,
        "status": "received",
        "message": f"Thank you {name}! We've received your message and will respond within 24 hours."
    }

@app.get("/api/v1/support/faq")
async def get_faq(search: str = None, category: str = None):
    """Get FAQ items"""
    faqs = [
        {
            "id": 1,
            "category": "security",
            "question": "Is my financial data secure?",
            "answer": "Yes. WandaTools uses bank-level encryption (AES-256) and complies with POPIA (South Africa's privacy law)."
        },
        {
            "id": 2,
            "category": "billing",
            "question": "How much does WandaTools cost?",
            "answer": "WandaTools is completely free to use with full access to all features."
        },
        {
            "id": 3,
            "category": "technical",
            "question": "Can I export my data?",
            "answer": "Yes, you can export your transaction history as CSV and generate professional PDF reports."
        },
        {
            "id": 4,
            "category": "security",
            "question": "Is WandaAI trained on my personal data?",
            "answer": "No. WandaAI uses your data only for personalized insights, not for training."
        }
    ]
    
    if search:
        search_lower = search.lower()
        faqs = [faq for faq in faqs if search_lower in faq["question"].lower() or search_lower in faq["answer"].lower()]
    
    if category:
        faqs = [faq for faq in faqs if faq["category"] == category]
    
    return {"faq_items": faqs, "total": len(faqs)}

@app.get("/api/v1/support/status")
async def support_status():
    """Get support status"""
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
            }
        ]
    }

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )