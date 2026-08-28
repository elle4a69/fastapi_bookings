"""Centralized Privacy-Safe OpenTelemetry Observability Module.

Provides traces, metrics, structured logs, and frontend diagnostic forwarding.
All configuration is driven strictly through `settings` (from app.core.config).
Redaction is enforced via an Allowlist-based Span Exporter wrapper prior to export.
"""

import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Sequence, Set
from urllib.parse import urlparse

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan, Event
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from ..core.config import settings

logger = logging.getLogger(__name__)

# Global Sentinel & Pipeline State
_telemetry_initialized: bool = False
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None
_logger_provider: Optional[Any] = None
_last_export_status: str = "idle"
_last_export_timestamp: Optional[str] = None

# Allowlist alias for backward compatibility
telemetry_disabled: bool = settings.OTEL_SDK_DISABLED

# Safe Telemetry Attribute Allowlist
SAFE_ATTRIBUTE_KEYS: Set[str] = {
    "http.method",
    "http.route",
    "http.status_code",
    "http.scheme",
    "http.target",
    "db.system",
    "db.operation",
    "error.type",
    "exception.type",
    "service.name",
    "service.namespace",
    "deployment.environment",
    "frontend.event_type",
    "frontend.error_class",
    "frontend.route",
    "frontend.component",
    "frontend.duration_ms",
    "frontend.vital_name",
    "event_code",
    "status",
    "job_type",
    "operation",
    "reason",
    "account_id",
}

# Strict Enum Sets for Metrics & Events
VALID_STATUSES: Set[str] = {"accepted", "rejected", "duplicate", "failed", "success", "retry", "queued", "cancelled", "processed", "activated", "alert_repeated", "acknowledged"}
VALID_OPERATIONS: Set[str] = {"confirm", "cancel", "reschedule", "complete", "noshow", "search", "create", "update", "delete", "other"}
VALID_REASONS: Set[str] = {"client_no_show", "slot_unavailable", "invalid_state", "unauthorized", "validation_failed", "payment_failed", "other"}
VALID_JOB_TYPES: Set[str] = {"outbox_sms", "chatwoot_sync", "ai_autopilot", "arrival_notification", "other"}

# Path Normalization Pattern
PATH_ID_PATTERN = re.compile(r"/\d+(?=/|$)")

def sanitize_url_path(url_val: str) -> str:
    """Normalize raw URL paths to template format (/path/{id}) and strip query strings."""
    if not url_val or not isinstance(url_val, str):
        return ""
    try:
        parsed = urlparse(url_val)
        clean_path = PATH_ID_PATTERN.sub("/{id}", parsed.path)
        return clean_path
    except Exception:
        return "/redacted"

def sanitize_attribute_value(key: str, val: Any) -> Any:
    """Validate and sanitize single attribute value against privacy rules."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool)):
        return val
    
    str_val = str(val)
    if key in ("http.route", "http.target", "frontend.route"):
        return sanitize_url_path(str_val)
    
    # Strip string values containing query tokens, credentials, or sensitive symbols
    if any(s in str_val.lower() for s in ["token=", "key=", "auth=", "secret=", "password=", "@"]):
        return "[REDACTED]"
    
    if len(str_val) > 150:
        return str_val[:147] + "..."
    return str_val


class SanitizedSpanProxy:
    """Read-only proxy wrapping a ReadableSpan to enforce privacy redaction before export."""
    def __init__(self, span: ReadableSpan, allowed_keys: Set[str]):
        self._span = span
        
        # 1. Allowlist-filtered attributes
        clean_attrs: Dict[str, Any] = {}
        if span.attributes:
            for k, v in span.attributes.items():
                if k in allowed_keys:
                    sanitized_val = sanitize_attribute_value(k, v)
                    if sanitized_val is not None:
                        clean_attrs[k] = sanitized_val
        self.attributes = clean_attrs

        # 2. Sanitized events (keep exception class name only; drop raw message & stacktrace)
        clean_events = []
        if span.events:
            for ev in span.events:
                ev_attrs = {}
                if ev.attributes:
                    if "exception.type" in ev.attributes:
                        ev_attrs["exception.type"] = str(ev.attributes["exception.type"])
                    elif "error.type" in ev.attributes:
                        ev_attrs["error.type"] = str(ev.attributes["error.type"])
                    elif "event_type" in ev.attributes:
                        ev_attrs["event_type"] = str(ev.attributes["event_type"])
                clean_events.append(Event(name=ev.name, attributes=ev_attrs, timestamp=ev.timestamp))
        self.events = clean_events

    def __getattr__(self, name: str) -> Any:
        return getattr(self._span, name)


class PrivacySafeSpanExporter(SpanExporter):
    """Wrapper exporter enforcing strict attribute allowlisting and fail-closed error safety."""
    def __init__(self, wrapped_exporter: SpanExporter):
        self.wrapped_exporter = wrapped_exporter

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        global _last_export_status, _last_export_timestamp
        try:
            sanitized_spans = [SanitizedSpanProxy(s, SAFE_ATTRIBUTE_KEYS) for s in spans]
            result = self.wrapped_exporter.export(sanitized_spans)
            if result == SpanExportResult.SUCCESS:
                _last_export_status = "ok"
                _last_export_timestamp = datetime.now(timezone.utc).isoformat()
            else:
                _last_export_status = "error"
            return result
        except Exception as e:
            _last_export_status = "error"
            logger.debug(f"PrivacySafeSpanExporter export suppressed exception: {e}")
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


# Global Meter & Metric Instruments
tracer = trace.get_tracer("fastapi-bookings")
meter = metrics.get_meter("fastapi-bookings")

webhook_counter = meter.create_counter("webhook_events_total", description="Chatwoot webhooks count")
sms_counter = meter.create_counter("sms_events_total", description="Outbound SMS count")
ai_counter = meter.create_counter("ai_jobs_total", description="AI jobs count")
arrival_counter = meter.create_counter("arrival_events_total", description="Arrival system events count")
link_counter = meter.create_counter("link_resolution_failures_total", description="Short-link resolution failures count")
booking_counter = meter.create_counter("booking_failures_total", description="Booking operations failures count")

api_duration = meter.create_histogram("api_request_duration_seconds", description="Duration of API routes")
job_duration = meter.create_histogram("job_execution_duration_seconds", description="Duration of background worker jobs")


# Bounded Enum Helpers
def record_webhook_event(status: str) -> None:
    """Record a webhook event using a bounded status code."""
    clean_status = status if status in VALID_STATUSES else "failed"
    webhook_counter.add(1, {"status": clean_status})
    record_telemetry_log(f"WEBHOOK_{clean_status.upper()}", "INFO", "chatwoot_service", status=clean_status)

def record_sms_event(status: str, account_id: Optional[int] = None) -> None:
    """Record SMS outbound status using a bounded status enum."""
    clean_status = status if status in VALID_STATUSES else "failure"
    attrs = {"status": clean_status}
    if account_id is not None:
        attrs["account_id"] = str(account_id)
    sms_counter.add(1, attrs)
    record_telemetry_log(f"SMS_{clean_status.upper()}", "INFO" if clean_status == "success" else "ERROR", "sms_service", status=clean_status)

def record_ai_event(status: str, job_type: str) -> None:
    """Record AI job status using bounded enums."""
    clean_status = status if status in VALID_STATUSES else "failed"
    clean_job_type = job_type if job_type in VALID_JOB_TYPES else "other"
    attrs = {"status": clean_status, "job_type": clean_job_type}
    ai_counter.add(1, attrs)
    record_telemetry_log(f"AI_JOB_{clean_status.upper()}", "INFO" if clean_status == "processed" else "ERROR", "ai_service", status=clean_status)

def record_arrival_event(status: str) -> None:
    """Record arrival status using bounded enums."""
    clean_status = status if status in VALID_STATUSES else "activated"
    arrival_counter.add(1, {"status": clean_status})
    record_telemetry_log(f"ARRIVAL_{clean_status.upper()}", "INFO", "arrival_service", status=clean_status)

def record_link_failure() -> None:
    """Record a short-link resolution failure."""
    link_counter.add(1)
    record_telemetry_log("LINK_RESOLUTION_FAILURE", "WARNING", "link_service")

def record_booking_failure(operation: str, reason: str) -> None:
    """Record a booking operation failure using validated enum codes."""
    clean_op = operation if operation in VALID_OPERATIONS else "other"
    clean_reason = reason if reason in VALID_REASONS else "other"
    attrs = {"operation": clean_op, "reason": clean_reason}
    booking_counter.add(1, attrs)
    record_telemetry_log(f"BOOKING_{clean_op.upper()}_FAILURE", "WARNING", "booking_service", status="failed")


# Dedicated Structured Telemetry Log Path
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
    """Emit a dedicated structured telemetry log record with allowlisted fields only."""
    log_data = {
        "event_code": str(event_code)[:50],
        "level": str(level)[:10],
        "safe_module": str(module)[:50],
        "request_id": str(request_id)[:32],
        "trace_id": str(trace_id)[:32],
        "route": sanitize_url_path(route_template),
        "method": str(method)[:10],
        "status": str(status)[:20],
        "error_class": str(error_class)[:50],
        "duration_ms": round(float(duration_ms), 2) if duration_ms else 0.0,
    }
    
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.add_event(f"telemetry_log.{event_code}", log_data)
        
    t_logger = logging.getLogger(f"telemetry.{module}")
    log_level = getattr(logging, level.upper(), logging.INFO)
    t_logger.log(log_level, f"Telemetry Event: {event_code}", extra=log_data)


def init_telemetry(app=None) -> None:
    """Idempotently initialize OpenTelemetry Traces, Metrics, Logs, and Instrumentations."""
    global _telemetry_initialized, _tracer_provider, _meter_provider, _logger_provider, _last_export_status

    if _telemetry_initialized:
        return

    if settings.OTEL_SDK_DISABLED:
        logger.info("Telemetry is disabled via settings (OTEL_SDK_DISABLED=True)")
        _last_export_status = "disabled"
        return

    base_endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
    traces_url = f"{base_endpoint}/v1/traces"
    metrics_url = f"{base_endpoint}/v1/metrics"
    logs_url = f"{base_endpoint}/v1/logs"

    resource = Resource.create({
        "service.name": "fastapi-bookings",
        "service.namespace": settings.APP_ENV,
        "deployment.environment": settings.APP_ENV,
    })

    # 1. Traces Pipeline
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        raw_exporter = OTLPSpanExporter(endpoint=traces_url, timeout=3)
        safe_exporter = PrivacySafeSpanExporter(raw_exporter)
        _tracer_provider = TracerProvider(resource=resource)
        _tracer_provider.add_span_processor(BatchSpanProcessor(safe_exporter, max_queue_size=2048, max_export_batch_size=512))
        trace.set_tracer_provider(_tracer_provider)
    except Exception as e:
        logger.warning(f"Failed to initialize Trace Provider: {e}")

    # 2. Metrics Pipeline
    try:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        m_exporter = OTLPMetricExporter(endpoint=metrics_url, timeout=3)
        m_reader = PeriodicExportingMetricReader(m_exporter, export_interval_millis=5000, export_timeout_millis=3000)
        _meter_provider = MeterProvider(resource=resource, metric_readers=[m_reader])
        metrics.set_meter_provider(_meter_provider)
    except Exception as e:
        logger.warning(f"Failed to initialize Metric Provider: {e}")

    # 3. Logs Pipeline
    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        l_exporter = OTLPLogExporter(endpoint=logs_url, timeout=3)
        _logger_provider = LoggerProvider(resource=resource)
        _logger_provider.add_log_record_processor(BatchLogRecordProcessor(l_exporter, max_queue_size=2048, max_export_batch_size=512))
    except Exception as e:
        logger.warning(f"Failed to initialize Log Provider: {e}")

    # 4. Instrumentations
    if app and _tracer_provider:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app, tracer_provider=_tracer_provider)
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from ..db.database import engine
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=_tracer_provider)
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {e}")

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument(tracer_provider=_tracer_provider)
    except Exception as e:
        logger.error(f"Failed to instrument HTTPX: {e}")

    _telemetry_initialized = True
    _last_export_status = "idle"
    logger.info(f"Telemetry initialized using OTLP base endpoint: {base_endpoint}")


def shutdown_telemetry() -> None:
    """Cleanly flush and shutdown OpenTelemetry providers."""
    global _telemetry_initialized, _tracer_provider, _meter_provider, _logger_provider

    if _tracer_provider:
        try:
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
            _logger_provider.shutdown()
        except Exception:
            pass
        _logger_provider = None

    _telemetry_initialized = False


def get_telemetry_status_data() -> Dict[str, Any]:
    """Return truthful, safe telemetry health metadata (no credentials, endpoints, or tokens)."""
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
