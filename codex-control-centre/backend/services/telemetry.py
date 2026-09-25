"""Centralized Privacy-Safe OpenTelemetry Observability Module for Codex Control Centre.

Provides traces, metrics, and structured logs via OTLP.
Configuration is driven through settings (backend.config).
Privacy is enforced by an allowlist-based span exporter wrapper, strict
field validation in the telemetry log path, and a privacy-redaction
filter for general operational log exports to SigNoz.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Sequence, FrozenSet, List, Tuple
from urllib.parse import urlparse

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan, Event
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from backend.config import settings

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

# Track only logging handlers created and attached by this telemetry module
# Tuple of (logger_instance, handler_instance)
_telemetry_owned_handlers: List[Tuple[logging.Logger, logging.Handler]] = []

# ---------------------------------------------------------------------------
# Span attribute allowlist
# ---------------------------------------------------------------------------
SAFE_ATTRIBUTE_KEYS: FrozenSet[str] = frozenset({
    "http.method", "http.route", "http.status_code", "http.scheme",
    "http.target", "http.url",
    "db.system", "db.operation", "db.name",
    "error.type", "exception.type",
    "service.name", "service.namespace", "deployment.environment",
    "project_id", "thread_id", "turn_id", "turn_number", "request_id",
    "status", "status_code", "duration_ms", "worker_status", "operation",
    "reason", "event_type", "event_code", "tool_name", "risk_tier",
    "client_id", "account_id",
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
    if key in ("http.route", "http.target", "http.url"):
        return sanitize_url_path(s)
    # Redact values that look like they contain secrets or tokens
    low = s.lower()
    if any(tok in low for tok in (
        "token=", "token_secret=", "key=", "auth=", "secret=", "password=",
        "bearer ", "cookie=", "api_key", "prompt", "completion"
    )):
        return "[REDACTED]"
    if "@" in s and "." in s:  # email-like
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
    cookies, secrets, webhook signatures, query strings, and PII
    from log messages, arguments, extras, and exception traces.
    """
    _SECRET_PATTERNS = [
        (re.compile(r"(?i)\b(bearer\s+)[a-zA-Z0-9\-\._~\+\/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
        (
            re.compile(
                r"""(?i)(authorization|api[-_]?key|token|token[-_]?secret|password|secret|cookie|signature|access[-_]?token|refresh[-_]?token|prompt|completion)\s*([:=])\s*(?:['"][^'"]*['"]|[^\s,;'\"&]+)""",
                re.IGNORECASE,
            ),
            r"\1\2[REDACTED]",
        ),
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

    def _redact_data(self, data: Any) -> Any:
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if any(s in str(k).lower() for s in ("password", "secret", "token", "auth", "cookie", "key", "signature", "prompt", "completion")):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = self._redact_data(v)
            return clean
        elif isinstance(data, (list, tuple)):
            res = [self._redact_data(item) for item in data]
            return tuple(res) if isinstance(data, tuple) else res
        elif isinstance(data, str):
            return self.redact_text(data)
        return data

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # 1. Redact message template
            if isinstance(record.msg, str):
                record.msg = self.redact_text(record.msg)
            # 2. Redact args
            if record.args:
                if isinstance(record.args, dict):
                    record.args = self._redact_data(record.args)
                elif isinstance(record.args, (list, tuple)):
                    record.args = tuple(self._redact_data(a) for a in record.args)
            # 3. Redact exception text if pre-formatted
            if record.exc_text:
                record.exc_text = self.redact_text(record.exc_text)
        except Exception:
            pass
        return True


# ---------------------------------------------------------------------------
# Span privacy proxy & Exporter
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
        except Exception as exc:
            logger.warning("PrivacySafeSpanExporter export encountered exception: %s", exc)
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
# Public tracer and meter accessors for worker processes and services
# ---------------------------------------------------------------------------
class _LazyTracer:
    def __getattr__(self, name: str) -> Any:
        svc = getattr(settings, "otel_service_name", "codex-control-centre")
        return getattr(trace.get_tracer(f"{svc}.tracer"), name)

    def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
        svc = getattr(settings, "otel_service_name", "codex-control-centre")
        return trace.get_tracer(f"{svc}.tracer").start_as_current_span(*args, **kwargs)


class _LazyMeter:
    def __getattr__(self, name: str) -> Any:
        svc = getattr(settings, "otel_service_name", "codex-control-centre")
        return getattr(metrics.get_meter(f"{svc}.meter"), name)


tracer = _LazyTracer()
meter = _LazyMeter()

# ---------------------------------------------------------------------------
# Dedicated structured telemetry logger
# ---------------------------------------------------------------------------
_TELEMETRY_LOGGER_NAME = "codex.telemetry"
logging.getLogger(_TELEMETRY_LOGGER_NAME).setLevel(logging.DEBUG)


def _clean_string(val: Any, max_len: int = 128) -> str:
    """Coerce to string, strip, and bound length."""
    if val is None:
        return ""
    return str(val).strip()[:max_len]


def record_telemetry_log(
    event_code: str,
    level: str = "INFO",
    module: str = "codex",
    project_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    route: Optional[str] = None,
    method: Optional[str] = None,
    status: Optional[Any] = None,
    duration_ms: Optional[float] = None,
) -> None:
    safe_code = _clean_string(event_code, 64)
    safe_level = level.upper() if level.upper() in ("DEBUG", "INFO", "WARNING", "ERROR") else "INFO"
    safe_module = _clean_string(module, 64) or "codex"

    safe_project_id = _clean_string(project_id, 64) if (project_id and _SAFE_ID_PATTERN.match(str(project_id))) else None
    safe_thread_id = _clean_string(thread_id, 64) if (thread_id and _SAFE_ID_PATTERN.match(str(thread_id))) else None
    safe_turn_id = _clean_string(turn_id, 64) if (turn_id and _SAFE_ID_PATTERN.match(str(turn_id))) else None
    safe_request_id = _clean_string(request_id, 64) if (request_id and _SAFE_ID_PATTERN.match(str(request_id))) else None
    safe_trace_id = _clean_string(trace_id, 64) if (trace_id and _SAFE_ID_PATTERN.match(str(trace_id))) else None
    safe_route = sanitize_url_path(route) if route else None
    safe_method = method.upper() if method and method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD") else None

    try:
        int_status = int(status) if status is not None else None
        safe_status = int_status if (int_status is not None and 100 <= int_status <= 599) else None
    except (ValueError, TypeError):
        safe_status = None

    safe_duration = round(float(duration_ms), 2) if (duration_ms is not None and isinstance(duration_ms, (int, float)) and 0 <= duration_ms < 3_600_000) else None

    log_data: Dict[str, Any] = {
        "service": getattr(settings, "otel_service_name", "codex-control-centre"),
        "environment": getattr(settings, "environment", "development"),
        "event_code": safe_code,
        "safe_module": safe_module,
        "project_id": safe_project_id,
        "thread_id": safe_thread_id,
        "turn_id": safe_turn_id,
        "request_id": safe_request_id,
        "trace_id": safe_trace_id,
        "route": safe_route,
        "method": safe_method,
        "status": safe_status,
        "duration_ms": safe_duration,
    }

    tl = logging.getLogger(_TELEMETRY_LOGGER_NAME)
    log_level_int = getattr(logging, safe_level, logging.INFO)
    tl.log(log_level_int, safe_code, extra=log_data)


# ---------------------------------------------------------------------------
# Telemetry lifecycle
# ---------------------------------------------------------------------------
def init_telemetry(app: Optional[Any] = None) -> None:
    """Idempotently initialize OTel traces, metrics, logs, and instrumentations."""
    global _telemetry_initialized, _tracer_provider, _meter_provider
    global _logger_provider, _last_export_status, _telemetry_owned_handlers

    if _telemetry_initialized:
        return

    # Clean up any stale telemetry-owned handlers from a prior run
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

    # Check if telemetry is disabled via settings or environment
    is_disabled = getattr(settings, "otel_sdk_disabled", False) or os.getenv("OTEL_SDK_DISABLED", "").lower() in ("true", "1")
    if is_disabled:
        logger.info("OpenTelemetry disabled via otel_sdk_disabled=True")
        _last_export_status = "disabled"
        _telemetry_initialized = True
        return

    base = getattr(settings, "otlp_endpoint", "http://localhost:4318").rstrip("/")
    service_name = getattr(settings, "otel_service_name", "codex-control-centre")
    env = getattr(settings, "environment", "development")

    resource = Resource.create({
        "service.name": service_name,
        "service.namespace": env,
        "deployment.environment": env,
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
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        l_exp = OTLPLogExporter(endpoint=f"{base}/v1/logs", timeout=3)
        _logger_provider = LoggerProvider(resource=resource)
        _logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(l_exp, max_queue_size=2048, max_export_batch_size=512)
        )

        # Operational log handler with privacy redaction filter
        op_otlp_handler = LoggingHandler(
            level=logging.INFO,
            logger_provider=_logger_provider,
        )
        op_otlp_handler.addFilter(PrivacySafeLogFilter())

        # Attach to root logger for propagating application loggers
        root_logger = logging.getLogger()
        root_logger.addHandler(op_otlp_handler)
        _telemetry_owned_handlers.append((root_logger, op_otlp_handler))

        # Attach directly to non-propagating framework loggers
        for _log_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "codex.access", "codex.main"):
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
            FastAPIInstrumentor.instrument_app(app, tracer_provider=_tracer_provider)
        except Exception as exc:
            logger.warning("FastAPI instrumentation failed: %s", exc)

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from backend.database import engine
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=_tracer_provider)
    except Exception as exc:
        logger.warning("SQLAlchemy instrumentation failed: %s", exc)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument(tracer_provider=_tracer_provider)
    except Exception as exc:
        logger.warning("HTTPX instrumentation failed: %s", exc)

    _telemetry_initialized = True
    _last_export_status = "idle"
    logger.info("Telemetry initialized successfully (OTLP base: %s)", base)


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
    is_disabled = getattr(settings, "otel_sdk_disabled", False) or os.getenv("OTEL_SDK_DISABLED", "").lower() in ("true", "1")
    return {
        "telemetry_enabled": not is_disabled,
        "trace_exporter_active": _tracer_provider is not None,
        "metric_exporter_active": _meter_provider is not None,
        "log_exporter_active": _logger_provider is not None,
        "service_name": getattr(settings, "otel_service_name", "codex-control-centre"),
        "environment": getattr(settings, "environment", "development"),
        "last_export_status": _last_export_status,
        "last_export_timestamp": _last_export_timestamp,
    }
