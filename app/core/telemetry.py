import os
import re
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urlunparse

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

# Module-level flag: True when OTEL_SDK_DISABLED is set to a truthy value
telemetry_disabled: bool = os.environ.get("OTEL_SDK_DISABLED", "").lower() in {"1", "true", "yes"}

# Sensitive key patterns to redact
SENSITIVE_KEYS = re.compile(
    r"(token|key|auth|secret|cookie|password|pwd|email|phone|name|mobile|address|body|prompt|note|payload|message)", 
    re.IGNORECASE
)

def sanitize_url(url_val: str) -> str:
    """Strip query strings from URLs to prevent sensitive data leak in telemetry."""
    if not url_val or not isinstance(url_val, str):
        return url_val
    try:
        parsed = urlparse(url_val)
        if parsed.query:
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    except Exception:
        pass
    return url_val

def sanitize_span_attributes(span) -> None:
    """Sanitize all attributes on a span to protect privacy."""
    if not span or not hasattr(span, "attributes"):
        return
    
    # Extract copy of keys to avoid mutating dictionary during iteration
    for key, val in list(span.attributes.items()):
        # Redact sensitive keys
        if SENSITIVE_KEYS.search(key):
            span.set_attribute(key, "[REDACTED]")
            continue
        
        # Redact sensitive or query-containing values
        if isinstance(val, str):
            if key in ("http.url", "http.target", "http.path") or val.startswith(("http://", "https://", "/")):
                span.set_attribute(key, sanitize_url(val))
            elif "@" in val or (any(c.isdigit() for c in val) and len(val) > 7):
                if SENSITIVE_KEYS.search(val) or "@" in val:
                    span.set_attribute(key, "[REDACTED]")

class PrivacySafeSpanProcessor(SpanProcessor):
    """Middleware span processor that guarantees privacy-safe tracing."""
    def __init__(self, wrapped: SpanProcessor):
        self.wrapped = wrapped

    def on_start(self, span, parent_context=None) -> None:
        self.wrapped.on_start(span, parent_context)

    def on_end(self, span) -> None:
        try:
            sanitize_span_attributes(span)
        except Exception as e:
            logger.error(f"Error sanitizing span attributes: {e}")
        self.wrapped.on_end(span)

    def shutdown(self) -> None:
        self.wrapped.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.wrapped.force_flush(timeout_millis)


# Initialize Global Observability Contexts
tracer = trace.get_tracer("fastapi-bookings")
meter = metrics.get_meter("fastapi-bookings")

# Global Counters & Metrics
webhook_counter = meter.create_counter("webhook_events_total", description="Chatwoot webhooks count")
sms_counter = meter.create_counter("sms_events_total", description="Outbound SMS count")
ai_counter = meter.create_counter("ai_jobs_total", description="AI jobs count")
arrival_counter = meter.create_counter("arrival_events_total", description="Arrival system events count")
link_counter = meter.create_counter("link_resolution_failures_total", description="Short-link resolution failures count")
booking_counter = meter.create_counter("booking_failures_total", description="Booking operations failures count")

api_duration = meter.create_histogram("api_request_duration_seconds", description="Duration of key API routes")
job_duration = meter.create_histogram("job_execution_duration_seconds", description="Duration of background worker jobs")


def record_webhook_event(status: str) -> None:
    """Record a webhook event with status: accepted, rejected, duplicate, failed."""
    webhook_counter.add(1, {"status": status})
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event("webhook_event", {"status": status})

def record_sms_event(status: str, account_id: Optional[int] = None) -> None:
    """Record SMS outbound status: success, failure, retry."""
    attrs = {"status": status}
    if account_id is not None:
        attrs["account_id"] = str(account_id)
    sms_counter.add(1, attrs)
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event("sms_event", attrs)

def record_ai_event(status: str, job_type: str) -> None:
    """Record AI job status: queued, cancelled, processed, failed."""
    attrs = {"status": status, "job_type": job_type}
    ai_counter.add(1, attrs)
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event("ai_event", attrs)

def record_arrival_event(status: str) -> None:
    """Record arrival status: activated, alert_repeated, acknowledged."""
    arrival_counter.add(1, {"status": status})
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event("arrival_event", {"status": status})

def record_link_failure() -> None:
    """Record a short-link resolution failure."""
    link_counter.add(1)
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event("link_resolution_failure")

def record_booking_failure(operation: str, reason: str) -> None:
    """Record a booking operation failure."""
    booking_counter.add(1, {"operation": operation, "reason": reason})
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event("booking_failure", {"operation": operation, "reason": reason})


def init_telemetry(app=None) -> None:
    """Initialize OpenTelemetry and attach instrumentations."""
    telemetry_disabled = os.environ.get("OTEL_SDK_DISABLED", "").lower() in {"1", "true", "yes"}
    if telemetry_disabled:
        logger.info("Telemetry is disabled via OTEL_SDK_DISABLED=true")
        return

    # Use HTTP OTLP exporter pointing to SigNoz collector
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4318"
    if not otlp_endpoint.endswith("/v1/traces") and "localhost:4318" in otlp_endpoint:
        otlp_endpoint = otlp_endpoint.rstrip("/") + "/v1/traces"

    # Configure Resource metadata
    resource = Resource(attributes={
        "service.name": "fastapi-bookings",
        "service.namespace": "production",
        "deployment.environment": os.environ.get("APP_ENV", "development")
    })

    provider = TracerProvider(resource=resource)
    
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        # Wrap the OTLP exporter in our PrivacySafeSpanProcessor
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, timeout=5)
        provider.add_span_processor(PrivacySafeSpanProcessor(BatchSpanProcessor(exporter)))
        logger.info(f"Telemetry initialized using OTLP endpoint: {otlp_endpoint}")
    except Exception as e:
        logger.warning(f"Failed to load OTLP exporter: {e}. Falling back to Console exporter.")
        provider.add_span_processor(PrivacySafeSpanProcessor(BatchSpanProcessor(ConsoleSpanExporter())))

    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    if app:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI app: {e}")

    # Instrument SQLAlchemy
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from ..db.database import engine
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {e}")

    # Instrument HTTPX Client (for outbound Chatwoot calls)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
    except Exception as e:
        logger.error(f"Failed to instrument HTTPX client: {e}")

    # Instrument standard logging
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=False)
    except Exception as e:
        logger.error(f"Failed to instrument Logging: {e}")
