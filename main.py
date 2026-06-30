"""
WandaTools Backend — main.py
FastAPI + SQLAlchemy ORM + PostgreSQL (Railway)
Version: 2.0.0

════════════════════════════════════════════════════════════════
WHAT LIVES HERE (foundation — imported by everything else)
  ✅ Logging configuration
  ✅ Security constants + JWT/password functions
  ✅ Database engine, session, Base
  ✅ Core models: User, RefreshToken, ContactMessage
  ✅ Email helpers: send_email(), _contact_email_html(), _contact_confirm_html()
  ✅ FastAPI app + CORS middleware
  ✅ Router registration
  ✅ Root / health / stats endpoints

WHAT DOES NOT LIVE HERE (moved to dedicated files)
  ❌ Transaction, MonthlyTransactionSummary  → routes/transactions.py
  ❌ Notification, NotificationLog           → notifications.py
  ❌ Route endpoints                         → routes/*.py
  ❌ EmailService class                      → services/email.py
  ❌ Advanced security (TOTP, OTP, scoring)  → security.py

IMPORT ORDER (critical — never rearrange)
  1. Standard library + third-party packages
  2. Define Base
  3. Core models (User, RefreshToken, ContactMessage)
     — no external deps, safe to define here
  4. Import external models AFTER Base exists
     (routes/transactions.py and notifications.py both do
      `from main import Base` — this works because Base is above)
  5. Create DB tables (all models now registered on Base)
  6. Create FastAPI app
  7. Register routers LAST (routers import from main — must come after app)

FILE LOCATIONS
  main.py                  ← ROOT
  db.py                    ← ROOT
  security.py              ← ROOT
  notifications.py         ← ROOT
  config.py                ← ROOT
  requirements.txt         ← ROOT
  Procfile                 ← ROOT
  services/
    __init__.py
    email.py
  routes/
    __init__.py
    auth.py
    tools.py
    wandaai.py
    support.py
    users.py
    documents.py
    transactions.py        ← models only (Transaction, MonthlyTransactionSummary)
════════════════════════════════════════════════════════════════
"""

import os
import html
import secrets
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import FastAPI, HTTPException, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, JSON, String, Text, create_engine, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from passlib.context import CryptContext
from jose import JWTError, jwt


# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("wandatools")


# ═══════════════════════════════════════════════════════════════
# SECURITY CONFIGURATION
# Set these as Railway environment variables — never hardcode secrets.
# ═══════════════════════════════════════════════════════════════

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

_jwt_secret_raw         = os.getenv("JWT_SECRET",         "")
_jwt_refresh_secret_raw = os.getenv("JWT_REFRESH_SECRET", "")

if not _jwt_secret_raw:
    _jwt_secret_raw = secrets.token_hex(32)
    log.warning("⚠️  JWT_SECRET env var not set — using random secret. All tokens will be invalidated on restart. Set JWT_SECRET on Railway.")

if not _jwt_refresh_secret_raw:
    _jwt_refresh_secret_raw = secrets.token_hex(32)
    log.warning("⚠️  JWT_REFRESH_SECRET env var not set — using random secret. All tokens will be invalidated on restart. Set JWT_REFRESH_SECRET on Railway.")

JWT_SECRET           = _jwt_secret_raw
JWT_REFRESH_SECRET   = _jwt_refresh_secret_raw
JWT_ALGORITHM        = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "120"))  # 2 h default — PWA offline queues need breathing room
REFRESH_TOKEN_DAYS   = int(os.getenv("REFRESH_TOKEN_DAYS",   "7"))

SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",     "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "admin@wandatools.com")


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return pwd_ctx.verify(plain, hashed)


def create_access_token(user_id: int, email: str) -> str:
    """Create a short-lived JWT access token (default 30 min)."""
    payload = {
        "sub":   str(user_id),
        "email": email,
        "type":  "access",
        "exp":   datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iat":   datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int, email: str) -> str:
    """Create a long-lived JWT refresh token (default 7 days)."""
    payload = {
        "sub":   str(user_id),
        "email": email,
        "type":  "refresh",
        "exp":   datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        "iat":   datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises HTTP 401 if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Wrong token type — use your access token")
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Access token invalid or expired: {exc}")


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh token. Raises HTTP 401 if invalid."""
    try:
        payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Wrong token type — use your refresh token")
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Refresh token invalid or expired: {exc}")


# ═══════════════════════════════════════════════════════════════
# STEP 1 — DATABASE SETUP
# Base must be defined BEFORE any model class or external import.
# ═══════════════════════════════════════════════════════════════

Base = declarative_base()

SUPPORTED_CURRENCIES = {"E", "ZAR", "USD", "GBP", "EUR"}
DEFAULT_CURRENCY     = "E"    # Emalangeni — Eswatini

DATABASE_URL = os.getenv("DATABASE_URL", "")

# SQLAlchemy requires "postgresql://" not legacy "postgres://" prefix
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Mask credentials in log output
_db_log_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
log.info(f"🔌 Connecting to DB host: {_db_log_url[:60]}...")

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,           # drop stale connections automatically
        pool_recycle=3600,            # recycle connections every 1 hour
        pool_size=10,
        max_overflow=20,
        connect_args={"connect_timeout": 10},
        echo=False,
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    db_connected = True
    log.info("✅ PostgreSQL connected!")

except Exception as exc:
    log.error(f"❌ PostgreSQL failed: {exc}")
    log.warning("⚠️  Falling back to SQLite for local development")
    db_connected = False
    DATABASE_URL = "sqlite:///./wandatools_dev.db"
    engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ═══════════════════════════════════════════════════════════════
# STEP 2 — CORE MODELS
# Only models with NO external file dependencies live here.
# Other files import Base from here — keep these self-contained.
# ═══════════════════════════════════════════════════════════════

class User(Base):
    """
    Core user account model.
    Relationships reference models defined in other files —
    SQLAlchemy resolves them by string name at runtime.
    """
    __tablename__ = "users"

    id            = Column(Integer,     primary_key=True, index=True)
    name          = Column(String(255), nullable=False)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password      = Column(String(255), nullable=False)      # bcrypt hash
    business_type = Column(String(100), nullable=True)
    timezone      = Column(String(50),  default="Africa/Johannesburg")
    currency      = Column(String(10),  default=DEFAULT_CURRENCY)
    created_at    = Column(DateTime,    default=datetime.utcnow)

    # Relationships — resolved by string name, safe to declare before the models exist
    refresh_tokens    = relationship("RefreshToken",              back_populates="user", cascade="all, delete-orphan")
    transactions      = relationship("Transaction",               back_populates="user", cascade="all, delete-orphan")
    monthly_summaries = relationship("MonthlyTransactionSummary", back_populates="user", cascade="all, delete-orphan")
    notifications     = relationship("Notification",              back_populates="user", cascade="all, delete-orphan")
    notification_logs = relationship("NotificationLog",           back_populates="user", cascade="all, delete-orphan")
    push_subscriptions = relationship("PushSubscription",         back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    """Stores active refresh tokens for server-side session revocation."""
    __tablename__ = "refresh_tokens"

    id         = Column(Integer,     primary_key=True, index=True)
    user_id    = Column(Integer,     ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token      = Column(String(512), unique=True, nullable=False, index=True)
    revoked    = Column(Boolean,     default=False, nullable=False)
    created_at = Column(DateTime,    default=datetime.utcnow)
    expires_at = Column(DateTime,    nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class ContactMessage(Base):
    """Stores every support contact form submission and feedback entry."""
    __tablename__ = "contact_messages"

    id         = Column(Integer,      primary_key=True, index=True)
    name       = Column(String(255),  nullable=False)
    email      = Column(String(255),  nullable=False)
    subject    = Column(String(255),  nullable=True)
    message    = Column(String(2000), nullable=False)
    created_at = Column(DateTime,     default=datetime.utcnow)


class PushSubscription(Base):
    """Web Push API subscription — one row per browser/device per user."""
    __tablename__ = "push_subscriptions"

    id         = Column(Integer,      primary_key=True, index=True)
    user_id    = Column(Integer,      ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    endpoint   = Column(String(2000), nullable=False, unique=True)
    p256dh     = Column(String(500),  nullable=False)   # browser public key
    auth       = Column(String(200),  nullable=False)   # browser auth secret
    user_agent = Column(String(500),  nullable=True)
    created_at = Column(DateTime,     default=datetime.utcnow)
    last_used  = Column(DateTime,     nullable=True)

    user = relationship("User", back_populates="push_subscriptions")


class PwaEvent(Base):
    """
    Single row for every logged PWA / service-worker lifecycle event.
    user_id is nullable — SW events (install, activate) fire before login.
    """
    __tablename__ = "pwa_events"

    id         = Column(Integer,     primary_key=True, index=True)
    user_id    = Column(Integer,     ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    event_type = Column(String(50),  nullable=False, index=True)
    data       = Column(JSON,        nullable=True)
    ip_address = Column(String(45),  nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime,    default=datetime.utcnow, nullable=False, index=True)


# ═══════════════════════════════════════════════════════════════
# STEP 3 — IMPORT EXTERNAL MODELS
# These files do `from main import Base` — safe NOW because Base exists above.
# NEVER move these imports above the Base definition.
# ═══════════════════════════════════════════════════════════════

from routes.transactions import Transaction, MonthlyTransactionSummary   # noqa: E402
from notifications       import Notification, NotificationLog             # noqa: E402


# ═══════════════════════════════════════════════════════════════
# STEP 4 — CREATE ALL TABLES
# All models (local + imported) are now registered on Base.metadata.
# create_all() is safe to call on every startup — skips existing tables.
# ═══════════════════════════════════════════════════════════════

try:
    Base.metadata.create_all(bind=engine)
    log.info("✅ All database tables created / verified")
except Exception as exc:
    log.error(f"⚠️  Could not create tables: {exc}")


# ═══════════════════════════════════════════════════════════════
# EMAIL HELPERS
# Low-level send function + HTML templates.
# Imported by services/email.py and routes/support.py.
# ═══════════════════════════════════════════════════════════════

def send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Send an HTML email via SMTP.
    Returns True on success, False on failure — never raises.
    Requires SMTP_USER + SMTP_PASSWORD Railway env vars.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        log.warning("⚠️  SMTP credentials not set — email not sent")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = to
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to, msg.as_string())

        log.info(f"📧 Email sent → {to}: {subject}")
        return True

    except smtplib.SMTPAuthenticationError:
        log.error("❌ SMTP auth failed — check SMTP_USER / SMTP_PASSWORD")
        return False
    except smtplib.SMTPConnectError:
        log.error(f"❌ SMTP connect failed — check SMTP_HOST ({SMTP_HOST}) / SMTP_PORT ({SMTP_PORT})")
        return False
    except Exception as exc:
        log.error(f"❌ Email error: {exc}")
        return False


def _contact_email_html(name: str, sender_email: str, subject: str, message: str) -> str:
    """HTML template for contact form notification sent to the support team."""
    safe_name    = html.escape(name)
    safe_email   = html.escape(sender_email)
    safe_subject = html.escape(subject or "—")
    safe_message = html.escape(message)
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;padding:24px">
      <h2 style="color:#007BFF">📬 New WandaTools Support Request</h2>
      <table style="border-collapse:collapse;width:100%;max-width:600px">
        <tr><td style="padding:8px;font-weight:bold;width:100px">Name</td>
            <td style="padding:8px">{safe_name}</td></tr>
        <tr style="background:#f5f5f5">
            <td style="padding:8px;font-weight:bold">Email</td>
            <td style="padding:8px">{safe_email}</td></tr>
        <tr><td style="padding:8px;font-weight:bold">Subject</td>
            <td style="padding:8px">{safe_subject}</td></tr>
        <tr style="background:#f5f5f5">
            <td style="padding:8px;font-weight:bold;vertical-align:top">Message</td>
            <td style="padding:8px;white-space:pre-wrap">{safe_message}</td></tr>
      </table>
      <p style="margin-top:24px;color:#888;font-size:12px">Sent from WandaTools contact form</p>
    </body></html>
    """


def _contact_confirm_html(name: str) -> str:
    """HTML template for the confirmation email sent back to the user."""
    safe_name = html.escape(name)
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;padding:24px">
      <h2 style="color:#28A745">✅ We received your message, {safe_name}!</h2>
      <p>Thank you for reaching out to <strong>WandaTools</strong>.</p>
      <p>Our support team will reply within <strong>24–48 hours</strong>.</p>
      <p style="margin-top:24px">— The WandaTools Team 🇸🇿</p>
      <p style="color:#888;font-size:12px">admin@wandatools.com</p>
    </body></html>
    """


# ═══════════════════════════════════════════════════════════════
# STEP 5 — FASTAPI APP
# Created AFTER models and helpers are ready.
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="WandaTools API",
    description="AI-powered financial insights for Eswatini small businesses",
    version="2.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://wandatools.vercel.app,http://localhost:3000,http://localhost:5500"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
# SECURITY HEADERS MIDDLEWARE
# Applied to every response. Enforces HTTPS, prevents clickjacking,
# and sets a strict CSP appropriate for a pure API server.
# ═══════════════════════════════════════════════════════════════

_ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()

# Paths whose responses may be cached by the browser (public or private)
_CACHE_RULES: list[tuple[str, str]] = [
    ("/api/v1/pwa/manifest",     "public, max-age=3600, stale-while-revalidate=86400"),
    ("/api/v1/pwa/offline-data", "private, max-age=300, stale-while-revalidate=600"),
    ("/health",                  "no-cache"),
    ("/",                        "public, max-age=60"),
]
# Everything else gets: private, no-store (no sensitive data leaks)
_DEFAULT_CACHE = "private, no-store"


@app.middleware("http")
async def security_and_cache_middleware(request: Request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"]        = "DENY"
    response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]     = (
        "camera=(), microphone=(), geolocation=(self), payment=()"
    )
    # API-only CSP — no scripts/styles served from this origin
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none';"
    )
    if _ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    # Cache-Control (only set if the route handler hasn't already set one)
    if "cache-control" not in response.headers:
        path = request.url.path
        cache_value = _DEFAULT_CACHE
        for prefix, rule in _CACHE_RULES:
            if path.startswith(prefix):
                cache_value = rule
                break
        response.headers["Cache-Control"] = cache_value

    return response


# ═══════════════════════════════════════════════════════════════
# SHARED HELPER — extract user_id from Authorization header
# Used in root/health/stats. Route files use get_current_user
# from routes/auth.py which returns the full User object.
# ═══════════════════════════════════════════════════════════════

def get_current_user_id(authorization: str = Header(default=None)) -> int:
    """Return the integer user_id from the Bearer token, or raise 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing. Format: 'Bearer <access_token>'"
        )
    token   = authorization[7:]
    payload = decode_access_token(token)
    return int(payload["sub"])


# ═══════════════════════════════════════════════════════════════
# STEP 6 — REGISTER ROUTERS
# Must come AFTER app is created and AFTER all models are imported.
# Route files import from main.py — they must load after main is ready.
# ═══════════════════════════════════════════════════════════════

from routes.auth      import router as auth_router      # noqa: E402
from routes.tools     import router as tools_router     # noqa: E402
from routes.wandaai   import router as wandaai_router   # noqa: E402
from routes.support   import router as support_router   # noqa: E402
from routes.users     import router as users_router     # noqa: E402
from routes.documents import router as documents_router # noqa: E402
from routes.export    import router as export_router    # noqa: E402
from routes.pwa       import router as pwa_router       # noqa: E402

app.include_router(auth_router)
app.include_router(tools_router)
app.include_router(wandaai_router)
app.include_router(support_router)
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(export_router)
app.include_router(pwa_router)

# routes/transactions.py contains models only (no router).
# Uncomment below if you later add transaction-specific endpoints there:
# from routes.transactions import router as transactions_router
# app.include_router(transactions_router)


# ═══════════════════════════════════════════════════════════════
# ROOT / HEALTH / STATS ENDPOINTS
# Kept in main.py — these don't belong to any specific feature domain.
# ═══════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """API root — returns version, DB status, and record counts."""
    db = SessionLocal()
    try:
        return {
            "name":         "WandaTools API",
            "version":      "2.0.0",
            "database":     "PostgreSQL ✅" if db_connected else "SQLite (fallback)",
            "status":       "online",
            "users":        db.query(User).count(),
            "transactions": db.query(Transaction).count(),
        }
    except Exception as exc:
        log.error(f"root error: {exc}")
        return {"name": "WandaTools API", "status": "error", "detail": str(exc)}
    finally:
        db.close()


@app.get("/health")
async def health():
    """Health check — used by Railway and uptime monitors."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {
            "status":                "healthy ✅",
            "database":              "PostgreSQL" if db_connected else "SQLite",
            "version":               "2.0.0",
            "users_count":           db.query(User).count(),
            "transactions_count":    db.query(Transaction).count(),
            "active_refresh_tokens": db.query(RefreshToken).filter_by(revoked=False).count(),
        }
    except Exception as exc:
        log.error(f"health check error: {exc}")
        return {"status": "unhealthy ⚠️", "detail": str(exc)}
    finally:
        db.close()


@app.get("/test-push")
async def test_push():
    """Public smoke-test — confirms the service is reachable on Railway."""
    return {"detail": "push working"}


@app.get("/api/v1")
async def api_info():
    """API version info."""
    db = SessionLocal()
    try:
        return {
            "version":      "2.0.0",
            "status":       "running ✅",
            "database":     "PostgreSQL" if db_connected else "SQLite",
            "users":        db.query(User).count(),
            "transactions": db.query(Transaction).count(),
        }
    finally:
        db.close()


@app.get("/api/v1/stats")
async def get_stats(authorization: str = Header(default=None)):
    """Admin stats — total users, transactions, income, expenses, net profit. Requires auth."""
    get_current_user_id(authorization)
    db = SessionLocal()
    try:
        from routes.transactions import TransactionType   # noqa: E402
        users = db.query(User).all()
        txns  = db.query(Transaction).filter(Transaction.is_deleted == False).all()   # noqa: E712

        total_income   = sum(t.amount for t in txns if t.type == TransactionType.INCOME)
        total_expenses = sum(t.amount for t in txns if t.type == TransactionType.EXPENSE)

        return {
            "total_users":        len(users),
            "total_transactions": len(txns),
            "total_income":       total_income,
            "total_expenses":     total_expenses,
            "net_profit":         total_income - total_expenses,
            "database":           "PostgreSQL ✅" if db_connected else "SQLite",
            "users_list": [
                {
                    "id":         u.id,
                    "name":       u.name,
                    "email":      u.email,
                    "currency":   u.currency,
                    "created_at": u.created_at.isoformat(),
                }
                for u in users
            ],
        }
    except Exception as exc:
        log.error(f"stats error: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not load stats: {exc}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)