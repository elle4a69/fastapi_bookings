"""Main application entrypoint.

This module instantiates the FastAPI application, configures CORS,
includes all route modules and initializes the database. It also
exposes simple health and readiness endpoints.
"""

import json
import logging
import os
import traceback

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .core.config import settings
from .db.database import Base, engine, get_db


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        current_span = trace.get_current_span()
        if current_span and current_span.get_span_context().is_valid:
            ctx = current_span.get_span_context()
            log_data["trace_id"] = f"{ctx.trace_id:032x}"
            log_data["span_id"] = f"{ctx.span_id:016x}"
        if record.exc_info:
            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(log_data)


def setup_logging() -> None:
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        for h in lg.handlers[:]:
            lg.removeHandler(h)
        lg.addHandler(handler)
        lg.propagate = False


setup_logging()

# --- OpenTelemetry setup ---
otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
telemetry_disabled = os.environ.get("OTEL_SDK_DISABLED", "").lower() in {"1", "true", "yes"}
provider = TracerProvider()
if telemetry_disabled:
    pass
elif otlp_endpoint:
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    except Exception:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
else:
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)


# --- Import routers ---
from .api.routers import (
    auth,
    services,
    providers,
    clients,
    locations,
    bookings,
    availability,
    admin_dashboard,
    public_bootstrap,
    public_bookings,
    audit,
    payments,
    notifications,
    holds,
    waitlist,
    search,
    ui_config,
    forms,
    diagnostics,
    categories,
    resources as resources_router,
    addons,
    products,
    packages,
    # New routers from merge
    admin_schedule,
    additional_fields,
    checkout,
    public_clients,
    public_entities,
    public_timeline,
    series,
    service_relations,
    # FastBook merge
    webhooks,
    calendar_notes,
    general_systems,
    stripe_webhooks,
    devices,
    management_reviews,
    business_profile,
    location_relations,
    system,
    notifications,
    booking_forms,
    relationship_management,
    discovery,
)


# Database tables are managed entirely via Alembic migrations.



import asyncio
from contextlib import asynccontextmanager
from .services.outbox_worker import start_outbox_worker, stop_outbox_worker


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Startup
    worker_task = asyncio.create_task(start_outbox_worker())
    yield
    # Shutdown
    await stop_outbox_worker(worker_task)


limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])


class PublicRouteRateLimitMiddleware(SlowAPIMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        is_public = path.startswith("/api/public") or "/public/" in path
        if not is_public:
            return await call_next(request)
        return await super().dispatch(request, call_next)


servers = [
    {"url": "https://bookopenapi-backend-208926050296.us-central1.run.app", "description": "Production Deployed Server"},
    {"url": "http://localhost:8000", "description": "Local Backend (FastAPI)"},
    {"url": "http://localhost:7070", "description": "Local Frontend Dev Server (Vite)"},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/openapi.json",
    lifespan=app_lifespan,
    servers=servers
)

# Configure SlowAPI limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(PublicRouteRateLimitMiddleware)


def add_cors_headers(request, response: JSONResponse) -> JSONResponse:
    origin = request.headers.get("origin")
    if origin:
        allowed_origins = [o.strip() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()]
        if origin in allowed_origins or "*" in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    code = "HTTP_ERROR"
    if exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 400:
        code = "BAD_REQUEST"
    elif exc.status_code == 409:
        code = "CONFLICT"
    elif exc.status_code == 429:
        code = "TOO_MANY_REQUESTS"
    
    current_span = trace.get_current_span()
    trace_id = ""
    if current_span and current_span.get_span_context().is_valid:
        trace_id = f"{current_span.get_span_context().trace_id:032x}"
        
    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": code,
                "message": exc.detail,
                "details": {},
                "request_id": trace_id
            }
        }
    )
    return add_cors_headers(request, response)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    current_span = trace.get_current_span()
    trace_id = ""
    if current_span and current_span.get_span_context().is_valid:
        trace_id = f"{current_span.get_span_context().trace_id:032x}"
        
    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "ok": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed for the request.",
                "details": jsonable_encoder(exc.errors()),
                "request_id": trace_id
            }
        }
    )
    return add_cors_headers(request, response)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logging.exception(f"Unhandled exception occurred: {str(exc)}")
    current_span = trace.get_current_span()
    trace_id = ""
    if current_span and current_span.get_span_context().is_valid:
        trace_id = f"{current_span.get_span_context().trace_id:032x}"
        
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "ok": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "details": {},
                "request_id": trace_id
            }
        }
    )
    return add_cors_headers(request, response)


if not telemetry_disabled:
    FastAPIInstrumentor.instrument_app(app)

# Configure CORS
origins = [o.strip() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers with prefixes
app.include_router(auth.router, prefix="/api")
app.include_router(services.router, prefix="/api/admin")
app.include_router(providers.router, prefix="/api/admin")
app.include_router(clients.router, prefix="/api/admin")
app.include_router(locations.router, prefix="/api/admin")
app.include_router(bookings.router, prefix="/api/admin")
app.include_router(availability.router, prefix="/api/public")
app.include_router(admin_dashboard.router, prefix="/api/admin")
app.include_router(public_bootstrap.router, prefix="/api")
app.include_router(public_bookings.router)
app.include_router(audit.router, prefix="/api/admin")
app.include_router(payments.router, prefix="/api/admin")
app.include_router(notifications.router, prefix="/api/admin")

# Feature routers
app.include_router(holds.router)
app.include_router(waitlist.router)
app.include_router(search.router)
app.include_router(ui_config.router)
app.include_router(forms.router)
app.include_router(diagnostics.router)
app.include_router(categories.router)
app.include_router(resources_router.router)
app.include_router(addons.router)
app.include_router(products.router)
app.include_router(packages.router)

# Merged routers (no JSON-RPC)
app.include_router(admin_schedule.router)
app.include_router(additional_fields.router)
app.include_router(checkout.router)
app.include_router(public_clients.router)
app.include_router(public_entities.router)
app.include_router(public_timeline.router)
app.include_router(series.router)
app.include_router(service_relations.router, prefix="/api/admin")

# FastBook merge
app.include_router(webhooks.router)
app.include_router(calendar_notes.router)
app.include_router(general_systems.router)
app.include_router(general_systems.public_router)
app.include_router(stripe_webhooks.router)
app.include_router(devices.router)
app.include_router(management_reviews.router)
app.include_router(business_profile.router)
app.include_router(location_relations.router)
app.include_router(system.router)
app.include_router(notifications.router)
app.include_router(booking_forms.admin_router)
app.include_router(booking_forms.public_router)
app.include_router(relationship_management.router)
app.include_router(discovery.router)


@app.get("/health", tags=["system"])
@app.get("/healthcheck", tags=["system"], include_in_schema=False)
def health() -> dict:
    """Simple health check endpoint."""
    return {"ok": True}


@app.get("/ready", tags=["system"])
def readiness(db=Depends(get_db)) -> dict:
    """Readiness check endpoint that verifies database connectivity."""
    from sqlalchemy.sql import text
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logging.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connectivity failed."
        )
    return {"ok": True}


@app.get("/version", tags=["system"])
def version() -> dict:
    """Return application version information."""
    return {"ok": True, "data": {"version": "1.0.0", "environment": settings.APP_ENV}}
