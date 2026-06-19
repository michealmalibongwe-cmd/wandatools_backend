"""
WandaTools Backend Configuration
Handles environment variables and app settings
"""

import os
from typing import Optional
from datetime import timedelta
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/wandatools_db"
    )
    
    # JWT & Security
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-in-production-min-32-chars-required!!"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://wandatools.com",
        "https://www.wandatools.com",
        "https://wandatools-frontend.vercel.app",
        "https://wandatools-frontend.netlify.app"
    ]
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"
    
    # App
    APP_NAME: str = "WandaTools API"
    APP_VERSION: str = "1.0.0"
    
    # API Config
    API_PREFIX: str = "/api/v1"
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # File storage (for documents)
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    
    # Email (for notifications)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = 587
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SUPPORT_EMAIL: str = "support@wandatools.com"
    
    # AI (placeholder for future AI service)
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_API_URL: str = "https://api.openai.com/v1"  # or other AI provider
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()

# Security constants
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_NUMBERS = True
PASSWORD_REQUIRE_SPECIAL = True

# Token expiration
ACCESS_TOKEN_EXPIRE = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
REFRESH_TOKEN_EXPIRE = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
