"""
WandaTools — config.py
Location: ROOT folder (same level as main.py)

Centralised settings using pydantic-settings.
All values read from environment variables.
Defaults are safe for local development — override on Railway.

Usage anywhere in the project:
    from config import get_settings
    settings = get_settings()
    print(settings.DATABASE_URL)

Railway env vars to set:
  DATABASE_URL            PostgreSQL connection string (auto-injected by Railway)
  JWT_SECRET              Random hex string — openssl rand -hex 32
  JWT_REFRESH_SECRET      Different random hex — openssl rand -hex 32
  ACCESS_TOKEN_MINUTES    Default: 30
  REFRESH_TOKEN_DAYS      Default: 7
  SMTP_HOST               Default: smtp.gmail.com
  SMTP_PORT               Default: 587
  SMTP_USER               Your sending email address
  SMTP_PASSWORD           Gmail App Password
  SUPPORT_EMAIL           Email that receives contact form submissions
  FRONTEND_URL            https://wandatools.vercel.app
  ALLOWED_ORIGINS         Comma-separated list of allowed CORS origins
  ENVIRONMENT             production | development | testing
  DEBUG                   true | false (enables SQL query logging)
  PORT                    Default: 8000 (Railway sets this automatically)
  TOTP_ISSUER             Default: WandaTools (shown in authenticator apps)
  PASSWORD_REQUIRE_NUMBERS  true | false — Default: true
  PASSWORD_REQUIRE_SPECIAL  true | false — Default: true
"""

import secrets
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All WandaTools configuration in one place.
    Values are read from environment variables automatically.
    Field names match the env var names exactly (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",               # load from .env file in local dev
        env_file_encoding="utf-8",
        case_sensitive=False,          # DATABASE_URL == database_url
        extra="ignore",                # ignore unknown env vars
    )

    # ─────────────────────────────────────────────────────────
    # DATABASE
    # ─────────────────────────────────────────────────────────

    DATABASE_URL: str = ""   # required — set DATABASE_URL on Railway

    # ─────────────────────────────────────────────────────────
    # JWT / AUTH
    # ─────────────────────────────────────────────────────────

    JWT_SECRET:           str = ""   # required — set on Railway
    JWT_REFRESH_SECRET:   str = ""   # required — set on Railway
    JWT_ALGORITHM:        str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS:   int = 7

    # ─────────────────────────────────────────────────────────
    # SMTP EMAIL
    # ─────────────────────────────────────────────────────────

    SMTP_HOST:     str = "smtp.gmail.com"
    SMTP_PORT:     int = 587
    SMTP_USER:     str = ""                             # set on Railway
    SMTP_PASSWORD: str = ""                             # set on Railway
    SUPPORT_EMAIL: str = "admin@wandatools.com"

    # ─────────────────────────────────────────────────────────
    # FRONTEND + CORS
    # ─────────────────────────────────────────────────────────

    FRONTEND_URL:    str = "https://wandatools.vercel.app"
    ALLOWED_ORIGINS: str = (
        "https://wandatools.vercel.app,"
        "http://localhost:3000,"
        "http://localhost:5500"
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a Python list for FastAPI middleware."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ─────────────────────────────────────────────────────────
    # ENVIRONMENT + DEBUGGING
    # ─────────────────────────────────────────────────────────

    ENVIRONMENT: str  = "production"    # production | development | testing
    DEBUG:       bool = False           # enables SQL query logging when True
    PORT:        int  = 8000

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT.lower() == "testing"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    # ─────────────────────────────────────────────────────────
    # SECURITY POLICY
    # ─────────────────────────────────────────────────────────

    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    TOTP_ISSUER:              str  = "WandaTools"

    # ─────────────────────────────────────────────────────────
    # CURRENCY
    # ─────────────────────────────────────────────────────────

    DEFAULT_CURRENCY:     str  = "E"    # Emalangeni — Eswatini
    SUPPORTED_CURRENCIES: str  = "E,ZAR,USD,GBP,EUR"

    @property
    def supported_currencies_set(self) -> set[str]:
        """Return SUPPORTED_CURRENCIES as a Python set."""
        return {c.strip().upper() for c in self.SUPPORTED_CURRENCIES.split(",") if c.strip()}


@lru_cache()
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.
    @lru_cache ensures settings are only loaded once per process.

    Usage:
        from config import get_settings
        settings = get_settings()
        print(settings.DATABASE_URL)
    """
    return Settings()