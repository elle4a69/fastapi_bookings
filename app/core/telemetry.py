"""Centralized Privacy-Safe OpenTelemetry Observability Module.

Provides traces, metrics, and dedicated structured logs via OTLP.
All configuration is driven strictly through ``settings`` (app.core.config).
Privacy is enforced by an allowlist-based span exporter wrapper and strict
field validation in the dedicated telemetry log path.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Sequence, Set, FrozenSet
from urllib.parse import urlparse

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan, Event
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor, SpanExporter, SpanExportResult,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from ..core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global pipeline state
# ---------------------------------------------------------------------------
_telemetry_initialized: bool = False
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None
_logger_provider: Optional[Any] = None
_last_export_status: str = "idle"
_last_export_timestamp: Optional[str] = None
telemetry_disabled: bool = settings.OTEL_SDK_DISABLED

# ---------------------------------------------------------------------------
# Span attribute allowlist
# ---------------------------------------------------------------------------
SAFE_ATTRIBUTE_KEYS: FrozenSet[str] = frozenset({
    "http.method", "http.route", "http.status_code", "http.scheme",
    "http.target",
    "db.system", "db.operation",
    "error.type", "exception.type",
    "service.name", "service.namespace", "deployment.environment",
    "frontend.event_type", "frontend.error_class", "frontend.route",
    "frontend.component", "frontend.duration_ms", "frontend.vital_name",
    "event_code", "status", "job_type", "operation", "reason",
    "account_id",
})

# ---------------------------------------------------------------------------
# Per-domain bounded enum sets
# ---------------------------------------------------------------------------
WEBHOOK_STATUSES: FrozenSet[str] = frozenset({
    "accepted", "rejected", "duplicate", "failed",
})
SMS_STATUSES: FrozenSet[str] = frozenset({
    "success", "failure", "retry",
})
AI_STATUSES: FrozenSet[str] = frozenset({
    "queued", "processed", "cancelled", "failed",
})
ARRIVAL_STATUSES: FrozenSet[str] = frozenset({
    "activated", "alert_repeated", "acknowledged",
})
BOOKING_OPERATIONS: FrozenSet[str] = frozenset({
    "confirm", "cancel", "reschedule", "complete", "noshow", "other",
})
VALID_REASONS: FrozenSet[str] = frozenset({
    "client_no_show", "slot_unavailable", "invalid_state",
    "unauthorized", "validation_failed", "payment_failed", "other",
})
VALID_JOB_TYPES: FrozenSet[str] = frozenset({
    "outbox_sms", "chatwoot_sync", "ai_autopilot",
    "arrival_notification", "other",
})

# ---------------------------------------------------------------------------
# Structured telemetry log allowlists
# ---------------------------------------------------------------------------
VALID_EVENT_CODES: FrozenSet[str] = frozenset({
    "HTTP_REQUEST_SUCCESS", "HTTP_404_NOT_FOUND",
    "HTTP_405_METHOD_NOT_ALLOWED", "HTTP_5XX_ERROR",
    "WEBHOOK_ACCEPTED", "WEBHOOK_REJECTED",
    "WEBHOOK_DUPLICATE", "WEBHOOK_FAILED",
    "SMS_SUCCESS", "SMS_FAILURE", "SMS_RETRY",
    "AI_JOB_QUEUED", "AI_JOB_PROCESSED",
    "AI_JOB_CANCELLED", "AI_JOB_FAILED",
    "ARRIVAL_ACTIVATED", "ARRIVAL_ALERT_REPEATED",
    "ARRIVAL_ACKNOWLEDGED",
    "LINK_RESOLUTION_FAILURE",
    "BOOKING_CONFIRM_FAILURE", "BOOKING_CANCEL_FAILURE",
    "BOOKING_RESCHEDULE_FAILURE", "BOOKING_COMPLETE_FAILURE",
    "BOOKING_NOSHOW_FAILURE", "BOOKING_OTHER_FAILURE",
    "LIVE_TEST_EVENT",
})
VALID_LOG_LEVELS: FrozenSet[str] = frozenset({
    "DEBUG", "INFO", "WARNING", "ERROR",
})
VALID_MODULES: FrozenSet[str] = frozenset({
    "app", "chatwoot_service", "sms_service", "ai_service",
    "arrival_service", "link_service", "booking_service",
    "diagnostics", "live_validator",
})
VALID_METHODS: FrozenSet[str] = frozenset({
    "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "",
})

# ---------------------------------------------------------------------------
# Path sanitization — strips numeric IDs, UUIDs, hex tokens, and long slugs
# ---------------------------------------------------------------------------
_PATH_NUMERIC = re.compile(r"/\d+(?=/|$)")
_PATH_UUID = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?=/|$)"
)
_PATH_HEX_TOKEN = re.compile(r"/[0-9a-fA-F]{16,}(?=/|$)")
_PATH_LONG_SLUG = re.compile(r"/[a-zA-Z0-9_-]{32,}(?=/|$)")
_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def sanitize_url_path(url_val: str) -> str:
    """Strip query strings, hashes, and dynamic path segments from a URL path."""
    if not url_val or not isinstance(url_val, str):
        return ""
    try:
        parsed = urlparse(url_val)
        path = parsed.path
        path = _PATH_UUID.sub("/{id}", path)
        path = _PATH_HEX_TOKEN.sub("/{id}", path)
        path = _PATH_NUMERIC.sub("/{id}", path)
        path = _PATH_LONG_SLUG.sub("/{id}", path)
        return path[:200]
    except Exception:
        return "/redacted"


def _sanitize_attribute_value(key: str, val: Any) -> Any:
    """Sanitize a single span attribute value."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool)):
        return val
    s = str(val)
    if key in ("http.route", "http.target", "frontend.route"):
        return sanitize_url_path(s)
    # Redact values that look like they contain secrets
    low = s.lower()
    if any(tok in low for tok in (
        "token=", "key=", "auth=", "secret=", "password=", "bearer ",
    )):
        return "[REDACTED]"
    if "@" in s and "." in s:          # email-like
        return "[REDACTED]"
    if len(s) > 100:
        return "[REDACTED]"
    return s


# ---------------------------------------------------------------------------
# Span privacy proxy
# ---------------------------------------------------------------------------
class SanitizedSpanProxy:
    """Read-only proxy wrapping a ReadableSpan; enforces attribute allowlisting."""

    def __init__(self, span: ReadableSpan, allowed_keys: FrozenSet[str]):
        self._span = span

        clean: Dict[str, Any] = {}
        if span.attributes:
            for k, v in span.attributes.items():
                if k in allowed_keys:
                    sv = _sanitize_attribute_value(k, v)
                    if sv is not None:
                        clean[k] = sv
        self.attributes = clean

        clean_events = []
        if span.events:
            for ev in span.events:
                ea: Dict[str, Any] = {}
                if ev.attributes:
                    if "exception.type" in ev.attributes:
                        ea["exception.type"] = str(ev.attributes["exception.type"])
                clean_events.append(
                    Event(name=ev.name, attributes=ea, timestamp=ev.timestamp)
                )
        self.events = clean_events

    def __getattr__(self, name: str) -> Any:
        return getattr(self._span, name)


class PrivacySafeSpanExporter(SpanExporter):
    """Wraps another exporter; strips non-allowlisted attributes before export."""

    def __init__(self, wrapped_exporter: SpanExporter):
        self.wrapped_exporter = wrapped_exporter

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        global _last_export_status, _last_export_timestamp
        try:
            sanitized = [SanitizedSpanProxy(s, SAFE_ATTRIBUTE_KEYS) for s in spans]
            result = self.wrapped_exporter.export(sanitized)
            if result == SpanExportResult.SUCCESS:
                _last_export_status = "ok"
                _last_export_timestamp = datetime.now(timezone.utc).isoformat()
            else:
                _last_export_status = "error"
            return result
        except Exception:
            _last_export_status = "error"
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        try:
            self.wrapped_exporter.shutdown()
        except Exception:
            pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        try:
            return self.wrapped_exporter.force_flush(timeout_millis)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Per-domain metric recorders
# ---------------------------------------------------------------------------
_webhook_counter = metrics.get_meter("fastapi-bookings").create_counter(
    "webhook_events_total", description="Chatwoot webhook events",
)
_sms_counter = metrics.get_meter("fastapi-bookings").create_counter(
    "sms_events_total", description="Outbound SMS events",
)
_ai_counter = metrics.get_meter("fastapi-bookings").create_counter(
    "ai_jobs_total", description="AI job events",
)
_arrival_counter = metrics.get_meter("fastapi-bookings").create_counter(
    "arrival_events_total", description="Arrival system events",
)
_link_counter = metrics.get_meter("fastapi-bookings").create_counter(
    "link_failures_total", description="Short-link resolution failures",
)
_booking_counter = metrics.get_meter("fastapi-bookings").create_counter(
    "booking_failures_total", description="Booking operation failures",
)


def record_webhook_event(status: str) -> None:
    s = status if status in WEBHOOK_STATUSES else "failed"
    _webhook_counter.add(1, {"status": s})
    record_telemetry_log(f"WEBHOOK_{s.upper()}", "INFO", "chatwoot_service")


def record_sms_event(status: str, account_id: Optional[int] = None) -> None:
    s = status if status in SMS_STATUSES else "failure"
    attrs: Dict[str, Any] = {"status": s}
    if account_id is not None:
        attrs["account_id"] = str(int(account_id))
    _sms_counter.add(1, attrs)
    record_telemetry_log(
        f"SMS_{s.upper()}",
        "INFO" if s == "success" else "ERROR",
        "sms_service",
    )


def record_ai_event(status: str, job_type: str) -> None:
    s = status if status in AI_STATUSES else "failed"
    jt = job_type if job_type in VALID_JOB_TYPES else "other"
    _ai_counter.add(1, {"status": s, "job_type": jt})
    record_telemetry_log(
        f"AI_JOB_{s.upper()}",
        "INFO" if s == "processed" else "ERROR",
        "ai_service",
    )


def record_arrival_event(status: str) -> None:
    s = status if status in ARRIVAL_STATUSES else "activated"
    _arrival_counter.add(1, {"status": s})
    record_telemetry_log(f"ARRIVAL_{s.upper()}", "INFO", "arrival_service")


def record_link_failure() -> None:
    _link_counter.add(1)
    record_telemetry_log("LINK_RESOLUTION_FAILURE", "WARNING", "link_service")


def record_booking_failure(operation: str, reason: str) -> None:
    op = operation if operation in BOOKING_OPERATIONS else "other"
    rs = reason if reason in VALID_REASONS else "other"
    _booking_counter.add(1, {"operation": op, "reason": rs})
    record_telemetry_log(
        f"BOOKING_{op.upper()}_FAILURE", "WARNING", "booking_service",
    )


# ---------------------------------------------------------------------------
# Dedicated structured telemetry log
# ---------------------------------------------------------------------------
_TELEMETRY_LOGGER_NAME = "fastapi_bookings.telemetry"


def record_telemetry_log(
    event_code: str,
    level: str = "INFO",
    module: str = "app",
    request_id: str = "",
    trace_id: str = "",
    route_template: str = "",
    method: str = "",
    status: str = "",
    error_class: str = "",
    duration_ms: float = 0.0,
) -> None:
    """Emit a structured telemetry log via the dedicated OTLP-backed logger.

    Every field is validated against a strict allowlist or pattern.  Invalid
    values are replaced with empty strings or defaults — never truncated
    arbitrary text.
    """
    # Validate event_code
    safe_code = event_code if event_code in VALID_EVENT_CODES else ""
    if not safe_code:
        return  # reject unknown events silently

    # Validate level
    safe_level = level.upper() if level.upper() in VALID_LOG_LEVELS else "INFO"

    # Validate module
    safe_module = module if module in VALID_MODULES else "app"

    # Validate method
    safe_method = method.upper() if method.upper() in VALID_METHODS else ""

    # Validate request_id / trace_id — hex/alphanumeric only, bounded length
    safe_request_id = ""
    if request_id and _SAFE_ID_PATTERN.match(request_id):
        safe_request_id = request_id

    safe_trace_id = ""
    if trace_id and _SAFE_ID_PATTERN.match(trace_id):
        safe_trace_id = trace_id

    # Validate route — sanitize dynamic segments
    safe_route = sanitize_url_path(route_template) if route_template else ""

    # Validate status — bounded short string, digits or simple word
    safe_status = ""
    if status and re.match(r"^[a-zA-Z0-9_]{1,20}$", status):
        safe_status = status

    # Validate error_class — identifier only
    safe_error_class = ""
    if error_class and re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]{0,99}$", error_class):
        safe_error_class = error_class

    # Validate duration_ms — bounded numeric
    safe_duration = 0.0
    try:
        d = float(duration_ms)
        if 0.0 <= d <= 300000.0:
            safe_duration = round(d, 2)
    except (TypeError, ValueError):
        pass

    log_data = {
        "event_code": safe_code,
        "safe_module": safe_module,
        "request_id": safe_request_id,
        "trace_id": safe_trace_id,
        "route": safe_route,
        "method": safe_method,
        "status": safe_status,
        "error_class": safe_error_class,
        "duration_ms": safe_duration,
    }

    # Emit to dedicated OTLP-backed logger
    tl = logging.getLogger(_TELEMETRY_LOGGER_NAME)
    log_level_int = getattr(logging, safe_level, logging.INFO)
    tl.log(log_level_int, safe_code, extra=log_data)


# ---------------------------------------------------------------------------
# Telemetry lifecycle
# ---------------------------------------------------------------------------
def init_telemetry(app=None) -> None:
    """Idempotently initialize OTel traces, metrics, logs, and instrumentations."""
    global _telemetry_initialized, _tracer_provider, _meter_provider
    global _logger_provider, _last_export_status

    if _telemetry_initialized:
        return

    if settings.OTEL_SDK_DISABLED:
        logger.info("Telemetry disabled (OTEL_SDK_DISABLED=True)")
        _last_export_status = "disabled"
        _telemetry_initialized = True
        return

    base = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
    resource = Resource.create({
        "service.name": "fastapi-bookings",
        "service.namespace": settings.APP_ENV,
        "deployment.environment": settings.APP_ENV,
    })

    # 1. Traces
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        raw = OTLPSpanExporter(endpoint=f"{base}/v1/traces", timeout=3)
        safe = PrivacySafeSpanExporter(raw)
        _tracer_provider = TracerProvider(resource=resource)
        _tracer_provider.add_span_processor(
            BatchSpanProcessor(safe, max_queue_size=2048, max_export_batch_size=512)
        )
        trace.set_tracer_provider(_tracer_provider)
    except Exception as exc:
        logger.warning("Trace provider init failed: %s", exc)

    # 2. Metrics
    try:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        mr = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{base}/v1/metrics", timeout=3),
            export_interval_millis=5000,
            export_timeout_millis=3000,
        )
        _meter_provider = MeterProvider(resource=resource, metric_readers=[mr])
        metrics.set_meter_provider(_meter_provider)
    except Exception as exc:
        logger.warning("Metric provider init failed: %s", exc)

    # 3. Logs — dedicated OTLP pipeline on ``fastapi_bookings.telemetry``
    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (
            OTLPLogExporter,
        )
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk._logs import LoggingHandler

        l_exp = OTLPLogExporter(endpoint=f"{base}/v1/logs", timeout=3)
        _logger_provider = LoggerProvider(resource=resource)
        _logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(l_exp, max_queue_size=2048,
                                    max_export_batch_size=512)
        )

        # Attach handler ONLY to the dedicated telemetry logger
        handler = LoggingHandler(
            level=logging.DEBUG,
            logger_provider=_logger_provider,
        )
        dedicated = logging.getLogger(_TELEMETRY_LOGGER_NAME)
        dedicated.addHandler(handler)
        dedicated.setLevel(logging.DEBUG)
        dedicated.propagate = False  # never flow to root / arbitrary handlers
    except Exception as exc:
        logger.warning("Log provider init failed: %s", exc)

    # 4. Auto-instrumentations
    if app and _tracer_provider:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(
                app, tracer_provider=_tracer_provider,
            )
        except Exception as exc:
            logger.warning("FastAPI instrumentation failed: %s", exc)

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from ..db.database import engine
        SQLAlchemyInstrumentor().instrument(
            engine=engine, tracer_provider=_tracer_provider,
        )
    except Exception as exc:
        logger.warning("SQLAlchemy instrumentation failed: %s", exc)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument(tracer_provider=_tracer_provider)
    except Exception as exc:
        logger.warning("HTTPX instrumentation failed: %s", exc)

    _telemetry_initialized = True
    _last_export_status = "idle"
    logger.info("Telemetry initialized (OTLP base: %s)", base)


def shutdown_telemetry() -> None:
    """Flush and shut down all OTel providers."""
    global _telemetry_initialized, _tracer_provider, _meter_provider, _logger_provider

    if _tracer_provider:
        try:
            _tracer_provider.force_flush(timeout_millis=5000)
            _tracer_provider.shutdown()
        except Exception:
            pass
        _tracer_provider = None

    if _meter_provider:
        try:
            _meter_provider.shutdown()
        except Exception:
            pass
        _meter_provider = None

    if _logger_provider:
        try:
            _logger_provider.force_flush(timeout_millis=5000)
            _logger_provider.shutdown()
        except Exception:
            pass
        _logger_provider = None

    _telemetry_initialized = False


def get_telemetry_status_data() -> Dict[str, Any]:
    """Safe health metadata — never exposes endpoints, secrets, or tokens."""
    return {
        "telemetry_enabled": not settings.OTEL_SDK_DISABLED,
        "trace_exporter_active": _tracer_provider is not None,
        "metric_exporter_active": _meter_provider is not None,
        "log_exporter_active": _logger_provider is not None,
        "service_name": "fastapi-bookings",
        "environment": settings.APP_ENV,
        "last_export_status": _last_export_status,
        "last_export_timestamp": _last_export_timestamp,
    }
