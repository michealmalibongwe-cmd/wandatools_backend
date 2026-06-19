"""
WandaTools Backend
FastAPI application for financial management system
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══ Routes ═══

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "WandaTools API",
        "version": "1.0.0",
        "docs": "/api/docs"
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
        "status": "running"
    }

# Auth endpoints
@app.post("/api/v1/auth/register")
async def register(name: str, email: str, password: str):
    """Register new user"""
    return {
        "id": 1,
        "name": name,
        "email": email,
        "message": "User registered successfully"
    }

@app.post("/api/v1/auth/login")
async def login(email: str, password: str):
    """Login user"""
    return {
        "access_token": "test_token_12345",
        "refresh_token": "test_refresh_12345",
        "token_type": "bearer",
        "expires_in": 86400
    }

@app.get("/api/v1/auth/me")
async def get_current_user():
    """Get current user"""
    return {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "created_at": "2025-06-18T10:00:00"
    }

# Tools endpoints
@app.get("/api/v1/tools/transactions")
async def list_transactions():
    """List transactions"""
    return {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "total_pages": 0
    }

@app.post("/api/v1/tools/transactions")
async def create_transaction(type: str, amount: float, category: str, description: str):
    """Create transaction"""
    return {
        "id": 1,
        "type": type,
        "amount": amount,
        "category": category,
        "description": description,
        "created_at": "2025-06-18T10:00:00"
    }

@app.get("/api/v1/tools/dashboard/summary")
async def get_dashboard_summary():
    """Get dashboard summary"""
    return {
        "total_income": 42500.00,
        "total_expenses": 18240.00,
        "net_profit": 24260.00,
        "transaction_count": 47,
        "month": "2025-06",
        "income_by_category": {},
        "expense_by_category": {}
    }

# WandaAI endpoints
@app.post("/api/v1/wandaai/query")
async def ask_wandaai(question: str, mode: str = "insights"):
    """Ask WandaAI"""
    return {
        "response": "Based on your financial data, here's an insight about your finances.",
        "mode": mode,
        "confidence": 0.92,
        "recommendations": [
            "Review your spending regularly",
            "Set financial goals"
        ]
    }

@app.get("/api/v1/wandaai/modes")
async def get_ai_modes():
    """Get WandaAI modes"""
    return {
        "modes": [
            {"name": "Financial Insights", "id": "insights"},
            {"name": "Smart Recommendations", "id": "recommendations"},
            {"name": "Business Assistant", "id": "business"}
        ]
    }

# Support endpoints
@app.get("/api/v1/support/faq")
async def get_faq():
    """Get FAQ"""
    return {
        "faq_items": [
            {
                "id": 1,
                "question": "Is my data secure?",
                "answer": "Yes, we use bank-level encryption."
            }
        ],
        "total": 1
    }

@app.post("/api/v1/support/contact")
async def submit_contact(name: str, email: str, message: str):
    """Submit contact form"""
    return {
        "id": 1,
        "status": "received",
        "message": "Thank you for contacting WandaTools."
    }

@app.get("/api/v1/support/status")
async def support_status():
    """Get support status"""
    return {
        "status": "operational",
        "support_hours": "9AM-5PM SAST Mon-Fri"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )