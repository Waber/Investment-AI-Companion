import uvicorn
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.validation import request_validation_exception_handler
from app.api.companies import router as companies_router
from app.api.data_collection import router as data_collection_router
from app.api.financial_metrics import router as financial_metrics_router
from app.models.database_models import Base


def create_app(init_database_on_startup: bool = True) -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
    )
    application.add_exception_handler(
        RequestValidationError, request_validation_exception_handler
    )

    # Set up CORS middleware
    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if init_database_on_startup:

        @application.on_event("startup")
        async def startup_event():
            """
            This function runs when the FastAPI application starts up.
            It's used to initialize the database and perform any other startup tasks.
            """
            try:
                # Create all database tables if they don't exist
                # This ensures the database schema is ready when the app starts
                Base.metadata.create_all(bind=engine)
                print("✅ Database tables created/verified successfully!")
            except Exception as e:
                print(f"❌ Error creating database tables: {e}")
                # In production, you might want to exit here if the database is critical
                # For development, we'll continue and let the app start

    @application.get("/")
    async def root():
        return {
            "message": "Welcome to Investment AI Companion API",
            "version": "1.0.0",
            "docs_url": "/docs",
        }

    @application.get("/api/v1/test-config")
    async def test_config() -> Dict:
        """
        Endpoint for testing environment configuration.
        Available only in DEBUG mode.
        """
        if not settings.DEBUG:
            raise HTTPException(
                status_code=403,
                detail="This endpoint is only available in debug mode",
            )

        config_status = {
            "required_settings": {
                "OPENAI_API_KEY": "✓" if settings.OPENAI_API_KEY else "✗",
                "SECRET_KEY": "✓" if settings.SECRET_KEY else "✗",
            },
            "optional_settings": {
                "DATABASE_URL": "✓" if settings.DATABASE_URL else "✗ (optional)",
                "REDIS_URL": "✓" if settings.REDIS_URL else "✗ (optional)",
                "ELASTICSEARCH_URL": "✓"
                if settings.ELASTICSEARCH_URL
                else "✗ (optional)",
                "NEWS_API_KEY": "✓" if settings.NEWS_API_KEY else "✗ (optional)",
                "TWITTER_API_KEY": "✓"
                if settings.TWITTER_API_KEY
                else "✗ (optional)",
            },
            "environment": {
                "DEBUG": settings.DEBUG,
                "LOG_LEVEL": settings.LOG_LEVEL,
                "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
            },
        }

        return config_status

    application.include_router(companies_router, prefix=settings.API_V1_STR)
    application.include_router(financial_metrics_router, prefix=settings.API_V1_STR)
    application.include_router(data_collection_router, prefix=settings.API_V1_STR)

    return application


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
