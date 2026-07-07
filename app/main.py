"""Main application entrypoint.

This module instantiates the FastAPI application, configures CORS,
includes all route modules and initializes the database. It also
exposes simple health and readiness endpoints.
"""

import json
import logging
import os
import traceback

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .core.config import settings
from .db.database import Base, engine


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
provider = TracerProvider()
if otlp_endpoint:
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
)


# Database tables are managed entirely via Alembic migrations.



limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])


class PublicRouteRateLimitMiddleware(SlowAPIMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        is_public = path.startswith("/api/public") or "/public/" in path
        if not is_public:
            return await call_next(request)
        return await super().dispatch(request, call_next)


app = FastAPI(title=settings.PROJECT_NAME, openapi_url="/openapi.json")

# Configure SlowAPI limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(PublicRouteRateLimitMiddleware)

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


@app.get("/health", tags=["system"])
@app.get("/healthcheck", tags=["system"], include_in_schema=False)
def health() -> dict:
    """Simple health check endpoint."""
    return {"ok": True}


@app.get("/ready", tags=["system"])
def readiness() -> dict:
    """Simple readiness check endpoint."""
    return {"ok": True}


@app.get("/version", tags=["system"])
def version() -> dict:
    """Return application version information."""
    return {"ok": True, "data": {"version": "1.0.0", "environment": settings.APP_ENV}}