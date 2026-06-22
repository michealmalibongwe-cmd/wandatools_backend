"""
WandaTools — db.py
Database configuration, session management, and health utilities.



How it works:
  - main.py creates the engine, Base, SessionLocal, and all models at startup.
  - db.py imports those and exposes helper functions for testing, health
    checks, and anywhere else in the project that needs a DB session.
  - Any route file (routes/auth.py, routes/transactions.py, etc.) should
    import get_db from here — not from main.py directly.
"""

import os
import logging
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

log = logging.getLogger("wandatools.db")

# ─────────────────────────────────────────────────────────────
# ENVIRONMENT DETECTION
# ─────────────────────────────────────────────────────────────
# Set ENVIRONMENT=testing in your test runner (pytest, etc.)
# Set ENVIRONMENT=production or leave unset for Railway deployment.

ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
IS_TESTING  = ENVIRONMENT == "testing"
DEBUG_SQL   = os.getenv("DEBUG", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────
# DATABASE URL — same resolution logic as main.py
# ─────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:PQFnczJqHdqKAsAtXAHicJMsSuVClByk@reseau.proxy.rlwy.net:27449/railway"
)

# SQLAlchemy requires "postgresql://" not legacy "postgres://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ─────────────────────────────────────────────────────────────
# ENGINE — import from main.py in production; create a local
# in-memory SQLite engine only during automated testing.
# ─────────────────────────────────────────────────────────────

if IS_TESTING:
    # Isolated in-memory SQLite for unit / integration tests.
    # StaticPool keeps the same connection alive for the whole test session
    # so tables created in one fixture are visible in the next.
    log.info("🧪 Test environment detected — using in-memory SQLite")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=DEBUG_SQL,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

else:
    # Production / development: re-use the engine built in main.py.
    # Importing here triggers main.py's startup (DB connection, table creation).
    # This means db.py is intentionally lightweight — main.py owns the engine.
    try:
        from main import engine, SessionLocal          # noqa: F401  (re-exported)
        log.info("✅ db.py: imported engine and SessionLocal from main.py")
    except ImportError as exc:
        # Fallback: if db.py is used standalone (e.g. a migration script),
        # build its own engine using the same settings as main.py.
        log.warning(f"⚠️  Could not import from main.py ({exc}) — building standalone engine")
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm
        engine = _ce(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20,
            connect_args={"connect_timeout": 10},
            echo=DEBUG_SQL,
        )
        SessionLocal = _sm(autocommit=False, autoflush=False, bind=engine)


# ─────────────────────────────────────────────────────────────
# BASE — always imported from main.py so all models are registered
# ─────────────────────────────────────────────────────────────

try:
    from main import Base                              # noqa: F401  (re-exported)
except ImportError:
    # Standalone fallback (e.g. running a migration script directly)
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()
    log.warning("⚠️  db.py: using a standalone Base — models from main.py are NOT registered")


# ─────────────────────────────────────────────────────────────
# get_db() — FastAPI dependency for all route files
# ─────────────────────────────────────────────────────────────

def get_db():
    """
    FastAPI dependency — yields a database session and guarantees it closes.

    Usage in any route file:
        from db import get_db
        from fastapi import Depends
        from sqlalchemy.orm import Session

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# init_db() — creates all tables (call this in tests or migrations)
# ─────────────────────────────────────────────────────────────

def init_db():
    """
    Create all tables defined in main.py's models.
    main.py already calls this at startup — only call this explicitly in:
      - Test fixtures (to set up the in-memory SQLite schema)
      - Database migration / seeding scripts
    """
    try:
        # Import models so they register on Base.metadata before create_all
        import main  # noqa: F401  — registers User, Transaction, RefreshToken, ContactMessage
        Base.metadata.create_all(bind=engine)
        log.info("✅ init_db: all tables created / verified")
    except Exception as exc:
        log.error(f"❌ init_db failed: {exc}")
        raise


# ─────────────────────────────────────────────────────────────
# health_check_db() — used by /health endpoint and monitoring
# ─────────────────────────────────────────────────────────────

def health_check_db() -> bool:
    """
    Ping the database with SELECT 1.
    Returns True if the connection is live, False otherwise.
    Safe to call from the /health endpoint or an uptime monitor.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))   # text() required for SQLAlchemy 2.x
            return result is not None
    except Exception as exc:
        log.error(f"❌ DB health check failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────
# drop_all_tables() — TEST USE ONLY
# ─────────────────────────────────────────────────────────────

def drop_all_tables():
    """
    Drop every table. ONLY use this in test teardown — never in production.
    Guarded by an environment check.
    """
    if not IS_TESTING:
        log.error("❌ drop_all_tables() called outside a test environment — refused")
        raise RuntimeError("drop_all_tables() is only allowed when ENVIRONMENT=testing")

    Base.metadata.drop_all(bind=engine)
    log.info("🧪 All tables dropped (test teardown)")
