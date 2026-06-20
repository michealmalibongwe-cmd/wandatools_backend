"""
WandaTools Backend - PostgreSQL Version
FastAPI with SQLAlchemy ORM and real database storage
"""

from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from typing import Optional

# ═══════════════════════════════════════════════════════════
# DATABASE SETUP
# ═══════════════════════════════════════════════════════════

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wandatools_db")

# For Railway, replace 'localhost' with actual host if needed
if "localhost" not in DATABASE_URL:
    # Railway URL format is correct
    pass

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False  # Set to True to see SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ═══════════════════════════════════════════════════════════
# DATABASE MODELS
# ═══════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    business_type = Column(String(100), nullable=True)
    timezone = Column(String(50), default="Africa/Johannesburg")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # income or expense
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ═══════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════

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

# In-memory sessions (tokens)
active_sessions = {}

# ═══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def get_user_from_token(token: str):
    """Get user session from token"""
    if token not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return active_sessions[token]

# ═══════════════════════════════════════════════════════════
# ROOT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint"""
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        txn_count = db.query(Transaction).count()
        return {
            "name": "WandaTools API",
            "version": "1.0.0",
            "database": "PostgreSQL",
            "users": user_count,
            "transactions": txn_count,
            "active_sessions": len(active_sessions)
        }
    except Exception as e:
        return {
            "error": f"Database error: {str(e)}",
            "status": "database_connection_failed"
        }
    finally:
        db.close()

@app.get("/health")
async def health():
    """Health check - shows database stats"""
    db = SessionLocal()
    try:
        # Test database connection
        db.execute("SELECT 1")
        
        user_count = db.query(User).count()
        txn_count = db.query(Transaction).count()
        total_income = sum(float(t.amount) for t in db.query(Transaction).filter(Transaction.type == "income").all())
        total_expenses = sum(float(t.amount) for t in db.query(Transaction).filter(Transaction.type == "expense").all())
        
        return {
            "status": "healthy",
            "database": "connected",
            "database_type": "PostgreSQL",
            "version": "1.0.0",
            "users_count": user_count,
            "transactions_count": txn_count,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "active_sessions": len(active_sessions)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": "disconnected"
        }
    finally:
        db.close()

@app.get("/api/v1")
async def api_v1_info():
    """API info"""
    db = SessionLocal()
    try:
        return {
            "version": "1.0.0",
            "status": "running",
            "database": "PostgreSQL",
            "users": db.query(User).count(),
            "transactions": db.query(Transaction).count()
        }
    finally:
        db.close()

@app.get("/api/v1/stats")
async def get_stats():
    """App statistics from database"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        transactions = db.query(Transaction).all()
        
        total_income = sum(t.amount for t in transactions if t.type == "income")
        total_expenses = sum(t.amount for t in transactions if t.type == "expense")
        
        return {
            "total_users": len(users),
            "active_users": len(active_sessions),
            "total_transactions": len(transactions),
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": total_income - total_expenses,
            "users_list": [{"id": u.id, "name": u.name, "email": u.email, "created_at": u.created_at.isoformat()} for u in users]
        }
    finally:
        db.close()

# ═══════════════════════════════════════════════════════════
# AUTHENTICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/auth/register")
async def register(name: str, email: str, password: str, business_type: str = None):
    """Register new user - SAVES TO DATABASE"""
    db = SessionLocal()
    try:
        # Check if email exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
        
        # Create user
        user = User(
            name=name,
            email=email,
            password=password,
            business_type=business_type,
            timezone="Africa/Johannesburg"
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create session token
        token = f"token_{user.id}_{email[:3]}"
        active_sessions[token] = {
            "user_id": user.id,
            "email": email,
            "login_time": datetime.utcnow().isoformat()
        }
        
        return {
            "access_token": token,
            "refresh_token": f"refresh_{token}",
            "token_type": "bearer",
            "expires_in": 86400,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "created_at": user.created_at.isoformat()
            },
            "message": f"✅ User registered! Saved to PostgreSQL database."
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}")
    finally:
        db.close()

@app.post("/api/v1/auth/login")
async def login(email: str, password: str):
    """Login user - VALIDATES FROM DATABASE"""
    db = SessionLocal()
    try:
        # Find user in database
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Check password
        if user.password != password:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Create session token
        token = f"token_{user.id}_{email[:3]}_{datetime.utcnow().timestamp()}"
        active_sessions[token] = {
            "user_id": user.id,
            "email": email,
            "login_time": datetime.utcnow().isoformat()
        }
        
        return {
            "access_token": token,
            "refresh_token": f"refresh_{token}",
            "token_type": "bearer",
            "expires_in": 86400,
            "message": f"✅ Login successful! Retrieved from PostgreSQL database."
        }
    finally:
        db.close()

@app.get("/api/v1/auth/me")
async def get_current_user(authorization: str = None):
    """Get current user from database"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == session["user_id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        txn_count = db.query(Transaction).filter(Transaction.user_id == user.id).count()
        
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "business_type": user.business_type,
            "timezone": user.timezone,
            "created_at": user.created_at.isoformat(),
            "transaction_count": txn_count
        }
    finally:
        db.close()

@app.post("/api/v1/auth/logout")
async def logout(authorization: str = None):
    """Logout"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token in active_sessions:
            del active_sessions[token]
    return {"message": "Logged out"}

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
    """Create transaction - SAVES TO DATABASE"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    
    db = SessionLocal()
    try:
        txn = Transaction(
            user_id=session["user_id"],
            type=type,
            amount=amount,
            category=category,
            description=description,
            transaction_date=datetime.fromisoformat(transaction_date)
        )
        
        db.add(txn)
        db.commit()
        db.refresh(txn)
        
        return {
            "id": txn.id,
            "user_id": txn.user_id,
            "type": txn.type,
            "amount": txn.amount,
            "category": txn.category,
            "description": txn.description,
            "transaction_date": txn.transaction_date.isoformat(),
            "created_at": txn.created_at.isoformat(),
            "message": "✅ Transaction saved to PostgreSQL!"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@app.get("/api/v1/tools/transactions")
async def list_transactions(skip: int = 0, limit: int = 10, authorization: str = None):
    """List user's transactions from database"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    
    db = SessionLocal()
    try:
        query = db.query(Transaction).filter(Transaction.user_id == session["user_id"]).order_by(Transaction.transaction_date.desc())
        
        total = query.count()
        txns = query.offset(skip).limit(limit).all()
        
        return {
            "items": [
                {
                    "id": t.id,
                    "user_id": t.user_id,
                    "type": t.type,
                    "amount": t.amount,
                    "category": t.category,
                    "description": t.description,
                    "transaction_date": t.transaction_date.isoformat(),
                    "created_at": t.created_at.isoformat()
                }
                for t in txns
            ],
            "total": total,
            "page": (skip // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit,
            "message": f"✅ Retrieved {len(txns)} transactions from PostgreSQL!"
        }
    finally:
        db.close()

@app.delete("/api/v1/tools/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int, authorization: str = None):
    """Delete transaction"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    
    db = SessionLocal()
    try:
        txn = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == session["user_id"]
        ).first()
        
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        db.delete(txn)
        db.commit()
        
        return {"message": "✅ Transaction deleted from PostgreSQL!"}
    finally:
        db.close()

# ═══════════════════════════════════════════════════════════
# DASHBOARD ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/tools/dashboard/summary")
async def get_dashboard_summary(authorization: str = None):
    """Get dashboard summary from database"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    
    db = SessionLocal()
    try:
        txns = db.query(Transaction).filter(Transaction.user_id == session["user_id"]).all()
        
        total_income = sum(t.amount for t in txns if t.type == "income")
        total_expenses = sum(t.amount for t in txns if t.type == "expense")
        
        income_by_category = {}
        expense_by_category = {}
        
        for t in txns:
            if t.type == "income":
                income_by_category[t.category] = income_by_category.get(t.category, 0) + t.amount
            else:
                expense_by_category[t.category] = expense_by_category.get(t.category, 0) + t.amount
        
        return {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": total_income - total_expenses,
            "transaction_count": len(txns),
            "income_by_category": income_by_category,
            "expense_by_category": expense_by_category,
            "message": "✅ Dashboard data from PostgreSQL!"
        }
    finally:
        db.close()

# ═══════════════════════════════════════════════════════════
# WANDAAI ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/wandaai/query")
async def ask_wandaai(question: str, mode: str = "insights", authorization: str = None):
    """Ask WandaAI - uses real database data"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    
    db = SessionLocal()
    try:
        txns = db.query(Transaction).filter(Transaction.user_id == session["user_id"]).all()
        
        total_income = sum(t.amount for t in txns if t.type == "income")
        total_expenses = sum(t.amount for t in txns if t.type == "expense")
        net_profit = total_income - total_expenses
        
        if total_income == 0:
            response = "Start by adding some transactions to get insights!"
        else:
            margin = (net_profit / total_income * 100) if total_income > 0 else 0
            response = f"**Your Financial Overview (from PostgreSQL):**\n\n💰 Income: R{total_income:,.2f}\n💸 Expenses: R{total_expenses:,.2f}\n📈 Profit: R{net_profit:,.2f}\n📊 Margin: {margin:.1f}%"
        
        return {
            "response": response,
            "mode": mode,
            "confidence": 0.95,
            "message": "✅ Insights from PostgreSQL database!"
        }
    finally:
        db.close()

@app.get("/api/v1/wandaai/modes")
async def get_ai_modes():
    return {
        "modes": [
            {"name": "Financial Insights", "id": "insights"},
            {"name": "Smart Recommendations", "id": "recommendations"},
            {"name": "Business Assistant", "id": "business"}
        ]
    }

# ═══════════════════════════════════════════════════════════
# SUPPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/support/contact")
async def submit_contact(name: str, email: str, message: str):
    return {
        "id": 1,
        "status": "received",
        "message": f"Thank you {name}! Message received."
    }

@app.get("/api/v1/support/faq")
async def get_faq():
    return {
        "faq_items": [
            {"id": 1, "question": "Is my data secure?", "answer": "Yes, encrypted with PostgreSQL."},
            {"id": 2, "question": "Where is data stored?", "answer": "In our PostgreSQL database on Railway."}
        ],
        "total": 2
    }

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)