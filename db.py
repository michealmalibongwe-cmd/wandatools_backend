"""
WandaTools — db.py
Location: ROOT folder (same level as main.py)

Thin wrapper around the engine and session created in main.py.
Does NOT define its own engine, Base, or models.

How it works:
  - main.py creates the engine, Base, SessionLocal, and all models at startup
  - db.py imports those and re-exports get_db() for all route files
  - Route files import get_db from here — not from main.py directly

Usage in any route file:
    from db import get_db
    from fastapi import Depends
    from sqlalchemy.orm import Session

    @router.get("/example")
    def example(db: Session = Depends(get_db)):
        ...
"""

import os
import logging
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

log = logging.getLogger("wandatools.db")

# ─────────────────────────────────────────────────────────────
# ENVIRONMENT DETECTION
# Set ENVIRONMENT=testing in your test runner (pytest, etc.)
# Leave unset or set to "production" for Railway deployment.
# ─────────────────────────────────────────────────────────────

ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
IS_TESTING  = ENVIRONMENT == "testing"
DEBUG_SQL   = os.getenv("DEBUG", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────
# DATABASE URL
# Same value as main.py — reads from Railway env var.
# ─────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ─────────────────────────────────────────────────────────────
# ENGINE + SESSION
# Testing:    in-memory SQLite (isolated, fast)
# Production: re-use engine from main.py (no duplicate connections)
# ─────────────────────────────────────────────────────────────

if IS_TESTING:
    log.info("🧪 Test environment — using in-memory SQLite")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=DEBUG_SQL,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

else:
    try:
        from main import engine, SessionLocal          # noqa: F401
        log.info("✅ db.py: engine + SessionLocal imported from main.py")
    except ImportError as exc:
        # Fallback for standalone scripts (migrations, seeds)
        log.warning(f"⚠️  Could not import from main.py ({exc}) — building standalone engine")
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20,
            connect_args={"connect_timeout": 10},
            echo=DEBUG_SQL,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ─────────────────────────────────────────────────────────────
# BASE
# Always imported from main.py so all models are registered.
# ─────────────────────────────────────────────────────────────

try:
    from main import Base                              # noqa: F401
except ImportError:
    Base = declarative_base()
    log.warning("⚠️  db.py: standalone Base — main.py models NOT registered")


# ─────────────────────────────────────────────────────────────
# get_db() — FastAPI dependency injected into every route
# ─────────────────────────────────────────────────────────────

def get_db():
    """
    Yield a database session. Guarantees the session closes
    after the request completes, even if an exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# init_db() — create all tables (tests and migration scripts)
# main.py already calls this at startup — only call explicitly in tests.
# ─────────────────────────────────────────────────────────────

def init_db():
    try:
        import main  # noqa: F401 — triggers model registration
        Base.metadata.create_all(bind=engine)
        log.info("✅ init_db: all tables created / verified")
    except Exception as exc:
        log.error(f"❌ init_db failed: {exc}")
        raise


# ─────────────────────────────────────────────────────────────
# health_check_db() — ping the DB, returns True/False
# ─────────────────────────────────────────────────────────────

def health_check_db() -> bool:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result is not None
    except Exception as exc:
        log.error(f"❌ DB health check failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────
# drop_all_tables() — TEST USE ONLY
# ─────────────────────────────────────────────────────────────

def drop_all_tables():
    """Drop all tables. Refused outside test environment."""
    if not IS_TESTING:
        log.error("❌ drop_all_tables() refused outside test environment")
        raise RuntimeError("drop_all_tables() only allowed when ENVIRONMENT=testing")
    Base.metadata.drop_all(bind=engine)
    log.info("🧪 All tables dropped (test teardown)")