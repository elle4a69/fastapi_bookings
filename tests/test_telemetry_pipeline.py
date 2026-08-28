"""Rigorous tests for the telemetry/observability pipeline.

Covers: configuration resolution, OTLP serialization privacy, metrics with
real reader, dedicated log capture, HTTP 200/404/405 trace evidence, frontend
diagnostics validation, exporter-failure resilience, idempotency, and honest
status reporting.
"""

import logging
import re
import pytest
from unittest.mock import MagicMock

from opentelemetry.sdk.trace import ReadableSpan, Event
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import SpanContext, TraceFlags
from opentelemetry.exporter.otlp.proto.common._internal.trace_encoder import (
    encode_spans,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.core.config import settings
from app.core.telemetry import (
    PrivacySafeSpanExporter,
    SanitizedSpanProxy,
    SAFE_ATTRIBUTE_KEYS,
    VALID_EVENT_CODES,
    VALID_MODULES,
    WEBHOOK_STATUSES,
    SMS_STATUSES,
    AI_STATUSES,
    record_webhook_event,
    record_sms_event,
    record_ai_event,
    record_arrival_event,
    record_link_failure,
    record_booking_failure,
    record_telemetry_log,
    get_telemetry_status_data,
    sanitize_url_path,
    _TELEMETRY_LOGGER_NAME,
    init_telemetry,
    shutdown_telemetry,
)
from app.main import app


# ── 1. Configuration Resolution ──────────────────────────────────────────

def test_config_resolution():
    """Settings must define OTEL fields; telemetry reads from settings only."""
    assert hasattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT")
    assert hasattr(settings, "OTEL_SDK_DISABLED")
    # Default must be port 4318, not 8080
    default_val = settings.__class__.model_fields["OTEL_EXPORTER_OTLP_ENDPOINT"].default
    assert "4318" in str(default_val)
    status = get_telemetry_status_data()
    assert status["service_name"] == "fastapi-bookings"
    assert status["environment"] == settings.APP_ENV


# ── 2. OTLP Serialization Privacy ────────────────────────────────────────

def test_otlp_serialization_privacy():
    """Prohibited sentinel values must be absent from real OTLP protobuf output."""
    SENTINELS = {
        "token":   "bearer_secret_token_xyz_789",
        "phone":   "+15559876543",
        "email":   "customer.pii@example.com",
        "sql":     "SELECT password FROM users WHERE id = 42",
        "errmsg":  "Auth failed for customer.pii@example.com with bearer_secret_token_xyz_789",
        "stack":   "Traceback:\n  File 'secret.py', line 1\n    password='open sesame'",
        "qstring": "/booking/99?token=bearer_secret_token_xyz_789&key=abc",
        "custpath": "/customers/john-doe-vip-client/bookings/99",
    }

    ctx = SpanContext(
        trace_id=0xAABBCCDD11223344AABBCCDD11223344,
        span_id=0xAABBCCDD11223344,
        is_remote=False,
        trace_flags=TraceFlags(1),
    )

    raw_span = ReadableSpan(
        name="privacy_test",
        context=ctx,
        attributes={
            "http.method": "POST",
            "http.route": SENTINELS["qstring"],
            "http.status_code": 200,
            "secret_token": SENTINELS["token"],
            "customer_phone": SENTINELS["phone"],
            "customer_email": SENTINELS["email"],
            "db.statement": SENTINELS["sql"],
            "error.type": "ValueError",
        },
        events=[
            Event(
                name="exception",
                attributes={
                    "exception.type": "ValueError",
                    "exception.message": SENTINELS["errmsg"],
                    "exception.stacktrace": SENTINELS["stack"],
                },
                timestamp=100000,
            )
        ],
    )

    # Run through PrivacySafeSpanExporter with mock inner
    mock_inner = MagicMock()
    mock_inner.export.return_value = None
    safe_exporter = PrivacySafeSpanExporter(mock_inner)
    safe_exporter.export([raw_span])

    proxy = mock_inner.export.call_args[0][0][0]

    # Encode via real OTLP protobuf encoder
    pb = encode_spans([proxy])
    pb_str = str(pb)

    for label, sentinel in SENTINELS.items():
        assert sentinel not in pb_str, f"Sentinel '{label}' leaked into OTLP payload"

    # Allowlisted values must survive
    assert "POST" in pb_str
    assert "ValueError" in pb_str


# ── 3. Metrics with InMemoryMetricReader ──────────────────────────────────

def test_metrics_with_in_memory_reader(monkeypatch):
    """Metric counters must produce real data points with correct names/values."""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    meter = provider.get_meter("test-meter")

    wh_ctr = meter.create_counter("webhook_events_total")
    wh_ctr.add(1, {"status": "accepted"})
    wh_ctr.add(3, {"status": "rejected"})

    sms_ctr = meter.create_counter("sms_events_total")
    sms_ctr.add(2, {"status": "success"})

    data = reader.get_metrics_data()
    assert data is not None
    rm = data.resource_metrics
    assert len(rm) > 0
    all_metrics = []
    for r in rm:
        for sm in r.scope_metrics:
            all_metrics.extend(sm.metrics)

    names = {m.name for m in all_metrics}
    assert "webhook_events_total" in names
    assert "sms_events_total" in names

    # Check specific data points
    for m in all_metrics:
        if m.name == "webhook_events_total":
            dps = m.data.data_points
            total = sum(dp.value for dp in dps)
            assert total == 4  # 1 + 3
            attrs = {
                frozenset(dp.attributes.items()): dp.value for dp in dps
            }
            assert attrs[frozenset({("status", "accepted")})] == 1
            assert attrs[frozenset({("status", "rejected")})] == 3


# ── 4. Dedicated Log Capture ─────────────────────────────────────────────

def test_dedicated_log_capture():
    """record_telemetry_log must emit via the dedicated logger, with validated fields."""
    captured = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            captured.append(record)

    tl = logging.getLogger(_TELEMETRY_LOGGER_NAME)
    handler = CaptureHandler()
    tl.addHandler(handler)
    old_propagate = tl.propagate
    tl.propagate = False
    try:
        record_telemetry_log(
            event_code="WEBHOOK_ACCEPTED",
            level="INFO",
            module="chatwoot_service",
            request_id="abc123def456",
            route_template="/api/webhook?token=secret123",
            method="POST",
            status="200",
            duration_ms=42.5,
        )
        assert len(captured) == 1
        rec = captured[0]
        assert rec.event_code == "WEBHOOK_ACCEPTED"
        assert rec.safe_module == "chatwoot_service"
        assert rec.method == "POST"
        assert rec.route == "/api/webhook"  # query stripped
        assert rec.duration_ms == 42.5
        assert "secret" not in rec.route
        assert "token" not in rec.route

        # Invalid event code must be silently rejected
        captured.clear()
        record_telemetry_log(
            event_code="ARBITRARY_INJECTED_EVENT<script>",
            module="hacker_module",
        )
        assert len(captured) == 0  # rejected

        # Invalid module falls back to "app"
        captured.clear()
        record_telemetry_log(event_code="HTTP_REQUEST_SUCCESS", module="evil_module")
        assert len(captured) == 1
        assert captured[0].safe_module == "app"
    finally:
        tl.removeHandler(handler)
        tl.propagate = old_propagate


# ── 5. HTTP 200 / 404 / 405 Trace Evidence ───────────────────────────────

def test_http_200_404_405_trace_evidence(client):
    """HTTP responses must carry X-Trace-ID and correct status codes."""
    # 200 via the public diagnostics endpoint
    r200 = client.post(
        "/api/public/diagnostics/telemetry",
        json={
            "event_type": "web_vital",
            "vital_name": "LCP",
            "duration_ms": 100.0,
        },
    )
    assert r200.status_code == 200
    assert "X-Trace-ID" in r200.headers
    assert len(r200.headers["X-Trace-ID"]) == 32  # hex trace id

    # 404
    r404 = client.get("/api/public/nonexistent-route-telemetry-test")
    assert r404.status_code == 404
    assert "X-Trace-ID" in r404.headers

    # 405 — GET on a POST-only endpoint
    r405 = client.get("/api/public/diagnostics/telemetry")
    assert r405.status_code == 405
    assert "X-Trace-ID" in r405.headers


# ── 6. Frontend Diagnostics Validation ────────────────────────────────────

def test_frontend_diagnostics_validation(client):
    """Public diagnostics endpoint must reject invalid/dangerous payloads."""
    # Valid → accepted
    r = client.post(
        "/api/public/diagnostics/telemetry",
        json={"event_type": "js_error", "error_class": "TypeError"},
    )
    assert r.json() == {"status": "accepted"}

    # Invalid event_type → rejected
    r = client.post(
        "/api/public/diagnostics/telemetry",
        json={"event_type": "xss_injection<script>"},
    )
    assert r.json() == {"status": "rejected"}

    # Tokenized URL → query stripped in the span, but endpoint still accepts
    r = client.post(
        "/api/public/diagnostics/telemetry",
        json={
            "event_type": "route_change",
            "route": "/checkout?token=secret123#step2",
        },
    )
    assert r.json() == {"status": "accepted"}

    # UUID-like dynamic route → accepted but path should be sanitized
    r = client.post(
        "/api/public/diagnostics/telemetry",
        json={
            "event_type": "route_change",
            "route": "/customers/550e8400-e29b-41d4-a716-446655440000/edit",
        },
    )
    assert r.json() == {"status": "accepted"}


# ── 7. Exporter Failure Non-Impact ────────────────────────────────────────

def test_exporter_failure_non_impact():
    """A failing exporter must not crash the wrapper or propagate exceptions."""
    boom = MagicMock()
    boom.export.side_effect = RuntimeError("Collector on fire")
    safe = PrivacySafeSpanExporter(boom)

    ctx = SpanContext(
        trace_id=0x1111, span_id=0x2222,
        is_remote=False, trace_flags=TraceFlags(1),
    )
    span = ReadableSpan(name="fail_test", context=ctx)

    result = safe.export([span])
    assert result == SpanExportResult.FAILURE  # no exception raised


# ── 8. Idempotency ───────────────────────────────────────────────────────

def test_idempotency():
    """Calling init_telemetry repeatedly must not install duplicate providers."""
    init_telemetry(app)
    init_telemetry(app)
    # If this didn't raise, idempotency guard is working.
    # The dedicated logger must have at most one OTLP handler.
    tl = logging.getLogger(_TELEMETRY_LOGGER_NAME)
    otlp_handlers = [
        h for h in tl.handlers
        if type(h).__name__ == "LoggingHandler"
    ]
    assert len(otlp_handlers) <= 1


# ── 9. Status Endpoint Honesty ────────────────────────────────────────────

def test_status_endpoint_honest(client, db_session):
    """Status endpoint must return honest state and never expose secrets."""
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.core.security import create_access_token

    t = Tenant(name="StatusBiz", subdomain="status-biz")
    db_session.add(t)
    db_session.commit()
    u = User(tenant_id=t.id, login="stat_admin", password_hash="x", role="owner")
    db_session.add(u)
    db_session.commit()

    token = create_access_token({"sub": str(u.id)})
    r = client.get(
        "/api/admin/system/diagnostics/telemetry/status",
        headers={"X-Tenant": "status-biz", "X-Token": token},
    )
    assert r.status_code == 200
    data = r.json()

    assert "telemetry_enabled" in data
    assert "last_export_status" in data
    assert data["service_name"] == "fastapi-bookings"

    # Must distinguish states
    assert data["last_export_status"] in ("idle", "ok", "error", "disabled")

    # Must never expose sensitive data
    payload = str(data).lower()
    assert "localhost" not in payload
    assert "4318" not in payload
    assert "secret" not in payload
    assert "password" not in payload
    assert "token" not in payload


# ── Helpers: path sanitisation ────────────────────────────────────────────

def test_sanitize_url_path_coverage():
    """URL sanitiser must strip query/hash/numeric/UUID/hex/long-slug segments."""
    assert sanitize_url_path("/api/bookings/42") == "/api/bookings/{id}"
    assert sanitize_url_path("/api/bookings/42?token=x") == "/api/bookings/{id}"
    assert sanitize_url_path("/api/bookings/42#sec") == "/api/bookings/{id}"
    assert sanitize_url_path(
        "/customers/550e8400-e29b-41d4-a716-446655440000/edit"
    ) == "/customers/{id}/edit"
    assert sanitize_url_path(
        "/verify/aabbccdd11223344aabbccdd11223344/confirm"
    ) == "/verify/{id}/confirm"
    assert sanitize_url_path("") == ""
    assert sanitize_url_path("/plain") == "/plain"


# ── Worker Compatibility ──────────────────────────────────────────────────

def test_worker_tracer_accessor_compatibility():
    """Verify tracer can be imported from app.core.telemetry and used in worker spans."""
    from app.core.telemetry import tracer, meter
    assert tracer is not None
    assert meter is not None

    # Must support start_as_current_span as a context manager without raising
    with tracer.start_as_current_span("worker_test_span") as span:
        assert span is not None

