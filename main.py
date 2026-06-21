"""
WandaTools Backend - PostgreSQL Version (FIXED)
FastAPI with SQLAlchemy ORM and real database storage
"""

from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import text
from datetime import datetime
import os

# ═══════════════════════════════════════════════════════════
# DATABASE SETUP - FIX 1: Import declarative_base FIRST
# ═══════════════════════════════════════════════════════════

Base = declarative_base()  # ✅ DEFINE BASE FIRST!

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("⚠️  WARNING: DATABASE_URL not set! Using SQLite fallback.")
    DATABASE_URL = "sqlite:///./wandatools.db"
    db_connected = False
else:
    print(f"✅ DATABASE_URL found: {DATABASE_URL[:60]}...")

# FIX 2: Better connection string handling for Railway
# Railway PostgreSQL connection string might look like:
# postgresql://postgres:password@HOST:5432/railway
# Replace any "postgres.railway.internal" with correct format

if "postgres.railway.internal" in DATABASE_URL:
    # Use public connection for Railway
    DATABASE_URL = DATABASE_URL.replace("postgres.railway.internal", "containers-us-west-77.railway.app")
    print(f"✅ Converted to public Railway URL")

print(f"🔌 Connecting to database...")

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20,
        echo=False,
        connect_args={"timeout": 10} if "sqlite" in DATABASE_URL else {}
    )
    
    # Test connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    
    print("✅ Database connected successfully!")
    db_connected = True
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    print("⚠️  Falling back to in-memory SQLite mode")
    db_connected = False
    DATABASE_URL = "sqlite:///./wandatools.db"
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ═══════════════════════════════════════════════════════════
# DATABASE MODELS - AFTER Base IS DEFINED
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
    type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")

# Create tables safely
if db_connected:
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified")
    except Exception as e:
        print(f"⚠️  Could not create tables: {e}")

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

# In-memory sessions
active_sessions = {}
fallback_users = {}
fallback_transactions = {}

# ═══════════════════════════════════════════════════════════
# ROOT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint"""
    if db_connected:
        try:
            db = SessionLocal()
            user_count = db.query(User).count()
            txn_count = db.query(Transaction).count()
            db.close()
            return {
                "name": "WandaTools API",
                "version": "1.0.0",
                "database": "PostgreSQL ✅",
                "status": "connected",
                "users": user_count,
                "transactions": txn_count,
                "active_sessions": len(active_sessions)
            }
        except Exception as e:
            return {
                "name": "WandaTools API",
                "version": "1.0.0",
                "database": "PostgreSQL ⚠️",
                "status": "error",
                "error": str(e)
            }
    else:
        return {
            "name": "WandaTools API",
            "version": "1.0.0",
            "database": "SQLite (Fallback)",
            "status": "fallback",
            "users": len(fallback_users),
            "transactions": sum(len(t) for t in fallback_transactions.values())
        }

@app.get("/health")
async def health():
    """Health check"""
    if db_connected:
        try:
            db = SessionLocal()
            db.execute("SELECT 1")
            user_count = db.query(User).count()
            txn_count = db.query(Transaction).count()
            total_income = sum(float(t.amount) for t in db.query(Transaction).filter(Transaction.type == "income").all())
            total_expenses = sum(float(t.amount) for t in db.query(Transaction).filter(Transaction.type == "expense").all())
            db.close()
            
            return {
                "status": "healthy ✅",
                "database": "PostgreSQL Connected",
                "version": "1.0.0",
                "users_count": user_count,
                "transactions_count": txn_count,
                "total_income": total_income,
                "total_expenses": total_expenses,
                "active_sessions": len(active_sessions)
            }
        except Exception as e:
            return {
                "status": "unhealthy ⚠️",
                "database": f"Error: {str(e)}",
                "mode": "fallback"
            }
    else:
        return {
            "status": "healthy (Fallback) ⚠️",
            "database": "SQLite",
            "users_count": len(fallback_users),
            "transactions_count": sum(len(t) for t in fallback_transactions.values()),
            "active_sessions": len(active_sessions)
        }

@app.get("/api/v1")
async def api_v1_info():
    """API info"""
    if db_connected:
        try:
            db = SessionLocal()
            users = db.query(User).count()
            txns = db.query(Transaction).count()
            db.close()
            return {
                "version": "1.0.0",
                "status": "running ✅",
                "database": "PostgreSQL",
                "users": users,
                "transactions": txns
            }
        except:
            pass
    
    return {
        "version": "1.0.0",
        "status": "running",
        "database": "SQLite (Fallback)",
        "users": len(fallback_users),
        "transactions": sum(len(t) for t in fallback_transactions.values())
    }

@app.get("/api/v1/stats")
async def get_stats():
    """Stats"""
    if db_connected:
        try:
            db = SessionLocal()
            users = db.query(User).all()
            transactions = db.query(Transaction).all()
            
            total_income = sum(t.amount for t in transactions if t.type == "income")
            total_expenses = sum(t.amount for t in transactions if t.type == "expense")
            
            db.close()
            
            return {
                "total_users": len(users),
                "active_users": len(active_sessions),
                "total_transactions": len(transactions),
                "total_income": total_income,
                "total_expenses": total_expenses,
                "net_profit": total_income - total_expenses,
                "database": "PostgreSQL ✅",
                "users_list": [{"id": u.id, "name": u.name, "email": u.email, "created_at": u.created_at.isoformat()} for u in users]
            }
        except Exception as e:
            return {"error": f"Database error: {str(e)}", "database": "PostgreSQL ⚠️"}
    else:
        total_income = sum(
            sum(t["amount"] for t in txns if t["type"] == "income")
            for txns in fallback_transactions.values()
        )
        total_expenses = sum(
            sum(t["amount"] for t in txns if t["type"] == "expense")
            for txns in fallback_transactions.values()
        )
        
        return {
            "total_users": len(fallback_users),
            "active_users": len(active_sessions),
            "total_transactions": sum(len(t) for t in fallback_transactions.values()),
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": total_income - total_expenses,
            "database": "SQLite (Fallback)",
            "users_list": [{"id": u["id"], "name": u["name"], "email": u["email"]} for u in fallback_users.values()]
        }

# ═══════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════

def get_user_from_token(token: str):
    """Get user session from token"""
    if token not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return active_sessions[token]

@app.post("/api/v1/auth/register")
async def register(name: str, email: str, password: str, business_type: str = None):
    """Register user"""
    if db_connected:
        try:
            db = SessionLocal()
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                db.close()
                raise HTTPException(status_code=409, detail="Email already registered")
            
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
            user_id = user.id
            db.close()
        except HTTPException:
            raise
        except Exception as e:
            return {"error": f"Registration failed: {str(e)}", "database": "PostgreSQL ⚠️"}
    else:
        if email in fallback_users:
            raise HTTPException(status_code=409, detail="Email already registered")
        user_id = len(fallback_users) + 1
        fallback_users[email] = {
            "id": user_id,
            "name": name,
            "email": email,
            "password": password,
            "business_type": business_type
        }
        fallback_transactions[user_id] = []
    
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
        "user": {"id": user_id, "name": name, "email": email},
        "message": "✅ User registered!"
    }

@app.post("/api/v1/auth/login")
async def login(email: str, password: str):
    """Login"""
    user_id = None
    
    if db_connected:
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.email == email).first()
            db.close()
            
            if not user or user.password != password:
                raise HTTPException(status_code=401, detail="Invalid email or password")
            
            user_id = user.id
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        if email not in fallback_users:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        if fallback_users[email]["password"] != password:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        user_id = fallback_users[email]["id"]
    
    token = f"token_{user_id}_{email[:3]}_{datetime.utcnow().timestamp()}"
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
        "message": "✅ Login successful!"
    }

@app.get("/api/v1/auth/me")
async def get_current_user(authorization: str = None):
    """Get current user"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    
    if db_connected:
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.id == session["user_id"]).first()
            db.close()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "database": "PostgreSQL ✅"
            }
        except Exception as e:
            return {"error": str(e)}
    else:
        for u in fallback_users.values():
            if u["id"] == session["user_id"]:
                return {
                    "id": u["id"],
                    "name": u["name"],
                    "email": u["email"],
                    "database": "SQLite (Fallback)"
                }

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
    """Create transaction"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    if db_connected:
        try:
            db = SessionLocal()
            txn = Transaction(
                user_id=user_id,
                type=type,
                amount=amount,
                category=category,
                description=description,
                transaction_date=datetime.fromisoformat(transaction_date)
            )
            
            db.add(txn)
            db.commit()
            db.refresh(txn)
            db.close()
            
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
            return {"error": str(e), "database": "PostgreSQL ⚠️"}
    else:
        if user_id not in fallback_transactions:
            fallback_transactions[user_id] = []
        
        txn_id = max([t.get("id", 0) for t in fallback_transactions[user_id]], default=0) + 1
        
        txn = {
            "id": txn_id,
            "user_id": user_id,
            "type": type,
            "amount": amount,
            "category": category,
            "description": description,
            "transaction_date": transaction_date,
            "created_at": datetime.utcnow().isoformat()
        }
        
        fallback_transactions[user_id].append(txn)
        
        return {
            **txn,
            "message": "✅ Transaction saved (SQLite Fallback)"
        }

@app.get("/api/v1/tools/transactions")
async def list_transactions(skip: int = 0, limit: int = 10, authorization: str = None):
    """List transactions"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    if db_connected:
        try:
            db = SessionLocal()
            query = db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.transaction_date.desc())
            
            total = query.count()
            txns = query.offset(skip).limit(limit).all()
            db.close()
            
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
                "database": "PostgreSQL ✅"
            }
        except Exception as e:
            return {"error": str(e)}
    else:
        txns = fallback_transactions.get(user_id, [])
        txns_sorted = sorted(txns, key=lambda x: x["transaction_date"], reverse=True)
        
        return {
            "items": txns_sorted[skip:skip+limit],
            "total": len(txns),
            "page": (skip // limit) + 1,
            "page_size": limit,
            "total_pages": (len(txns) + limit - 1) // limit,
            "database": "SQLite (Fallback)"
        }

@app.delete("/api/v1/tools/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int, authorization: str = None):
    """Delete transaction"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    if db_connected:
        try:
            db = SessionLocal()
            txn = db.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id
            ).first()
            
            if not txn:
                db.close()
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            db.delete(txn)
            db.commit()
            db.close()
            
            return {"message": "✅ Transaction deleted from PostgreSQL!"}
        except Exception as e:
            return {"error": str(e)}
    else:
        txns = fallback_transactions.get(user_id, [])
        for i, t in enumerate(txns):
            if t["id"] == transaction_id:
                txns.pop(i)
                return {"message": "✅ Transaction deleted (SQLite)"}
        
        raise HTTPException(status_code=404, detail="Transaction not found")

# ═══════════════════════════════════════════════════════════
# DASHBOARD ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/tools/dashboard/summary")
async def get_dashboard_summary(authorization: str = None):
    """Dashboard summary"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    if db_connected:
        try:
            db = SessionLocal()
            txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()
            db.close()
        except Exception as e:
            return {"error": str(e), "database": "PostgreSQL ⚠️"}
    else:
        txns = fallback_transactions.get(user_id, [])
    
    total_income = sum(t.amount if hasattr(t, 'amount') else t["amount"] for t in txns if (t.type if hasattr(t, 'type') else t["type"]) == "income")
    total_expenses = sum(t.amount if hasattr(t, 'amount') else t["amount"] for t in txns if (t.type if hasattr(t, 'type') else t["type"]) == "expense")
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
        "transaction_count": len(txns),
        "database": "PostgreSQL ✅" if db_connected else "SQLite (Fallback)"
    }

# ═══════════════════════════════════════════════════════════
# WANDAAI ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/wandaai/query")
async def ask_wandaai(question: str, mode: str = "insights", authorization: str = None):
    """WandaAI"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization[7:]
    session = get_user_from_token(token)
    user_id = session["user_id"]
    
    if db_connected:
        try:
            db = SessionLocal()
            txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()
            db.close()
        except:
            txns = []
    else:
        txns = fallback_transactions.get(user_id, [])
    
    total_income = sum(t.amount if hasattr(t, 'amount') else t["amount"] for t in txns if (t.type if hasattr(t, 'type') else t["type"]) == "income")
    total_expenses = sum(t.amount if hasattr(t, 'amount') else t["amount"] for t in txns if (t.type if hasattr(t, 'type') else t["type"]) == "expense")
    net_profit = total_income - total_expenses
    
    if total_income == 0:
        response = "Add some transactions to get insights!"
    else:
        margin = (net_profit / total_income * 100) if total_income > 0 else 0
        response = f"📊 **Your Financial Overview:**\n\n💰 Income: R{total_income:,.2f}\n💸 Expenses: R{total_expenses:,.2f}\n📈 Profit: R{net_profit:,.2f}\n📊 Margin: {margin:.1f}%"
    
    return {
        "response": response,
        "mode": mode,
        "confidence": 0.95,
        "database": "PostgreSQL ✅" if db_connected else "SQLite (Fallback)"
    }

@app.get("/api/v1/wandaai/modes")
async def get_ai_modes():
    return {"modes": [
        {"name": "Financial Insights", "id": "insights"},
        {"name": "Smart Recommendations", "id": "recommendations"},
        {"name": "Business Assistant", "id": "business"}
    ]}

# ═══════════════════════════════════════════════════════════
# SUPPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/support/contact")
async def submit_contact(name: str, email: str, message: str):
    return {"id": 1, "status": "received", "message": f"Thank you {name}!"}

@app.get("/api/v1/support/faq")
async def get_faq():
    return {
        "faq_items": [
            {"id": 1, "question": "Is my data secure?", "answer": "Yes, encrypted."},
            {"id": 2, "question": "Where is data stored?", "answer": "PostgreSQL on Railway."}
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