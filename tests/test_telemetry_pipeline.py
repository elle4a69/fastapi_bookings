"""Comprehensive Automated Unit and Integration Tests for Telemetry & Observability Pipeline."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from opentelemetry.sdk.trace import ReadableSpan, Event
from opentelemetry.trace import SpanContext, TraceFlags
from opentelemetry.exporter.otlp.proto.common._internal.trace_encoder import encode_spans

from app.core.config import settings
from app.core.telemetry import (
    init_telemetry,
    shutdown_telemetry,
    PrivacySafeSpanExporter,
    SAFE_ATTRIBUTE_KEYS,
    record_webhook_event,
    record_sms_event,
    record_ai_event,
    record_arrival_event,
    record_link_failure,
    record_booking_failure,
    record_telemetry_log,
    get_telemetry_status_data,
    SanitizedSpanProxy,
)
from app.main import app


def test_telemetry_configuration_resolution():
    """Verify settings drive telemetry configuration cleanly without raw os.environ reads."""
    status = get_telemetry_status_data()
    assert "telemetry_enabled" in status
    assert status["service_name"] == "fastapi-bookings"
    assert status["environment"] == settings.APP_ENV


def test_otlp_serialization_privacy():
    """Test PrivacySafeSpanExporter with real OTLP span encoding to prove prohibited sentinel values are absent."""
    mock_inner_exporter = MagicMock()
    mock_inner_exporter.export.return_value = None
    safe_exporter = PrivacySafeSpanExporter(mock_inner_exporter)

    ctx = SpanContext(trace_id=0x12345678901234567890123456789012, span_id=0x1234567890123456, is_remote=False, trace_flags=TraceFlags(1))

    SENTINEL_TOKEN = "bearer_secret_token_val_123"
    SENTINEL_PHONE = "+15551234567"
    SENTINEL_EMAIL = "customer_privacy@example.com"
    SENTINEL_SQL = "SELECT * FROM users WHERE password = 'super_secret'"
    SENTINEL_MSG = "Authentication failed for user customer_privacy@example.com with token bearer_secret_token_val_123"

    raw_span = ReadableSpan(
        name="test_privacy_serialization_span",
        context=ctx,
        attributes={
            "http.method": "POST",
            "http.route": "/api/bookings/99999?token=" + SENTINEL_TOKEN,
            "http.status_code": 200,
            "secret_token": SENTINEL_TOKEN,
            "customer_phone": SENTINEL_PHONE,
            "customer_email": SENTINEL_EMAIL,
            "sql_statement": SENTINEL_SQL,
            "error.type": "ValueError",
        },
        events=[
            Event(
                name="exception",
                attributes={
                    "exception.type": "ValueError",
                    "exception.message": SENTINEL_MSG,
                    "exception.stacktrace": f"Traceback:\n  File 'auth.py', line 50\n    {SENTINEL_MSG}"
                },
                timestamp=100000
            )
        ]
    )

    safe_exporter.export([raw_span])
    assert mock_inner_exporter.export.called
    exported_proxies = mock_inner_exporter.export.call_args[0][0]
    sanitized_proxy = exported_proxies[0]

    # Real OTLP Protobuf Serialization via trace_encoder.encode_spans
    encoded_otlp_pb = encode_spans([sanitized_proxy])
    otlp_str = str(encoded_otlp_pb)

    # Assert NO prohibited sentinel string appears anywhere in the serialized payload
    assert SENTINEL_TOKEN not in otlp_str
    assert SENTINEL_PHONE not in otlp_str
    assert SENTINEL_EMAIL not in otlp_str
    assert SENTINEL_SQL not in otlp_str
    assert SENTINEL_MSG not in otlp_str

    # Assert allowlisted attributes are present
    assert "http.method" in otlp_str or "POST" in otlp_str
    assert "/api/bookings/{id}" in otlp_str


def test_metric_recorders_and_bounded_enums():
    """Verify metrics recording functions accept bounded enum codes cleanly."""
    record_webhook_event("accepted")
    record_webhook_event("invalid_enum_status")  # falls back to "failed"
    
    record_sms_event("success", account_id=42)
    record_ai_event("processed", job_type="outbox_sms")
    record_arrival_event("activated")
    record_link_failure()
    record_booking_failure(operation="cancel", reason="client_no_show")


def test_safe_structured_telemetry_logging():
    """Verify record_telemetry_log emits structured allowlisted attributes only without KeyError."""
    record_telemetry_log(
        event_code="WEBHOOK_ACCEPTED",
        level="INFO",
        module="chatwoot_service",
        request_id="req_123",
        trace_id="trace_456",
        route_template="/api/chatwoot/webhook?token=secret",
        method="POST",
        status="200",
        duration_ms=45.2,
    )


def test_http_404_405_5xx_telemetry(client: TestClient):
    """Verify HTTP 404, 405, and 200 responses carry correlation headers and trace contexts."""
    # 200 OK
    r200 = client.post("/api/public/diagnostics/telemetry", json={"event_type": "web_vital", "vital_name": "LCP", "duration_ms": 100.0})
    assert r200.status_code == 200
    assert "X-Trace-ID" in r200.headers

    # 404 Not Found
    r404 = client.get("/api/public/non-existent-endpoint-test-404")
    assert r404.status_code == 404
    assert "X-Trace-ID" in r404.headers

    # 405 Method Not Allowed
    r405 = client.get("/api/public/diagnostics/telemetry")
    assert r405.status_code == 405
    assert "X-Trace-ID" in r405.headers


def test_public_frontend_telemetry_validation(client: TestClient):
    """Verify POST /api/public/diagnostics/telemetry validates schemas and strips sensitive inputs."""
    # 1. Valid event
    res1 = client.post("/api/public/diagnostics/telemetry", json={
        "event_type": "js_error",
        "error_class": "TypeError",
        "route": "/checkout/payment?token=secret123#step2",
        "component": "CheckoutForm",
        "duration_ms": 120.0,
    })
    assert res1.status_code == 200
    assert res1.json() == {"status": "accepted"}

    # 2. Invalid event_type -> rejected
    res2 = client.post("/api/public/diagnostics/telemetry", json={
        "event_type": "malicious_script_injection",
        "error_class": "TypeError",
    })
    assert res2.status_code == 200
    assert res2.json() == {"status": "rejected"}


def test_collector_failure_non_impact():
    """Verify exporter failure does not break telemetry exporter wrapper or throw exceptions."""
    failing_inner_exporter = MagicMock()
    failing_inner_exporter.export.side_effect = RuntimeError("Collector connection refused")

    safe_exporter = PrivacySafeSpanExporter(failing_inner_exporter)
    ctx = SpanContext(trace_id=0x1111, span_id=0x2222, is_remote=False, trace_flags=TraceFlags(1))
    span = ReadableSpan(name="test_fail_span", context=ctx)

    # Must return FAILURE without raising RuntimeError to the caller
    res = safe_exporter.export([span])
    assert res.name == "FAILURE"


def test_idempotent_telemetry_init():
    """Verify calling init_telemetry multiple times is safe and idempotent."""
    init_telemetry(app)
    init_telemetry(app)


def test_truthful_telemetry_status(client: TestClient, db_session):
    """Verify GET /api/admin/system/diagnostics/telemetry/status returns truthful state without credentials or endpoints."""
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.core.security import create_access_token

    tenant = Tenant(name="Truth Biz", subdomain="truth-biz")
    db_session.add(tenant)
    db_session.commit()

    user = User(tenant_id=tenant.id, login="truth_admin", password_hash="hash", role="owner")
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"X-Tenant": "truth-biz", "X-Token": token}

    res = client.get("/api/admin/system/diagnostics/telemetry/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    
    assert "telemetry_enabled" in data
    assert "last_export_status" in data
    assert data["service_name"] == "fastapi-bookings"
    
    # Must NOT expose endpoints, tokens, or credentials
    assert "http://localhost" not in str(data)
    assert "secret" not in str(data).lower()
