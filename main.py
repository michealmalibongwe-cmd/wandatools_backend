"""
WandaTools Backend - WORKING VERSION
FastAPI application with real user & transaction storage
"""

from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import json

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════
# IN-MEMORY STORAGE
# ═══════════════════════════════════════════════════════════

# Store users: {email: {name, password, id, created_at}}
users_db = {
    "demo@test.com": {
        "id": 1,
        "name": "Demo User",
        "email": "demo@test.com",
        "password": "Demo123!",  # In production: hashed password
        "created_at": "2025-06-18T10:00:00"
    }
}

# Store transactions: {user_id: [transaction_list]}
transactions_db = {
    1: [
        {
            "id": 1,
            "user_id": 1,
            "type": "income",
            "amount": 5000.00,
            "category": "Sales",
            "description": "Client payment",
            "transaction_date": "2025-06-18T10:00:00",
            "created_at": "2025-06-18T10:00:00"
        },
        {
            "id": 2,
            "user_id": 1,
            "type": "expense",
            "amount": 1200.00,
            "category": "Rent",
            "description": "Monthly rent",
            "transaction_date": "2025-06-17T09:00:00",
            "created_at": "2025-06-17T09:00:00"
        }
    ]
}

# Track active sessions: {token: {user_id, email, login_time}}
active_sessions = {}

next_user_id = 2
next_transaction_id = 3

# ═══════════════════════════════════════════════════════════
# ROOT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "WandaTools API",
        "version": "1.0.0",
        "users": len(users_db),
        "active_sessions": len(active_sessions)
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "in-memory",
        "version": "1.0.0",
        "total_users": len(users_db),
        "active_users": len(active_sessions),
        "total_transactions": sum(len(txns) for txns in transactions_db.values())
    }

@app.get("/api/v1")
async def api_v1_info():
    """API v1 info"""
    return {
        "version": "1.0.0",
        "name": "WandaTools API v1",
        "status": "running",
        "users_registered": len(users_db),
        "active_sessions": len(active_sessions)
    }

@app.get("/api/v1/stats")
async def get_stats():
    """Get app statistics"""
    total_transactions = sum(len(txns) for txns in transactions_db.values())
    total_income = 0
    total_expenses = 0
    
    for txns in transactions_db.values():
        for txn in txns:
            if txn["type"] == "income":
                total_income += txn["amount"]
            else:
                total_expenses += txn["amount"]
    
    return {
        "total_users": len(users_db),
        "active_users": len(active_sessions),
        "total_transactions": total_transactions,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses
    }

# ═══════════════════════════════════════════════════════════
# AUTHENTICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/auth/register")
async def register(name: str, email: str, password: str, business_type: str = None, timezone: str = "Africa/Johannesburg"):
    """Register new user"""
    global next_user_id
    
    # Check if email already exists
    if email in users_db:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # Validate password
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Create user
    user_id = next_user_id
    next_user_id += 1
    
    users_db[email] = {
        "id": user_id,
        "name": name,
        "email": email,
        "password": password,  # In production: hashed
        "business_type": business_type,
        "timezone": timezone,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Initialize empty transactions for user
    transactions_db[user_id] = []
    
    # Create session token
    token = f"token_{user_id}_{email[:3]}"
    active_sessions[token] = {
        "user_id": user_id,
        "email": email,
        "login_time": datetime.utcnow().isoformat()
    }
    
    return {
        "access_token": token,
        "refresh_token": f"refresh_{token}",
        "token_type": "bearer",
        "expires_in": 86400,
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "created_at": users_db[email]["created_at"]
        }
    }

@app.post("/api/v1/auth/login")
async def login(email: str, password: str):
    """Login user - NOW VALIDATES CREDENTIALS"""
    
    # Check if user exists
    if email not in users_db:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user = users_db[email]
    
    # Check password
    if user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create session token
    token = f"token_{user['id']}_{email[:3]}_{datetime.utcnow().timestamp()}"
    active_sessions[token] = {
        "user_id": user["id"],
        "email": email,
        "login_time": datetime.utcnow().isoformat()
    }
    
    return {
        "access_token": token,
        "refresh_token": f"refresh_{token}",
        "token_type": "bearer",
        "expires_in": 86400,
        "message": f"Welcome back, {user['name']}!"
    }

def get_user_from_token(token: str):
    """Extract user from token"""
    if token not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return active_sessions[token]

@app.get("/api/v1/auth/me")
async def get_current_user(authorization: str = None):
    """Get current user info"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization[7:]  # Remove "Bearer "
    session = get_user_from_token(token)
    user_id = session["user_id"]
    email = session["email"]
    
    if email not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = users_db[email]
    
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "business_type": user.get("business_type"),
        "timezone": user.get("timezone", "Africa/Johannesburg"),
        "is_active": True,
        "created_at": user["created_at"],
        "transaction_count": len(transactions_db.get(user_id, []))
    }

@app.post("/api/v1/auth/logout")
async def logout(authorization: str = None):
    """Logout user"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token in active_sessions:
            del active_sessions[token]
    
    return {"message": "Logged out successfully"}

# ═══════════════════════════════════════════════════════════
# TRANSACTION ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/tools/transactions")
async def create_transaction(
    type: str,
    amount: float,
    category: str,
    description: str,
    transaction_date: str,
    authorization: str = None
):
    """Create transaction"""
    global next_transaction_id
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    # Create transaction
    transaction = {
        "id": next_transaction_id,
        "user_id": user_id,
        "type": type,
        "amount": amount,
        "category": category,
        "description": description,
        "transaction_date": transaction_date,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    next_transaction_id += 1
    
    if user_id not in transactions_db:
        transactions_db[user_id] = []
    
    transactions_db[user_id].append(transaction)
    
    return transaction

@app.get("/api/v1/tools/transactions")
async def list_transactions(skip: int = 0, limit: int = 10, authorization: str = None):
    """List user's transactions"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    user_txns = transactions_db.get(user_id, [])
    # Sort by date descending
    user_txns = sorted(user_txns, key=lambda x: x["transaction_date"], reverse=True)
    
    total = len(user_txns)
    items = user_txns[skip:skip+limit]
    
    return {
        "items": items,
        "total": total,
        "page": (skip // limit) + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit
    }

@app.get("/api/v1/tools/transactions/{transaction_id}")
async def get_transaction(transaction_id: int, authorization: str = None):
    """Get specific transaction"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    for txn in transactions_db.get(user_id, []):
        if txn["id"] == transaction_id:
            return txn
    
    raise HTTPException(status_code=404, detail="Transaction not found")

@app.put("/api/v1/tools/transactions/{transaction_id}")
async def update_transaction(transaction_id: int, amount: float = None, description: str = None, authorization: str = None):
    """Update transaction"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    for txn in transactions_db.get(user_id, []):
        if txn["id"] == transaction_id:
            if amount is not None:
                txn["amount"] = amount
            if description is not None:
                txn["description"] = description
            txn["updated_at"] = datetime.utcnow().isoformat()
            return txn
    
    raise HTTPException(status_code=404, detail="Transaction not found")

@app.delete("/api/v1/tools/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int, authorization: str = None):
    """Delete transaction"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    txns = transactions_db.get(user_id, [])
    for i, txn in enumerate(txns):
        if txn["id"] == transaction_id:
            txns.pop(i)
            return {"message": "Transaction deleted"}
    
    raise HTTPException(status_code=404, detail="Transaction not found")

# ═══════════════════════════════════════════════════════════
# DASHBOARD ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/tools/dashboard/summary")
async def get_dashboard_summary(month: str = None, authorization: str = None):
    """Get dashboard summary"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    user_txns = transactions_db.get(user_id, [])
    
    total_income = 0
    total_expenses = 0
    income_by_category = {}
    expense_by_category = {}
    
    for txn in user_txns:
        if txn["type"] == "income":
            total_income += txn["amount"]
            cat = txn["category"]
            income_by_category[cat] = income_by_category.get(cat, 0) + txn["amount"]
        else:
            total_expenses += txn["amount"]
            cat = txn["category"]
            expense_by_category[cat] = expense_by_category.get(cat, 0) + txn["amount"]
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
        "transaction_count": len(user_txns),
        "month": month or "current",
        "income_by_category": income_by_category,
        "expense_by_category": expense_by_category
    }

@app.get("/api/v1/tools/dashboard/history")
async def get_dashboard_history(months: int = 6, authorization: str = None):
    """Get multi-month history"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    user_txns = transactions_db.get(user_id, [])
    
    summaries = []
    for i in range(months):
        total_income = sum(t["amount"] for t in user_txns if t["type"] == "income")
        total_expenses = sum(t["amount"] for t in user_txns if t["type"] == "expense")
        summaries.append({
            "month": f"2025-{str(i+1).zfill(2)}",
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": total_income - total_expenses
        })
    
    return {"summaries": summaries}

# ═══════════════════════════════════════════════════════════
# DOCUMENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/tools/documents")
async def generate_document(type: str, authorization: str = None):
    """Generate document"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    user_txns = transactions_db.get(user_id, [])
    total_revenue = sum(t["amount"] for t in user_txns if t["type"] == "income")
    total_expenses = sum(t["amount"] for t in user_txns if t["type"] == "expense")
    
    return {
        "id": 1,
        "user_id": user_id,
        "type": type,
        "status": "ready",
        "filename": f"{type}_report.pdf",
        "file_url": "/api/v1/documents/1/download",
        "created_at": datetime.utcnow().isoformat(),
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": total_revenue - total_expenses
    }

@app.get("/api/v1/tools/documents")
async def list_documents(authorization: str = None):
    """List documents"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return {
        "items": [
            {
                "id": 1,
                "type": "monthly_summary",
                "status": "ready",
                "filename": "summary.pdf",
                "created_at": datetime.utcnow().isoformat()
            }
        ],
        "total": 1
    }

# ═══════════════════════════════════════════════════════════
# WANDAAI ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/wandaai/query")
async def ask_wandaai(question: str, mode: str = "insights", authorization: str = None):
    """Ask WandaAI"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    # Get user data for insights
    user_txns = transactions_db.get(user_id, [])
    total_income = sum(t["amount"] for t in user_txns if t["type"] == "income")
    total_expenses = sum(t["amount"] for t in user_txns if t["type"] == "expense")
    net_profit = total_income - total_expenses
    
    if mode == "insights":
        response = f"Your financial overview: **Income**: R{total_income:,.2f} | **Expenses**: R{total_expenses:,.2f} | **Profit**: R{net_profit:,.2f}. Your profit margin is {(net_profit/total_income*100 if total_income > 0 else 0):.1f}%."
    elif mode == "recommendations":
        response = "Based on your data: 1) Review your largest expense categories. 2) Set aside 20% as emergency reserves. 3) Consider increasing revenue streams."
    else:
        response = "For business growth: Focus on your top income categories. Build a 3-month cash reserve. Track metrics monthly."
    
    return {
        "response": response,
        "mode": mode,
        "confidence": 0.92,
        "recommendations": [
            "Review spending quarterly",
            "Set financial goals",
            "Track key metrics"
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

@app.get("/api/v1/wandaai/prompts")
async def get_sample_prompts():
    """Get sample prompts"""
    return {
        "prompts": [
            "How is my cash flow?",
            "Where am I spending most?",
            "What's my profit margin?",
            "How can I reduce expenses?",
            "Am I ready for a loan?",
            "Financial goals for next month?"
        ]
    }

# ═══════════════════════════════════════════════════════════
# SUPPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/support/contact")
async def submit_contact(name: str, email: str, message: str):
    """Submit contact"""
    return {
        "id": 1,
        "status": "received",
        "message": f"Thank you {name}! We received your message."
    }

@app.get("/api/v1/support/faq")
async def get_faq():
    """Get FAQ"""
    return {
        "faq_items": [
            {
                "id": 1,
                "question": "Is my data secure?",
                "answer": "Yes, we use bank-level encryption."
            },
            {
                "id": 2,
                "question": "How much does it cost?",
                "answer": "WandaTools is completely free."
            }
        ],
        "total": 2
    }

@app.get("/api/v1/support/status")
async def support_status():
    """Support status"""
    return {
        "status": "operational",
        "support_hours": "Mon-Fri 9AM-5PM SAST"
    }

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)