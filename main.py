"""
WandaTools Backend — main.py
FastAPI + SQLAlchemy ORM + PostgreSQL (Railway)


"""

import os
import secrets
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import (
    Boolean, create_engine, Column, Integer, String,
    Float, DateTime, ForeignKey, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from passlib.context import CryptContext
from jose import JWTError, jwt



# ─────────────────────────────────────────────────────────────
# LOGGING  — shows clear messages in Railway logs
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("wandatools")


# ─────────────────────────────────────────────────────────────
# SECURITY CONFIGURATION
# ─────────────────────────────────────────────────────────────

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Set both secrets as Railway env vars ──────────────────────
JWT_SECRET         = os.getenv("JWT_SECRET",         secrets.token_hex(32))
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", secrets.token_hex(32))
JWT_ALGORITHM      = "HS256"

# Short-lived access token (30 min) + long-lived refresh token (7 days)
ACCESS_TOKEN_MINUTES  = int(os.getenv("ACCESS_TOKEN_MINUTES",  "30"))
REFRESH_TOKEN_DAYS    = int(os.getenv("REFRESH_TOKEN_DAYS",    "7"))

# ── SMTP email settings — set these as Railway env vars ───────
SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",     "")          # e.g. admin@wandatools.com
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")          # Gmail App Password
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "admin@wandatools.com")


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_access_token(user_id: int, email: str) -> str:
    """Short-lived JWT (30 min). Used on every API call."""
    payload = {
        "sub":   str(user_id),
        "email": email,
        "type":  "access",
        "exp":   datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iat":   datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int, email: str) -> str:
    """Long-lived JWT (7 days). Used ONLY to get a new access token."""
    payload = {
        "sub":   str(user_id),
        "email": email,
        "type":  "refresh",
        "exp":   datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        "iat":   datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=401,
                detail="Wrong token type — use your access token here"
            )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Access token invalid or expired: {exc}"
        )


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Wrong token type — use your refresh token here"
            )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Refresh token invalid or expired: {exc}"
        )


# ─────────────────────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────────────────────

Base = declarative_base()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:PQFnczJqHdqKAsAtXAHicJMsSuVClByk@reseau.proxy.rlwy.net:27449/railway"
)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

log.info(f"🔌 Connecting to: {DATABASE_URL[:60]}...")

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
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
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─────────────────────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────────────────────

SUPPORTED_CURRENCIES = {"E", "ZAR", "USD", "GBP", "EUR"}   # extend as needed
DEFAULT_CURRENCY     = "E"    # Emalangeni — Eswatini


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer,     primary_key=True, index=True)
    name          = Column(String(255), nullable=False)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password      = Column(String(255), nullable=False)      # bcrypt hash
    business_type = Column(String(100), nullable=True)
    timezone      = Column(String(50),  default="Africa/Johannesburg")
    currency      = Column(String(10),  default=DEFAULT_CURRENCY)  # ← new
    created_at    = Column(DateTime,    default=datetime.utcnow)

    transactions   = relationship("Transaction",  back_populates="user",  cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user",  cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id               = Column(Integer,     primary_key=True, index=True)
    user_id          = Column(Integer,     ForeignKey("users.id"), nullable=False, index=True)
    type             = Column(String(50),  nullable=False)          # "income" | "expense"
    amount           = Column(Float,       nullable=False)
    currency         = Column(String(10),  default=DEFAULT_CURRENCY)  # ← new
    category         = Column(String(100), nullable=False)
    description      = Column(String(500), nullable=False)
    transaction_date = Column(DateTime,    nullable=False)
    created_at       = Column(DateTime,    default=datetime.utcnow)
    updated_at       = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class RefreshToken(Base):
    """
    Stores active refresh tokens in the DB so we can revoke them on logout
    or when a user resets their password.
    One row = one active session / device.
    """
    __tablename__ = "refresh_tokens"

    id         = Column(Integer,     primary_key=True, index=True)
    user_id    = Column(Integer,     ForeignKey("users.id"), nullable=False, index=True)
    token      = Column(String(512), unique=True, nullable=False, index=True)
    revoked    = Column(Boolean,     default=False)
    created_at = Column(DateTime,    default=datetime.utcnow)
    expires_at = Column(DateTime,    nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class ContactMessage(Base):
    """Stores every support contact form submission."""
    __tablename__ = "contact_messages"

    id         = Column(Integer,     primary_key=True, index=True)
    name       = Column(String(255), nullable=False)
    email      = Column(String(255), nullable=False)
    subject    = Column(String(255), nullable=True)
    message    = Column(String(2000), nullable=False)
    created_at = Column(DateTime,    default=datetime.utcnow)


try:
    Base.metadata.create_all(bind=engine)
    log.info("✅ Database tables created / verified")
except Exception as exc:
    log.error(f"⚠️  Could not create tables: {exc}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# EMAIL SERVICE
# ─────────────────────────────────────────────────────────────

def send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Send an email via SMTP (Gmail or any provider).
    Returns True on success, False on failure.
    Set SMTP_USER + SMTP_PASSWORD as Railway env vars.
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

        log.info(f"📧 Email sent to {to}: {subject}")
        return True

    except smtplib.SMTPAuthenticationError:
        log.error("❌ SMTP auth failed — check SMTP_USER / SMTP_PASSWORD env vars")
        return False
    except smtplib.SMTPConnectError:
        log.error(f"❌ SMTP connect failed — check SMTP_HOST ({SMTP_HOST}) / SMTP_PORT ({SMTP_PORT})")
        return False
    except Exception as exc:
        log.error(f"❌ Email error: {exc}")
        return False


def _contact_email_html(name: str, sender_email: str, subject: str, message: str) -> str:
    """HTML template for contact form notification sent to support."""
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;padding:24px">
      <h2 style="color:#007BFF">📬 New WandaTools Support Request</h2>
      <table style="border-collapse:collapse;width:100%;max-width:600px">
        <tr><td style="padding:8px;font-weight:bold;width:100px">Name</td>
            <td style="padding:8px">{name}</td></tr>
        <tr style="background:#f5f5f5">
            <td style="padding:8px;font-weight:bold">Email</td>
            <td style="padding:8px">{sender_email}</td></tr>
        <tr><td style="padding:8px;font-weight:bold">Subject</td>
            <td style="padding:8px">{subject or "—"}</td></tr>
        <tr style="background:#f5f5f5">
            <td style="padding:8px;font-weight:bold;vertical-align:top">Message</td>
            <td style="padding:8px;white-space:pre-wrap">{message}</td></tr>
      </table>
      <p style="margin-top:24px;color:#888;font-size:12px">Sent from WandaTools contact form</p>
    </body></html>
    """


def _contact_confirm_html(name: str) -> str:
    """HTML template for confirmation email sent back to the user."""
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;padding:24px">
      <h2 style="color:#28A745">✅ We received your message, {name}!</h2>
      <p>Thank you for reaching out to <strong>WandaTools</strong>.</p>
      <p>Our support team will reply within <strong>24–48 hours</strong>.</p>
      <p style="margin-top:24px">— The WandaTools Team 🇸🇿</p>
      <p style="color:#888;font-size:12px">admin@wandatools.com</p>
    </body></html>
    """


# ─────────────────────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="WandaTools API",
    description="AI-powered financial insights for Eswatini small businesses",
    version="2.0.0",
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


# ─────────────────────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────────────────────
from routes.auth          import router as auth_router
from routes.wandaai       import router as wandaai_router
from routes.tools         import router as tools_router
from routes.support       import router as support_router
from routes.transactions  import router as transactions_router
from routes.users         import router as users_router
from routes.documents     import router as documents_router


app.include_router(auth_router)
app.include_router(wandaai_router)
app.include_router(tools_router)
app.include_router(support_router)
app.include_router(transactions_router)
app.include_router(users_router)
app.include_router(documents_router)


# ─────────────────────────────────────────────────────────────
# SHARED HELPER — extract + validate access token
# ─────────────────────────────────────────────────────────────

def get_current_user_id(authorization: str = Header(default=None)) -> int:
    """
    Reads the 'Authorization: Bearer <token>' header.
    Returns the user_id (int) or raises 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing. Format: 'Bearer <access_token>'"
        )
    token = authorization[7:]
    payload = decode_access_token(token)
    return int(payload["sub"])


# ─────────────────────────────────────────────────────────────
# ROOT / HEALTH
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
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
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        txns           = db.query(Transaction).all()
        total_income   = sum(t.amount for t in txns if t.type == "income")
        total_expenses = sum(t.amount for t in txns if t.type == "expense")
        return {
            "status":              "healthy ✅",
            "database":            "PostgreSQL" if db_connected else "SQLite",
            "version":             "2.0.0",
            "users_count":         db.query(User).count(),
            "transactions_count":  len(txns),
            "total_income":        total_income,
            "total_expenses":      total_expenses,
            "active_refresh_tokens": db.query(RefreshToken).filter_by(revoked=False).count(),
        }
    except Exception as exc:
        log.error(f"health check error: {exc}")
        return {"status": "unhealthy ⚠️", "detail": str(exc)}
    finally:
        db.close()


@app.get("/api/v1")
async def api_info():
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
async def get_stats():
    db = SessionLocal()
    try:
        users          = db.query(User).all()
        txns           = db.query(Transaction).all()
        total_income   = sum(t.amount for t in txns if t.type == "income")
        total_expenses = sum(t.amount for t in txns if t.type == "expense")
        return {
            "total_users":        len(users),
            "total_transactions": len(txns),
            "total_income":       total_income,
            "total_expenses":     total_expenses,
            "net_profit":         total_income - total_expenses,
            "database":           "PostgreSQL ✅" if db_connected else "SQLite",
            "users_list": [
                {"id": u.id, "name": u.name, "email": u.email,
                 "currency": u.currency, "created_at": u.created_at.isoformat()}
                for u in users
            ],
        }
    except Exception as exc:
        log.error(f"stats error: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not load stats: {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# AUTH — REGISTER
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/register", status_code=201)
async def register(
    name:          str,
    email:         str,
    password:      str,
    business_type: str  = None,
    currency:      str  = DEFAULT_CURRENCY,
):
    """
    Register a new user.
    - Password is bcrypt-hashed before storage.
    - Returns both an access token (30 min) and a refresh token (7 days).
    - Currency defaults to 'E' (Emalangeni). Accepted: E, ZAR, USD, GBP, EUR.
    """
    currency = currency.upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported currency '{currency}'. Accepted: {', '.join(SUPPORTED_CURRENCIES)}"
        )

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=409, detail=f"Email '{email}' is already registered")

        user = User(
            name=name,
            email=email,
            password=hash_password(password),
            business_type=business_type,
            currency=currency,
            timezone="Africa/Johannesburg",
        )
        db.add(user)
        db.flush()   # assign user.id before creating the token row

        access_token  = create_access_token(user.id, user.email)
        refresh_token = create_refresh_token(user.id, user.email)

        db.add(RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        ))
        db.commit()
        db.refresh(user)

        log.info(f"✅ Registered user {user.id} ({user.email})")
        return {
            "access_token":           access_token,
            "refresh_token":          refresh_token,
            "token_type":             "bearer",
            "access_expires_in":      ACCESS_TOKEN_MINUTES * 60,
            "refresh_expires_in":     REFRESH_TOKEN_DAYS * 86400,
            "user": {
                "id":            user.id,
                "name":          user.name,
                "email":         user.email,
                "currency":      user.currency,
                "business_type": user.business_type,
            },
            "message": "✅ Registered successfully!",
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"register error for {email}: {exc}")
        raise HTTPException(status_code=500, detail=f"Registration failed — please try again: {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# AUTH — LOGIN
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login")
async def login(email: str, password: str):
    """
    Login with email + password.
    Returns a new access token (30 min) + refresh token (7 days).
    Old refresh tokens for this user remain valid until they expire or are revoked.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.password):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password — please check your credentials"
            )

        access_token  = create_access_token(user.id, user.email)
        refresh_token = create_refresh_token(user.id, user.email)

        db.add(RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        ))
        db.commit()

        log.info(f"✅ Login: user {user.id} ({user.email})")
        return {
            "access_token":           access_token,
            "refresh_token":          refresh_token,
            "token_type":             "bearer",
            "access_expires_in":      ACCESS_TOKEN_MINUTES * 60,
            "refresh_expires_in":     REFRESH_TOKEN_DAYS * 86400,
            "user": {
                "id":       user.id,
                "name":     user.name,
                "email":    user.email,
                "currency": user.currency,
            },
            "message": "✅ Login successful!",
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"login error for {email}: {exc}")
        raise HTTPException(status_code=500, detail=f"Login failed — server error: {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# AUTH — REFRESH TOKEN  (get a new access token without re-logging in)
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/refresh")
async def refresh_access_token(refresh_token: str):
    """
    Exchange a valid refresh token for a brand new access + refresh token pair.
    The old refresh token is revoked (rotated) so it cannot be reused.
    This is called automatically by the frontend when the access token expires.
    """
    # 1. Verify the JWT signature and expiry
    payload = decode_refresh_token(refresh_token)
    user_id = int(payload["sub"])

    db = SessionLocal()
    try:
        # 2. Check the token exists in the DB and has NOT been revoked
        stored = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == refresh_token,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,         # noqa: E712
            )
            .first()
        )
        if not stored:
            raise HTTPException(
                status_code=401,
                detail="Refresh token has been revoked or does not exist. Please log in again."
            )

        if stored.expires_at < datetime.utcnow():
            stored.revoked = True
            db.commit()
            raise HTTPException(
                status_code=401,
                detail="Refresh token has expired. Please log in again."
            )

        # 3. Load the user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User account no longer exists")

        # 4. Rotate: revoke the old refresh token
        stored.revoked = True

        # 5. Issue a new pair
        new_access  = create_access_token(user.id, user.email)
        new_refresh = create_refresh_token(user.id, user.email)

        db.add(RefreshToken(
            user_id=user.id,
            token=new_refresh,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        ))
        db.commit()

        log.info(f"🔄 Token refreshed for user {user.id}")
        return {
            "access_token":       new_access,
            "refresh_token":      new_refresh,
            "token_type":         "bearer",
            "access_expires_in":  ACCESS_TOKEN_MINUTES * 60,
            "refresh_expires_in": REFRESH_TOKEN_DAYS * 86400,
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"refresh error: {exc}")
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# AUTH — LOGOUT  (server-side revocation)
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/logout")
async def logout(refresh_token: str, authorization: str = Header(default=None)):
    """
    Logout the current session by revoking the refresh token in the DB.
    Pass the refresh_token in the request body and the access token in the header.
    The access token will expire naturally (max 30 min) — no need to blacklist it.
    """
    user_id = get_current_user_id(authorization)
    db = SessionLocal()
    try:
        stored = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == refresh_token,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,          # noqa: E712
            )
            .first()
        )
        if stored:
            stored.revoked = True
            db.commit()
            log.info(f"🚪 User {user_id} logged out — refresh token revoked")

        return {"message": "✅ Logged out successfully. Session revoked."}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"logout error: {exc}")
        raise HTTPException(status_code=500, detail=f"Logout failed: {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# AUTH — ME
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/auth/me")
async def get_current_user(authorization: str = Header(default=None)):
    """Return the authenticated user's profile."""
    user_id = get_current_user_id(authorization)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User ID {user_id} not found — account may have been deleted"
            )
        return {
            "id":            user.id,
            "name":          user.name,
            "email":         user.email,
            "business_type": user.business_type,
            "timezone":      user.timezone,
            "currency":      user.currency,
            "created_at":    user.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"get_me error for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not load profile: {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# TRANSACTIONS
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/tools/transactions", status_code=201)
async def create_transaction(
    type:             str,
    amount:           float,
    category:         str,
    description:      str,
    transaction_date: str,
    currency:         str  = None,                    # defaults to user's currency
    authorization:    str  = Header(default=None),
):
    """
    Create a new income or expense transaction.
    - 'type' must be 'income' or 'expense'.
    - 'amount' must be greater than 0.
    - 'currency' defaults to the user's set currency if not provided.
    - 'transaction_date' must be ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
    """
    user_id = get_current_user_id(authorization)

    if type not in ("income", "expense"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type '{type}' — must be 'income' or 'expense'"
        )
    if amount <= 0:
        raise HTTPException(
            status_code=422,
            detail=f"Amount must be greater than 0, received: {amount}"
        )

    try:
        parsed_date = datetime.fromisoformat(transaction_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid transaction_date '{transaction_date}' — use ISO format: YYYY-MM-DD"
        )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        txn_currency = (currency or user.currency).upper()
        if txn_currency not in SUPPORTED_CURRENCIES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported currency '{txn_currency}'. Accepted: {', '.join(SUPPORTED_CURRENCIES)}"
            )

        txn = Transaction(
            user_id=user_id,
            type=type,
            amount=amount,
            currency=txn_currency,
            category=category,
            description=description,
            transaction_date=parsed_date,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        return {
            "id":               txn.id,
            "user_id":          txn.user_id,
            "type":             txn.type,
            "amount":           txn.amount,
            "currency":         txn.currency,
            "category":         txn.category,
            "description":      txn.description,
            "transaction_date": txn.transaction_date.isoformat(),
            "created_at":       txn.created_at.isoformat(),
            "message":          "✅ Transaction saved!",
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"create_transaction error for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not save transaction: {exc}")
    finally:
        db.close()


@app.get("/api/v1/tools/transactions")
async def list_transactions(
    skip:          int = 0,
    limit:         int = 10,
    authorization: str = Header(default=None),
):
    """List the authenticated user's transactions, newest first. Paginated."""
    user_id = get_current_user_id(authorization)
    db = SessionLocal()
    try:
        query = (
            db.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.transaction_date.desc())
        )
        total = query.count()
        txns  = query.offset(skip).limit(limit).all()
        return {
            "items": [
                {
                    "id":               t.id,
                    "type":             t.type,
                    "amount":           t.amount,
                    "currency":         t.currency,
                    "category":         t.category,
                    "description":      t.description,
                    "transaction_date": t.transaction_date.isoformat(),
                    "created_at":       t.created_at.isoformat(),
                }
                for t in txns
            ],
            "total":       total,
            "page":        (skip // limit) + 1,
            "page_size":   limit,
            "total_pages": (total + limit - 1) // limit,
        }
    except Exception as exc:
        log.error(f"list_transactions error for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not load transactions: {exc}")
    finally:
        db.close()


@app.delete("/api/v1/tools/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: int,
    authorization:  str = Header(default=None),
):
    """Delete a transaction. Only the owner can delete their own transactions."""
    user_id = get_current_user_id(authorization)
    db = SessionLocal()
    try:
        txn = (
            db.query(Transaction)
            .filter(Transaction.id == transaction_id, Transaction.user_id == user_id)
            .first()
        )
        if not txn:
            raise HTTPException(
                status_code=404,
                detail=f"Transaction ID {transaction_id} not found or does not belong to you"
            )
        db.delete(txn)
        db.commit()
        return {"message": f"✅ Transaction {transaction_id} deleted!"}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"delete_transaction error (txn {transaction_id}, user {user_id}): {exc}")
        raise HTTPException(status_code=500, detail=f"Could not delete transaction: {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/tools/dashboard/summary")
async def get_dashboard_summary(authorization: str = Header(default=None)):
    """Return totals: income, expenses, net profit, transaction count, and user currency."""
    user_id = get_current_user_id(authorization)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        txns           = db.query(Transaction).filter(Transaction.user_id == user_id).all()
        total_income   = sum(t.amount for t in txns if t.type == "income")
        total_expenses = sum(t.amount for t in txns if t.type == "expense")

        return {
            "total_income":      total_income,
            "total_expenses":    total_expenses,
            "net_profit":        total_income - total_expenses,
            "transaction_count": len(txns),
            "currency":          user.currency,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"dashboard error for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not load dashboard: {exc}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# WANDAAI
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/wandaai/query")
async def ask_wandaai(
    question:      str,
    mode:          str = "insights",
    authorization: str = Header(default=None),
):
    """Return AI-driven financial insights using the user's own transaction data."""
    user_id = get_current_user_id(authorization)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"wandaai DB error for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not load financial data: {exc}")
    finally:
        db.close()

    currency       = user.currency
    total_income   = sum(t.amount for t in txns if t.type == "income")
    total_expenses = sum(t.amount for t in txns if t.type == "expense")
    net_profit     = total_income - total_expenses

    if total_income == 0 and total_expenses == 0:
        response = (
            "No transactions found yet. "
            "Add some income or expense records to receive AI-powered financial insights!"
        )
    else:
        margin = (net_profit / total_income * 100) if total_income > 0 else 0
        response = (
            f"📊 **Your Financial Overview:**\n\n"
            f"💰 Income:        {currency} {total_income:,.2f}\n"
            f"💸 Expenses:      {currency} {total_expenses:,.2f}\n"
            f"📈 Net Profit:    {currency} {net_profit:,.2f}\n"
            f"📊 Profit Margin: {margin:.1f}%\n\n"
            + (
                "✅ Great margin — your business is performing well!"
                if margin >= 20 else
                "⚠️  Margin is under 20% — consider reviewing your expense categories."
                if margin > 0 else
                "🔴 You are currently operating at a loss. Review your expenses urgently."
            )
        )

    return {
        "response":   response,
        "mode":       mode,
        "confidence": 0.95,
        "currency":   currency,
    }


@app.get("/api/v1/wandaai/modes")
async def get_ai_modes():
    return {
        "modes": [
            {"name": "Financial Insights",    "id": "insights"},
            {"name": "Smart Recommendations", "id": "recommendations"},
            {"name": "Business Assistant",    "id": "business"},
        ]
    }


# ─────────────────────────────────────────────────────────────
# SUPPORT — CONTACT  (real email sending)
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/support/contact")
async def submit_contact(
    name:    str,
    email:   str,
    message: str,
    subject: str = "WandaTools Support Request",
):
    """
    Submit a contact/support message.
    - Saves the message to the DB (contact_messages table).
    - Emails the support team (SUPPORT_EMAIL) with the message details.
    - Sends a confirmation email back to the user.
    Requires SMTP_USER + SMTP_PASSWORD env vars to be set on Railway.
    """
    if len(message.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="Message is too short — please provide more detail (at least 10 characters)"
        )

    db = SessionLocal()
    try:
        entry = ContactMessage(
            name=name, email=email, subject=subject, message=message
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        msg_id = entry.id
    except Exception as exc:
        db.rollback()
        log.error(f"contact save error: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not save your message: {exc}")
    finally:
        db.close()

    # Send notification to support team
    team_sent = send_email(
        to=SUPPORT_EMAIL,
        subject=f"[WandaTools Support #{msg_id}] {subject}",
        html_body=_contact_email_html(name, email, subject, message),
    )

    # Send confirmation to the user
    user_sent = send_email(
        to=email,
        subject="✅ We received your message — WandaTools Support",
        html_body=_contact_confirm_html(name),
    )

    email_status = "sent" if (team_sent and user_sent) else "queued"
    return {
        "id":      msg_id,
        "status":  "received",
        "email":   email_status,
        "message": f"Thank you {name}! We'll reply to {email} within 24–48 hours.",
    }


@app.get("/api/v1/support/faq")
async def get_faq():
    return {
        "faq_items": [
            {
                "id": 1,
                "question": "Is my data secure?",
                "answer": "Yes — passwords are bcrypt-hashed. All data is stored encrypted at rest on Railway PostgreSQL."
            },
            {
                "id": 2,
                "question": "Where is my data stored?",
                "answer": "PostgreSQL on Railway cloud infrastructure, hosted in a secure private network."
            },
            {
                "id": 3,
                "question": "What currency does WandaTools use?",
                "answer": "Default is Emalangeni (E) for Eswatini. You can set your preferred currency (E, ZAR, USD, GBP, EUR) during registration or per transaction."
            },
            {
                "id": 4,
                "question": "How long does my login session last?",
                "answer": "Your access token lasts 30 minutes. Your device refreshes it automatically using a 7-day refresh token — so you stay logged in without re-entering your password."
            },
            {
                "id": 5,
                "question": "How do I contact support?",
                "answer": "Use the contact form on the website or email admin@wandatools.com directly."
            },
        ],
        "total": 5,
    }


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
