"""Centralized Privacy-Safe OpenTelemetry Observability Module.

Provides traces, metrics, and dedicated structured logs via OTLP.
All configuration is driven strictly through ``settings`` (app.core.config).
Privacy is enforced by an allowlist-based span exporter wrapper, strict
field validation in the dedicated telemetry log path, and a privacy-redaction
filter for general operational log exports to SigNoz.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Sequence, Set, FrozenSet, List, Tuple
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
# Global pipeline state & lifecycle tracking
# ---------------------------------------------------------------------------
_telemetry_initialized: bool = False
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None
_logger_provider: Optional[Any] = None
_last_export_status: str = "idle"
_last_export_timestamp: Optional[str] = None
telemetry_disabled: bool = settings.OTEL_SDK_DISABLED

# Track only logging handlers created and attached by this telemetry module
# Tuple of (logger_instance, handler_instance)
_telemetry_owned_handlers: List[Tuple[logging.Logger, logging.Handler]] = []

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
        "token=", "key=", "auth=", "secret=", "password=", "bearer ", "prompt", "completion", "sms_body", "sms-body"
    )):
        return "[REDACTED]"
    if "@" in s and "." in s:          # email-like
        return "[REDACTED]"
    if len(s) > 100:
        return "[REDACTED]"
    return s


# ---------------------------------------------------------------------------
# Privacy-Safe Operational Log Redactor & Filter for SigNoz Log Export
# ---------------------------------------------------------------------------
class PrivacySafeLogFilter(logging.Filter):
    """Filter and sanitize log records destined for SigNoz OTLP log export.

    Redacts credentials, tokens, API keys, authorization headers, passwords,
    cookies, secrets, webhook signatures, query strings, and customer PII
    from log messages, arguments, extras, and exception traces.
    """
    _SECRET_PATTERNS = [
        (re.compile(r"(?i)\b(bearer\s+)[a-zA-Z0-9\-\._~\+\/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
        (re.compile(r"(?i)(authorization|api[-_]?key|token|password|secret|cookie|signature|access[-_]?token|refresh[-_]?token|prompt|completion|sms[-_]?body)\s*[:=]\s*['\"]?[^\s,;'\"&]+", re.IGNORECASE), r"\1=[REDACTED]"),
        (re.compile(r"(?i)(password|secret|token|api[-_]?key|authorization|signature|prompt|completion|sms[-_]?body)['\"]?\s*:\s*['\"][^'\"]+['\"]", re.IGNORECASE), r'\1: "[REDACTED]"'),
        (re.compile(r"https?://[^:\s]+:[^@\s]+@", re.IGNORECASE), "https://[REDACTED]@"),
        (re.compile(r"(\b[A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b)"), r"[REDACTED_EMAIL]"),
    ]
    # Query string redaction in HTTP access logs, URLs, or message paths
    _HTTP_ACCESS_QUERY = re.compile(r'(?i)(["\']?\b(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+)([^\s\?]+)\?([^\s"\'<>]+)')
    _GENERIC_URL_QUERY = re.compile(r'(https?://[^\s\?]+)\?([^\s"\'<>]+)', re.IGNORECASE)
    _PATH_QUERY = re.compile(r'(/\b[a-zA-Z0-9_\-\./]+)\?([^\s"\'<>]+)')

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        # 1. Redact query strings from access logs, generic URLs, and path queries
        text = cls._HTTP_ACCESS_QUERY.sub(r"\1\2?[REDACTED]", text)
        text = cls._GENERIC_URL_QUERY.sub(r"\1?[REDACTED]", text)
        text = cls._PATH_QUERY.sub(r"\1?[REDACTED]", text)
        # 2. Redact secret patterns
        for pattern, replacement in cls._SECRET_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # 1. Redact message template
            if isinstance(record.msg, str):
                record.msg = self.redact_text(record.msg)
            # 2. Redact args
            if record.args:
                if isinstance(record.args, dict):
                    clean_args = {}
                    for k, v in record.args.items():
                        if any(s in str(k).lower() for s in ("password", "secret", "token", "auth", "cookie", "key", "signature", "prompt", "completion", "sms_body")):
                            clean_args[k] = "[REDACTED]"
                        elif isinstance(v, str):
                            clean_args[k] = self.redact_text(v)
                        else:
                            clean_args[k] = v
                    record.args = clean_args
                elif isinstance(record.args, (list, tuple)):
                    record.args = tuple(
                        self.redact_text(a) if isinstance(a, str) else a
                        for a in record.args
                    )
            # 3. Redact exception text if pre-formatted
            if record.exc_text:
                record.exc_text = self.redact_text(record.exc_text)
        except Exception:
            pass
        return True


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
            return self.wrapped_exporter.force_flush(timeout_millis=timeout_millis)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Public tracer and meter accessors for worker processes
# ---------------------------------------------------------------------------
class _LazyTracer:
    def __getattr__(self, name: str) -> Any:
        import os
        svc = os.getenv("OTEL_SERVICE_NAME", "fastapi-bookings")
        return getattr(trace.get_tracer(f"{svc}.workers"), name)

    def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
        import os
        svc = os.getenv("OTEL_SERVICE_NAME", "fastapi-bookings")
        return trace.get_tracer(f"{svc}.workers").start_as_current_span(*args, **kwargs)


class _LazyMeter:
    def __getattr__(self, name: str) -> Any:
        import os
        svc = os.getenv("OTEL_SERVICE_NAME", "fastapi-bookings")
        return getattr(metrics.get_meter(f"{svc}.workers"), name)


tracer = _LazyTracer()
meter = _LazyMeter()

# ---------------------------------------------------------------------------
# Dedicated structured telemetry logger
# ---------------------------------------------------------------------------
_TELEMETRY_LOGGER_NAME = "fastapi_bookings.telemetry"


def _clean_string(val: Any, max_len: int = 128) -> str:
    """Coerce to string, strip, and bound length."""
    if val is None:
        return ""
    return str(val).strip()[:max_len]


def record_webhook_event(
    event_type: str = "webhook",
    status: Optional[str] = None,
    reason: str = "",
    account_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    if status is None:
        safe_status = event_type if event_type in WEBHOOK_STATUSES else "failed"
    else:
        safe_status = status if status in WEBHOOK_STATUSES else "failed"
    safe_reason = reason if reason in VALID_REASONS else ("other" if reason else "")
    safe_account_id = _clean_string(account_id, 64) if (account_id and _SAFE_ID_PATTERN.match(str(account_id))) else None

    code_map = {
        "accepted": "WEBHOOK_ACCEPTED",
        "rejected": "WEBHOOK_REJECTED",
        "duplicate": "WEBHOOK_DUPLICATE",
        "failed": "WEBHOOK_FAILED",
    }
    event_code = code_map.get(safe_status, "WEBHOOK_FAILED")

    record_telemetry_log(
        event_code=event_code,
        level="INFO" if safe_status in ("accepted", "duplicate") else "WARNING",
        module="app",
        account_id=safe_account_id,
        duration_ms=duration_ms,
    )


def record_sms_event(
    operation: str,
    status: str,
    job_type: str = "outbox_sms",
    reason: str = "",
    account_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    safe_status = status if status in SMS_STATUSES else "failure"
    safe_job_type = job_type if job_type in VALID_JOB_TYPES else "outbox_sms"
    safe_reason = reason if reason in VALID_REASONS else ("other" if reason else "")
    safe_account_id = _clean_string(account_id, 64) if (account_id and _SAFE_ID_PATTERN.match(str(account_id))) else None

    code_map = {
        "success": "SMS_SUCCESS",
        "failure": "SMS_FAILURE",
        "retry": "SMS_RETRY",
    }
    event_code = code_map.get(safe_status, "SMS_FAILURE")

    record_telemetry_log(
        event_code=event_code,
        level="INFO" if safe_status == "success" else "WARNING",
        module="sms_service",
        account_id=safe_account_id,
        duration_ms=duration_ms,
    )


def record_ai_event(
    operation: str,
    status: str,
    job_type: str = "ai_autopilot",
    reason: str = "",
    account_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    safe_status = status if status in AI_STATUSES else "failed"
    safe_job_type = job_type if job_type in VALID_JOB_TYPES else "ai_autopilot"
    safe_reason = reason if reason in VALID_REASONS else ("other" if reason else "")
    safe_account_id = _clean_string(account_id, 64) if (account_id and _SAFE_ID_PATTERN.match(str(account_id))) else None

    code_map = {
        "queued": "AI_JOB_QUEUED",
        "processed": "AI_JOB_PROCESSED",
        "cancelled": "AI_JOB_CANCELLED",
        "failed": "AI_JOB_FAILED",
    }
    event_code = code_map.get(safe_status, "AI_JOB_FAILED")

    record_telemetry_log(
        event_code=event_code,
        level="INFO" if safe_status in ("queued", "processed") else "WARNING",
        module="ai_service",
        account_id=safe_account_id,
        duration_ms=duration_ms,
    )


def record_arrival_event(
    operation: str,
    status: str,
    job_type: str = "arrival_notification",
    reason: str = "",
    account_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    safe_status = status if status in ARRIVAL_STATUSES else "activated"
    safe_job_type = job_type if job_type in VALID_JOB_TYPES else "arrival_notification"
    safe_reason = reason if reason in VALID_REASONS else ("other" if reason else "")
    safe_account_id = _clean_string(account_id, 64) if (account_id and _SAFE_ID_PATTERN.match(str(account_id))) else None

    code_map = {
        "activated": "ARRIVAL_ACTIVATED",
        "alert_repeated": "ARRIVAL_ALERT_REPEATED",
        "acknowledged": "ARRIVAL_ACKNOWLEDGED",
    }
    event_code = code_map.get(safe_status, "ARRIVAL_ACTIVATED")

    record_telemetry_log(
        event_code=event_code,
        level="INFO",
        module="arrival_service",
        account_id=safe_account_id,
        duration_ms=duration_ms,
    )


def record_link_failure(
    reason: str,
    account_id: Optional[str] = None,
) -> None:
    safe_reason = reason if reason in VALID_REASONS else "other"
    safe_account_id = _clean_string(account_id, 64) if (account_id and _SAFE_ID_PATTERN.match(str(account_id))) else None

    record_telemetry_log(
        event_code="LINK_RESOLUTION_FAILURE",
        level="WARNING",
        module="link_service",
        account_id=safe_account_id,
    )


def record_booking_failure(
    operation: str,
    reason: str,
    account_id: Optional[str] = None,
) -> None:
    safe_op = operation if operation in BOOKING_OPERATIONS else "other"
    safe_reason = reason if reason in VALID_REASONS else "other"
    safe_account_id = _clean_string(account_id, 64) if (account_id and _SAFE_ID_PATTERN.match(str(account_id))) else None

    code_map = {
        "confirm": "BOOKING_CONFIRM_FAILURE",
        "cancel": "BOOKING_CANCEL_FAILURE",
        "reschedule": "BOOKING_RESCHEDULE_FAILURE",
        "complete": "BOOKING_COMPLETE_FAILURE",
        "noshow": "BOOKING_NOSHOW_FAILURE",
        "other": "BOOKING_OTHER_FAILURE",
    }
    event_code = code_map.get(safe_op, "BOOKING_OTHER_FAILURE")

    record_telemetry_log(
        event_code=event_code,
        level="WARNING",
        module="booking_service",
        account_id=safe_account_id,
    )


def record_telemetry_log(
    event_code: str,
    level: str = "INFO",
    module: str = "app",
    account_id: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    route: Optional[str] = None,
    route_template: Optional[str] = None,
    method: Optional[str] = None,
    status: Optional[Any] = None,
    error_class: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    if event_code not in VALID_EVENT_CODES:
        return

    safe_code = event_code
    safe_level = level.upper() if level.upper() in VALID_LOG_LEVELS else "INFO"
    safe_module = module if module in VALID_MODULES else "app"

    safe_account_id = _clean_string(account_id, 64) if (account_id and _SAFE_ID_PATTERN.match(str(account_id))) else None
    safe_request_id = _clean_string(request_id, 64) if (request_id and _SAFE_ID_PATTERN.match(str(request_id))) else None
    safe_trace_id = _clean_string(trace_id, 64) if (trace_id and _SAFE_ID_PATTERN.match(str(trace_id))) else None
    chosen_route = route or route_template
    safe_route = sanitize_url_path(chosen_route) if chosen_route else None
    safe_method = method.upper() if (method and method.upper() in VALID_METHODS) else None
    try:
        int_status = int(status) if status is not None else None
        safe_status = int_status if (int_status is not None and 100 <= int_status <= 599) else None
    except (ValueError, TypeError):
        safe_status = None
    safe_error_class = _clean_string(error_class, 64) if (error_class and _SAFE_ID_PATTERN.match(str(error_class))) else None
    safe_duration = round(float(duration_ms), 2) if (duration_ms is not None and isinstance(duration_ms, (int, float)) and 0 <= duration_ms < 3_600_000) else None

    log_data: Dict[str, Any] = {
        "service": "fastapi-bookings",
        "environment": settings.APP_ENV,
        "event_code": safe_code,
        "account_id": safe_account_id,
        "safe_module": safe_module,
        "request_id": safe_request_id,
        "trace_id": safe_trace_id,
        "route": safe_route,
        "method": safe_method,
        "status": safe_status,
        "error_class": safe_error_class,
        "duration_ms": safe_duration,
    }

    tl = logging.getLogger(_TELEMETRY_LOGGER_NAME)
    log_level_int = getattr(logging, safe_level, logging.INFO)
    tl.log(log_level_int, safe_code, extra=log_data)


# ---------------------------------------------------------------------------
# Telemetry lifecycle
# ---------------------------------------------------------------------------
def init_telemetry(app=None) -> None:
    """Idempotently initialize OTel traces, metrics, logs, and instrumentations.

    Logger Topology:
    - Dedicated Structured Telemetry: Attached to ``fastapi_bookings.telemetry`` with ``propagate=False``.
    - General Application Logs: Attached to root logger (``logging.getLogger()``). Propagating loggers flow here once.
    - Non-Propagating Server Loggers: Attached to ``uvicorn``, ``uvicorn.error``, ``uvicorn.access``, and ``fastapi``
      (since ``setup_logging()`` sets ``propagate=False`` on them).
    - Privacy-Filter: A dedicated ``PrivacySafeLogFilter`` is attached to all operational log handlers to redact
      secrets, query parameters, authorization tokens, passwords, cookies, and sensitive PII before export.
    """
    global _telemetry_initialized, _tracer_provider, _meter_provider
    global _logger_provider, _last_export_status, _telemetry_owned_handlers

    if _telemetry_initialized:
        return

    # Remove any stale telemetry-owned handlers from prior incomplete shutdown
    for lg, h in _telemetry_owned_handlers:
        try:
            lg.removeHandler(h)
        except Exception:
            pass
        try:
            h.close()
        except Exception:
            pass
    _telemetry_owned_handlers.clear()

    if settings.OTEL_SDK_DISABLED:
        logger.info("Telemetry disabled (OTEL_SDK_DISABLED=True)")
        _last_export_status = "disabled"
        _telemetry_initialized = True
        return

    base = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
    import os
    service_name = os.getenv("OTEL_SERVICE_NAME", "fastapi-bookings")
    resource = Resource.create({
        "service.name": service_name,
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

    # 3. Logs — dedicated structured OTLP pipeline + privacy-filtered general server logs
    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (
            OTLPLogExporter,
        )
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        try:
            from opentelemetry.instrumentation.logging.handler import LoggingHandler
        except ImportError:
            from opentelemetry.sdk._logs import LoggingHandler

        l_exp = OTLPLogExporter(endpoint=f"{base}/v1/logs", timeout=3)
        _logger_provider = LoggerProvider(resource=resource)
        _logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(l_exp, max_queue_size=2048,
                                    max_export_batch_size=512)
        )

        # Operational log handler with privacy redaction filter
        op_otlp_handler = LoggingHandler(
            level=logging.INFO,
            logger_provider=_logger_provider,
        )
        op_otlp_handler.addFilter(PrivacySafeLogFilter())

        # Attach to root logger for all propagating application loggers
        root_logger = logging.getLogger()
        root_logger.addHandler(op_otlp_handler)
        _telemetry_owned_handlers.append((root_logger, op_otlp_handler))

        # Attach directly to non-propagating framework loggers (propagate=False)
        for _log_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
            target_logger = logging.getLogger(_log_name)
            target_logger.addHandler(op_otlp_handler)
            _telemetry_owned_handlers.append((target_logger, op_otlp_handler))

        # Attach dedicated structured telemetry handler ONLY to dedicated logger
        dedicated_handler = LoggingHandler(
            level=logging.DEBUG,
            logger_provider=_logger_provider,
        )
        dedicated = logging.getLogger(_TELEMETRY_LOGGER_NAME)
        dedicated.addHandler(dedicated_handler)
        dedicated.setLevel(logging.DEBUG)
        dedicated.propagate = False
        _telemetry_owned_handlers.append((dedicated, dedicated_handler))

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
    """Flush and shut down all OTel providers and remove all telemetry-owned handlers."""
    global _telemetry_initialized, _tracer_provider, _meter_provider, _logger_provider
    global _telemetry_owned_handlers

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

    # Remove all telemetry-owned handlers safely from their respective loggers
    for lg, h in _telemetry_owned_handlers:
        try:
            lg.removeHandler(h)
        except Exception:
            pass
        try:
            h.close()
        except Exception:
            pass
    _telemetry_owned_handlers.clear()

    _telemetry_initialized = False


def get_telemetry_status_data() -> Dict[str, Any]:
    """Safe health metadata — never exposes endpoints, secrets, or tokens."""
    import os
    return {
        "telemetry_enabled": not settings.OTEL_SDK_DISABLED,
        "trace_exporter_active": _tracer_provider is not None,
        "metric_exporter_active": _meter_provider is not None,
        "log_exporter_active": _logger_provider is not None,
        "service_name": os.getenv("OTEL_SERVICE_NAME", "fastapi-bookings"),
        "environment": settings.APP_ENV,
        "last_export_status": _last_export_status,
        "last_export_timestamp": _last_export_timestamp,
    }
