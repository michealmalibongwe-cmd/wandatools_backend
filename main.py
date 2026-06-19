"""
WandaTools Backend
FastAPI application for financial management system

Entry Point: main.py
Run with: uvicorn main:app --reload
"""

from fastapi import FastAPI, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from config import settings
from db import init_db, health_check_db
from routes import auth, tools, wandaai, support

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══ Lifespan Events ═══
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown
    """
    # Startup
    logger.info("🚀 WandaTools Backend Starting Up...")
    init_db()
    logger.info("✅ Database initialized")
    
    if health_check_db():
        logger.info("✅ Database connection healthy")
    else:
        logger.warning("⚠️ Database connection failed - check configuration")
    
    yield
    
    # Shutdown
    logger.info("🛑 WandaTools Backend Shutting Down...")


# ═══ Create FastAPI App ═══
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered financial insights and management platform",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)


# ═══ CORS Middleware ═══
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══ Custom Exception Handlers ═══
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": str(exc) if settings.DEBUG else None
        }
    )


# ═══ Routes ═══
@app.get("/", tags=["root"])
async def root():
    """Root endpoint - API info"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/api/docs",
        "openapi": "/api/openapi.json"
    }


@app.get("/api/v1", tags=["root"])
async def api_v1_info():
    """API v1 info"""
    return {
        "version": "1.0.0",
        "name": "WandaTools API v1",
        "endpoints": {
            "auth": "/api/v1/auth",
            "tools": "/api/v1/tools",
            "wandaai": "/api/v1/wandaai",
            "support": "/api/v1/support"
        }
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    db_healthy = health_check_db()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "healthy" if db_healthy else "unhealthy",
        "timestamp": str(__import__('datetime').datetime.utcnow()),
        "version": settings.APP_VERSION
    }


# ═══ Register Routes ═══
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(tools.router, prefix=settings.API_PREFIX)
app.include_router(wandaai.router, prefix=settings.API_PREFIX)
app.include_router(support.router, prefix=settings.API_PREFIX)


# ═══ Startup Logging ═══
if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[0]}@***")
    logger.info(f"CORS origins: {settings.CORS_ORIGINS}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )
