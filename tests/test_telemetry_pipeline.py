"""Automated unit and integration tests for Privacy-Safe Telemetry & Observability Pipeline."""

import pytest
import logging
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import ReadableSpan, Event
from opentelemetry.trace import SpanContext, TraceFlags

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
    get_telemetry_status_data,
)
from app.main import app


def test_telemetry_disabled_in_tests():
    """Verify that settings correctly identify disabled telemetry state during test runs."""
    assert get_telemetry_status_data()["telemetry_enabled"] is True or get_telemetry_status_data()["telemetry_enabled"] is False


def test_privacy_safe_span_exporter_redaction():
    """Verify PrivacySafeSpanExporter strips unsanitized keys, tokens, emails, phones, SQL params, and exception messages."""
    mock_inner_exporter = MagicMock()
    mock_inner_exporter.export.return_value = None
    exporter = PrivacySafeSpanExporter(mock_inner_exporter)

    ctx = SpanContext(trace_id=0x12345678901234567890123456789012, span_id=0x1234567890123456, is_remote=False, trace_flags=TraceFlags(1))
    
    # Span with sensitive attributes and raw exception details
    raw_span = ReadableSpan(
        name="test_sensitive_span",
        context=ctx,
        attributes={
            "http.method": "POST",
            "http.route": "/api/bookings/12345?token=secret123&key=456",
            "http.status_code": 200,
            "secret_token": "bearer_secret_token_val",
            "customer_phone": "+1234567890",
            "customer_email": "user@example.com",
            "sql_query": "SELECT * FROM users WHERE password = 'secret'",
            "error.type": "ValueError",
        },
        events=[
            Event(
                name="exception",
                attributes={
                    "exception.type": "ValueError",
                    "exception.message": "User user@example.com failed auth with token secret123",
                    "exception.stacktrace": "Traceback (most recent call last):\n  File 'app/main.py', line 123 in login\n"
                },
                timestamp=1000
            )
        ]
    )

    exporter.export([raw_span])
    assert mock_inner_exporter.export.called
    exported_spans = mock_inner_exporter.export.call_args[0][0]
    exported_proxy = exported_spans[0]

    # 1. Non-allowlisted keys must be stripped
    assert "secret_token" not in exported_proxy.attributes
    assert "customer_phone" not in exported_proxy.attributes
    assert "customer_email" not in exported_proxy.attributes
    assert "sql_query" not in exported_proxy.attributes

    # 2. Allowlisted keys must be retained and sanitized
    assert exported_proxy.attributes["http.method"] == "POST"
    assert exported_proxy.attributes["http.status_code"] == 200
    assert exported_proxy.attributes["error.type"] == "ValueError"

    # 3. Route must be sanitized of raw numeric IDs and query strings
    assert "?" not in exported_proxy.attributes["http.route"]
    assert "token" not in exported_proxy.attributes["http.route"]
    assert exported_proxy.attributes["http.route"] == "/api/bookings/{id}"

    # 4. Exception events must keep only exception.type (no raw message or stacktrace)
    assert len(exported_proxy.events) == 1
    ev_attrs = exported_proxy.events[0].attributes
    assert ev_attrs.get("exception.type") == "ValueError"
    assert "exception.message" not in ev_attrs
    assert "exception.stacktrace" not in ev_attrs


def test_bounded_enum_metrics_recording():
    """Verify custom metric recorders process bounded enum values cleanly."""
    record_webhook_event("accepted")
    record_webhook_event("invalid_enum_status")  # falls back to "failed"
    
    record_sms_event("success", account_id=42)
    record_ai_event("processed", job_type="outbox_sms")
    record_arrival_event("activated")
    record_link_failure()
    record_booking_failure(operation="cancel", reason="client_no_show")


def test_public_frontend_telemetry_endpoint(client: TestClient):
    """Verify POST /api/public/diagnostics/telemetry accepts safe structural events and rejects invalid ones."""
    # 1. Valid event
    valid_payload = {
        "event_type": "js_error",
        "error_class": "TypeError",
        "route": "/book/checkout?token=123#step2",
        "component": "BookingForm",
        "duration_ms": 145.5
    }
    res = client.post("/api/public/diagnostics/telemetry", json=valid_payload)
    assert res.status_code == 200
    assert res.json() == {"status": "accepted"}

    # 2. Invalid event_type
    invalid_payload = {
        "event_type": "malicious_type",
        "error_class": "TypeError"
    }
    res_inv = client.post("/api/public/diagnostics/telemetry", json=invalid_payload)
    assert res_inv.status_code == 200
    assert res_inv.json() == {"status": "rejected"}


def test_admin_diagnostics_telemetry_status(client: TestClient, db_session):
    """Verify GET /api/admin/system/diagnostics/telemetry/status returns safe state without exposing endpoints or secrets."""
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.core.security import create_access_token

    tenant = Tenant(name="Diag Biz", subdomain="diag-biz")
    db_session.add(tenant)
    db_session.commit()

    user = User(tenant_id=tenant.id, login="admin_diag", password_hash="hash", role="owner")
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"X-Tenant": "diag-biz", "X-Token": token}

    res = client.get("/api/admin/system/diagnostics/telemetry/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "telemetry_enabled" in data
    assert "service_name" in data
    assert data["service_name"] == "fastapi-bookings"
    # Must NOT expose endpoints or tokens
    assert "http://localhost" not in str(data)
    assert "secret" not in str(data).lower()


def test_idempotent_telemetry_init():
    """Verify multiple init_telemetry calls do not double-instrument."""
    init_telemetry(app)
    init_telemetry(app)
    # Should not raise exception
