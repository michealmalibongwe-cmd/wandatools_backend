"""
WandaTools Backend Configuration
"""
import os
from datetime import timedelta


class Settings:
    """Application settings loaded from environment variables"""
    
    # Database
    # Require DATABASE_URL to be set in the environment. No localhost fallback.
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # JWT & Security
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-in-production-min-32-chars-required!!"
    )
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    # CORS
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://wandatools.com",
        "https://www.wandatools.com",
    ]
    
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = ENVIRONMENT == "development"
    
    # App
    APP_NAME = "WandaTools API"
    APP_VERSION = "1.0.0"
    API_PREFIX = "/api/v1"
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_PERIOD = 60
    
    # File storage
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    
    # Email
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = 587
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SUPPORT_EMAIL = "support@wandatools.com"
    
    # AI
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_API_URL = "https://api.openai.com/v1"


# Create settings instance
settings = Settings()

# Security constants
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_NUMBERS = True
PASSWORD_REQUIRE_SPECIAL = True

# Token expiration
ACCESS_TOKEN_EXPIRE = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
REFRESH_TOKEN_EXPIRE = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)