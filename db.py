"""
Database Configuration & Session Management
SQLAlchemy setup for PostgreSQL connection
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from config import settings

# Database URL
DATABASE_URL = settings.DATABASE_URL

# Create engine
if settings.ENVIRONMENT == "testing":
    # Use SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # Use PostgreSQL for production/development
    engine = create_engine(
        DATABASE_URL,
        echo=settings.DEBUG,  # Log SQL queries in debug mode
        pool_pre_ping=True,   # Verify connections before using
        pool_size=10,
        max_overflow=20,
    )

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for all models
Base = declarative_base()


# Dependency for FastAPI
def get_db():
    """
    Dependency function to get database session
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize database (create all tables)
def init_db():
    """Create all tables in database"""
    Base.metadata.create_all(bind=engine)


# Health check
def health_check_db():
    """
    Test database connectivity
    Returns True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            return result is not None
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False
