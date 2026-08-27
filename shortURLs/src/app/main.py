from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.api.endpoints import url as url_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.url_mongodb import (
    close_mongodb,
    get_db,
    initialize_mongodb,
    ping_mongodb,
)
from app.db.url_crud import ensure_indexes
from app.middleware.observability import ObservabilityMiddleware
from app.middleware.request_size import RequestBodyLimitMiddleware
from app.utils.rate_limiter import RateLimiter

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def app_lifespan(_app_instance: FastAPI):
    logger.info("application_starting")
    initialize_mongodb()
    try:
        await ping_mongodb()
        if settings.enable_unique_indexes:
            try:
                await ensure_indexes(get_db())
            except Exception as exc:
                logger.exception(
                    "database_index_creation_failed",
                    error_type=type(exc).__name__,
                )
                if settings.index_strict_mode:
                    raise
        logger.info("application_started")
        yield
    finally:
        await close_mongodb()
        logger.info("application_stopped")


def create_app() -> FastAPI:
    configure_logging(settings.log_level, settings.log_json)
    docs_url = "/docs" if settings.enable_docs_url else None
    redoc_url = "/redoc" if settings.enable_redoc_url else None
    _app = FastAPI(docs_url=docs_url, redoc_url=redoc_url, lifespan=app_lifespan)

    origins = settings.cors_allow_origins_list()
    allow_credentials = settings.cors_allow_credentials
    if not origins:
        origins = ["*"]
        allow_credentials = False
    elif "*" in origins:
        allow_credentials = False

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.enable_rate_limit:
        _app.add_middleware(RateLimiter, max_requests=2, period=60)

    _app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=settings.max_request_body_bytes,
    )
    _app.add_middleware(
        ObservabilityMiddleware,
        service_name=settings.service_name,
    )

    _app.include_router(url_router.router, prefix="/api/v1")

    if settings.enable_metrics:
        _app.mount("/metrics", make_asgi_app())

    @_app.get("/")
    async def root():
        return {"message": "Welcome to the URL Shortener API"}

    @_app.get("/health/live", include_in_schema=False)
    async def liveness():
        return {"status": "ok"}

    @_app.get("/health/ready", include_in_schema=False)
    async def readiness():
        try:
            await ping_mongodb()
        except Exception as exc:
            logger.warning(
                "readiness_check_failed",
                error_type=type(exc).__name__,
            )
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "dependency": "mongodb"},
            )
        return {"status": "ok"}

    @_app.delete("/test-delete")
    async def test_delete():
        return {"message": "DELETE method is allowed"}

    return _app


app = create_app()
