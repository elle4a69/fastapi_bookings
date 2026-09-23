"""Main application entrypoint.

This module instantiates the FastAPI application, configures CORS,
includes all route modules and initializes the database. It also
exposes simple health and readiness endpoints.
"""

import json
import logging
import os
import traceback
import uuid
from itertools import islice
from time import perf_counter

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match
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


VALIDATION_ERROR_SCAN_LIMIT = 256
VALIDATION_ERROR_DETAIL_LIMIT = 20
# Starlette versions before the terminology update do not export the new name.
HTTP_422_UNPROCESSABLE_CONTENT = getattr(
    status,
    "HTTP_422_UNPROCESSABLE_CONTENT",
    422,
)
_SAFE_HTTP_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
)
_SAFE_DURATION_BUCKETS = (
    (0.010, "lt_10ms"),
    (0.050, "lt_50ms"),
    (0.250, "lt_250ms"),
    (1.000, "lt_1s"),
    (5.000, "lt_5s"),
)
_SAFE_DURATION_LABELS = frozenset(
    {label for _, label in _SAFE_DURATION_BUCKETS} | {"gte_5s"}
)


def _safe_http_method(value) -> str:
    method = value.upper() if isinstance(value, str) else ""
    return method if method in _SAFE_HTTP_METHODS else "OTHER"


def _safe_http_status(value) -> int:
    return value if isinstance(value, int) and 100 <= value <= 599 else 0


def _safe_route_template(value) -> str:
    """Return only a bounded code-owned route template, never a raw URL."""

    if value in {"<unmatched>", "<external>"}:
        return value
    if not isinstance(value, str) or not value.startswith("/") or len(value) > 200:
        return "<unmatched>"
    if "?" in value or "#" in value:
        return "<unmatched>"
    if not all(character.isalnum() or character in "/_-.:{}" for character in value):
        return "<unmatched>"
    return value


def _matched_route_template(request) -> str:
    """Recover the full code-owned template from FastAPI's lazy router match."""

    matched_route = request.scope.get("route")
    matched_path = getattr(matched_route, "path", None)
    for candidate in app.router.routes:
        try:
            match, _ = candidate.matches(request.scope)
        except Exception:
            continue
        if match != Match.FULL:
            continue
        include_context = getattr(candidate, "include_context", None)
        prefix = getattr(include_context, "prefix", "")
        if isinstance(prefix, str) and prefix and isinstance(matched_path, str):
            return _safe_route_template(f"{prefix}{matched_path}")
        candidate_path = getattr(candidate, "path", None)
        if isinstance(candidate_path, str):
            return _safe_route_template(candidate_path)
        break
    return _safe_route_template(matched_path)


def _duration_bucket(seconds: float) -> str:
    for upper_bound, label in _SAFE_DURATION_BUCKETS:
        if seconds < upper_bound:
            return label
    return "gte_5s"


def _is_safe_request_id(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _new_request_id() -> str:
    current_span = trace.get_current_span()
    if current_span and current_span.get_span_context().is_valid:
        return f"{current_span.get_span_context().trace_id:032x}"
    return uuid.uuid4().hex


def _request_id(request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if not _is_safe_request_id(request_id):
        request_id = _new_request_id()
        request.state.request_id = request_id
    return request_id


def _set_correlation_headers(response, request_id: str) -> None:
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Trace-ID"] = request_id


def _sanitize_access_record(record: logging.LogRecord) -> None:
    """Replace access/client log messages with fixed structural records."""

    logger_name = record.name.lower()
    args = record.args if isinstance(record.args, tuple) else ()
    method = "OTHER"
    status_code = 0
    event = "http_access_record"
    route = "<external>"
    duration = None
    request_id = None

    if logger_name == "app.access":
        event = "http_request_completed"
        route = "<unmatched>"
        if len(args) >= 5:
            method = _safe_http_method(args[0])
            route = _safe_route_template(args[1])
            status_code = _safe_http_status(args[2])
            duration = (
                args[3]
                if isinstance(args[3], str) and args[3] in _SAFE_DURATION_LABELS
                else None
            )
            request_id = args[4] if _is_safe_request_id(args[4]) else None
    elif logger_name == "uvicorn.access":
        event = "http_server_access"
        route = "<unmatched>"
        if len(args) >= 5:
            method = _safe_http_method(args[1])
            status_code = _safe_http_status(args[4])
    elif logger_name.startswith("httpx"):
        event = "http_client_access"
        if len(args) >= 4:
            method = _safe_http_method(args[0])
            status_code = _safe_http_status(args[3])
    elif logger_name.startswith("httpcore"):
        event = "http_client_transport"
    else:
        return

    record.msg = event
    record.args = ()
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None
    record.http_method = method
    record.http_route = route
    record.http_status = status_code
    if duration is not None:
        record.duration_bucket = duration
    if request_id is not None:
        record.request_id = request_id


def _install_privacy_safe_record_factory() -> None:
    """Sanitize access records before any handler, exporter, or test sees them."""

    current_factory = logging.getLogRecordFactory()
    if getattr(current_factory, "privacy_safe_access", False):
        return

    def privacy_safe_factory(*args, **kwargs):
        record = current_factory(*args, **kwargs)
        _sanitize_access_record(record)
        return record

    setattr(privacy_safe_factory, "privacy_safe_access", True)
    logging.setLogRecordFactory(privacy_safe_factory)


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
        if (
            record.name in {"app.access", "uvicorn.access"}
            or record.name.lower().startswith(("httpx", "httpcore"))
        ):
            log_data["http_method"] = _safe_http_method(
                getattr(record, "http_method", None)
            )
            log_data["http_route"] = _safe_route_template(
                getattr(record, "http_route", None)
            )
            log_data["http_status"] = _safe_http_status(
                getattr(record, "http_status", None)
            )
            duration = getattr(record, "duration_bucket", None)
            if duration in _SAFE_DURATION_LABELS:
                log_data["duration_bucket"] = duration
            request_id = getattr(record, "request_id", None)
            if _is_safe_request_id(request_id):
                log_data["request_id"] = request_id
        return json.dumps(log_data)


def setup_logging() -> None:
    _install_privacy_safe_record_factory()
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
from .core.telemetry import init_telemetry, telemetry_disabled


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
    sms_accounts,
    sms_webhooks,
    sms_conversations,
    sms_settings,
    sms_arrivals,
    sms_chatwoot,
)


# Database tables are managed entirely via Alembic migrations.



from contextlib import asynccontextmanager


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    yield
    from .core.telemetry import shutdown_telemetry
    shutdown_telemetry()



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

# Initialize OpenTelemetry instrumentation
init_telemetry(app)

# Configure SlowAPI limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(PublicRouteRateLimitMiddleware)


@app.middleware("http")
async def add_correlation_id_header(request, call_next):
    request_id = _request_id(request)
    started_at = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        _set_correlation_headers(response, request_id)
        return response
    finally:
        route = _matched_route_template(request)
        logging.getLogger("app.access").info(
            "http_request_completed",
            request.method,
            route,
            status_code,
            _duration_bucket(perf_counter() - started_at),
            request_id,
        )



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
    
    request_id = _request_id(request)
        
    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": code,
                "message": exc.detail,
                "details": {},
                "request_id": request_id
            }
        }
    )
    _set_correlation_headers(response, request_id)
    return add_cors_headers(request, response)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """Return bounded structural validation errors without reflecting input."""

    request_id = _request_id(request)

    safe_sources = frozenset({"body", "query", "path", "header", "cookie"})
    safe_type_categories = {
        "missing": "missing",
        "json_invalid": "invalid_json",
        "int_parsing": "type_error",
        "int_type": "type_error",
        "float_parsing": "type_error",
        "float_type": "type_error",
        "bool_parsing": "type_error",
        "bool_type": "type_error",
        "string_type": "type_error",
        "list_type": "type_error",
        "dict_type": "type_error",
        "model_attributes_type": "type_error",
        "datetime_parsing": "type_error",
        "datetime_from_date_parsing": "type_error",
        "date_parsing": "type_error",
        "date_from_datetime_parsing": "type_error",
        "time_parsing": "type_error",
        "uuid_parsing": "type_error",
        "decimal_parsing": "type_error",
        "url_parsing": "type_error",
        "enum": "choice_error",
        "literal_error": "choice_error",
        "greater_than": "constraint_error",
        "greater_than_equal": "constraint_error",
        "less_than": "constraint_error",
        "less_than_equal": "constraint_error",
        "string_too_short": "constraint_error",
        "string_too_long": "constraint_error",
        "too_short": "constraint_error",
        "too_long": "constraint_error",
        "extra_forbidden": "extra_field",
    }
    structural_errors: set[tuple[str, str]] = set()
    for error in islice(exc.errors(), VALIDATION_ERROR_SCAN_LIMIT):
        location = error.get("loc") if isinstance(error, dict) else None
        location_source = (
            location[0]
            if isinstance(location, (list, tuple)) and location
            else None
        )
        source = (
            location_source
            if isinstance(location_source, str) and location_source in safe_sources
            else "request"
        )
        raw_type = error.get("type") if isinstance(error, dict) else None
        error_type = (
            safe_type_categories.get(raw_type, "invalid")
            if isinstance(raw_type, str)
            else "invalid"
        )
        structural_errors.add((source, error_type))

    if not structural_errors:
        structural_errors.add(("request", "invalid"))
    details = [
        {
            "loc": [source],
            "type": error_type,
            "message": "Invalid request value.",
        }
        for source, error_type in sorted(structural_errors)[
            :VALIDATION_ERROR_DETAIL_LIMIT
        ]
    ]

    response = JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "ok": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed for the request.",
                "details": details,
                "request_id": request_id
            }
        }
    )
    _set_correlation_headers(response, request_id)
    return add_cors_headers(request, response)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    # Exception text and traceback frames can contain request data. Keep this
    # boundary event structural and rely on the request ID for correlation.
    logging.error("unhandled_exception")
    request_id = _request_id(request)
        
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "ok": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "details": {},
                "request_id": request_id
            }
        }
    )
    _set_correlation_headers(response, request_id)
    return add_cors_headers(request, response)


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
app.include_router(bookings.router, prefix="/api")
app.include_router(availability.router, prefix="/api/public")
app.include_router(admin_dashboard.router, prefix="/api/admin")
app.include_router(public_bootstrap.router, prefix="/api")
app.include_router(public_bookings.router)
app.include_router(audit.router, prefix="/api/admin")
app.include_router(payments.router, prefix="/api/admin")
app.include_router(notifications.router, prefix="/api/admin")

# Feature routers
app.include_router(waitlist.router)
app.include_router(search.router)
app.include_router(ui_config.router)
app.include_router(forms.router)
app.include_router(diagnostics.router)
app.include_router(diagnostics.public_router)
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

# SMS Module routers
app.include_router(sms_accounts.router, prefix="/api/admin")
app.include_router(sms_conversations.router, prefix="/api/admin")
app.include_router(sms_settings.router, prefix="/api/admin")
app.include_router(sms_arrivals.router, prefix="/api/admin")
app.include_router(sms_chatwoot.router, prefix="/api/admin")
app.include_router(sms_chatwoot.router, prefix="/api")
app.include_router(sms_webhooks.router, prefix="/api")


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
