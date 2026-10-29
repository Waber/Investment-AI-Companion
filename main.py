from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.companies import router as companies_router
from app.api.data_collection import router as data_collection_router
from app.api.financial_metrics import router as financial_metrics_router
from app.api.prices import router as prices_router
from app.api.research import notes_router, theses_router
from app.api.watchlist import router as watchlist_router
from app.core.config import settings
from app.core.init_db import init_db
from app.core.validation import request_validation_exception_handler
from app.models.price_bar import restore_volume_openapi_maximum
from app.ui.forms import router as ui_forms_router
from app.ui.origin import OriginRejected, forbidden_page
from app.ui.router import router as ui_router

# HTMX and CSS live in the repository. The pages link to this directory
# with root-relative paths, so the browser does not fetch a CDN.
STATIC_DIR = Path(__file__).resolve().parent / "static"


async def http_exception_page(request, exc):
    """HTML 405 for /ui. Every other HTTP error stays the API JSON.

    A POST to the instrument list matches the GET route and is 405
    before the endpoint runs. The page uses the same security headers
    as the other /ui responses. API routes keep the JSON handler.
    """
    path = request.url.path
    under_ui = path == "/ui" or path.startswith("/ui/")
    if exc.status_code == 405 and under_ui:
        # Imported here. This module loads the UI routers, and those
        # routers load the header helper.
        from app.ui.router import _with_ui_headers
        from app.ui.templating import render

        response = _with_ui_headers(
            render(request, "method_not_allowed.html", status_code=405)
        )
        allowed = (exc.headers or {}).get("Allow")
        if allowed:
            response.headers["Allow"] = allowed
        return response
    return await http_exception_handler(request, exc)


def create_app(init_database_on_startup: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if init_database_on_startup:
            init_db()
        yield

    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )
    application.add_exception_handler(
        RequestValidationError, request_validation_exception_handler
    )
    application.add_exception_handler(
        StarletteHTTPException, http_exception_page
    )
    # A cross-origin form post under /ui. The API routes do not use it.
    application.add_exception_handler(OriginRejected, forbidden_page)

    # Set up CORS middleware
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            # AnyHttpUrl adds a root slash that HTTP Origin does not contain.
            allow_origins=[
                str(origin).removesuffix("/")
                for origin in settings.cors_origins
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Outermost middleware. A Host header outside ALLOWED_HOSTS is
    # rejected before the route runs. Added last so it wraps CORS.
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )

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
                "DATABASE_URL": (
                    "✓" if settings.DATABASE_URL else "✗ (optional)"
                ),
                "REDIS_URL": "✓" if settings.REDIS_URL else "✗ (optional)",
                "ELASTICSEARCH_URL": (
                    "✓" if settings.ELASTICSEARCH_URL else "✗ (optional)"
                ),
                "NEWS_API_KEY": (
                    "✓" if settings.NEWS_API_KEY else "✗ (optional)"
                ),
                "TWITTER_API_KEY": (
                    "✓" if settings.TWITTER_API_KEY else "✗ (optional)"
                ),
            },
            "environment": {
                "DEBUG": settings.DEBUG,
                "LOG_LEVEL": settings.LOG_LEVEL,
                "ALLOWED_HOSTS": settings.allowed_hosts,
            },
        }

        return config_status

    application.include_router(companies_router, prefix=settings.API_V1_STR)
    application.include_router(
        financial_metrics_router, prefix=settings.API_V1_STR
    )
    application.include_router(
        data_collection_router, prefix=settings.API_V1_STR
    )
    application.include_router(prices_router, prefix=settings.API_V1_STR)
    application.include_router(watchlist_router, prefix=settings.API_V1_STR)
    application.include_router(notes_router, prefix=settings.API_V1_STR)
    application.include_router(theses_router, prefix=settings.API_V1_STR)
    application.include_router(ui_router)
    application.include_router(ui_forms_router)
    application.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )

    def openapi() -> Dict:
        # FastAPI stores ``maximum`` as float. 2**63-1 is not exact
        # in float64, so volume's maximum would be a rounded float.
        # Put the integer back on the dict FastAPI cached.
        schema = FastAPI.openapi(application)
        restore_volume_openapi_maximum(schema)
        return schema

    application.openapi = openapi

    return application


app = create_app()

if __name__ == "__main__":
    # Loopback only. Do not bind every interface.
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=settings.DEBUG)
