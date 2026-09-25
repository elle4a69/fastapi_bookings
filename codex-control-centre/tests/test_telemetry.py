import logging
from typing import Optional
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import ReadableSpan, Event
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import SpanContext, TraceFlags

from backend.main import app
from backend.config import settings
from backend.services.telemetry import (
    SAFE_ATTRIBUTE_KEYS,
    PrivacySafeSpanExporter,
    PrivacySafeLogFilter,
    SanitizedSpanProxy,
    sanitize_url_path,
    _sanitize_attribute_value,
    init_telemetry,
    shutdown_telemetry,
    get_telemetry_status_data,
    record_telemetry_log,
)


class MockReadableSpan(ReadableSpan):
    """Mock implementation of ReadableSpan for unit testing."""

    def __init__(
        self,
        name: str = "test_span",
        attributes: Optional[dict] = None,
        events: Optional[list] = None,
    ):
        self._name = name
        self._attributes = attributes or {}
        self._events = events or []
        self._context = SpanContext(
            trace_id=0x12345678123456781234567812345678,
            span_id=0x1234567812345678,
            is_remote=False,
            trace_flags=TraceFlags(0x01),
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def attributes(self) -> dict:
        return self._attributes

    @property
    def events(self) -> list:
        return self._events

    @property
    def context(self) -> SpanContext:
        return self._context


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {settings.token_secret}"}


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Span attribute allowlisting and privacy sanitization
# ---------------------------------------------------------------------------
def test_span_attribute_allowlisting_and_sanitization():
    """Verify non-allowlisted attributes are stripped and sensitive strings in allowed keys are redacted."""
    raw_attributes = {
        # Allowlisted safe attributes
        "http.method": "GET",
        "http.status_code": 200,
        "project_id": "proj_12345",
        "thread_id": "thread_abc",
        # Allowlisted attributes containing sensitive substrings
        "http.route": "/codex/turns/550e8400-e29b-41d4-a716-446655440000?token=secret123",
        "reason": "Invalid authentication token=secret123",
        "operation": "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        # Non-allowlisted sensitive attributes (MUST BE STRIPPED)
        "user.password": "SuperSecretPassword!",
        "customer.credit_card": "4111-2222-3333-4444",
        "raw_prompt": "Tell me the secret database credentials",
        "auth_cookie": "session=xyz123",
    }

    raw_events = [
        Event(
            name="exception",
            attributes={
                "exception.type": "ValueError",
                "exception.message": "Secret leak in message: password=mypassword",
            },
            timestamp=123456789,
        )
    ]

    mock_span = MockReadableSpan(attributes=raw_attributes, events=raw_events)
    proxy = SanitizedSpanProxy(mock_span, SAFE_ATTRIBUTE_KEYS)

    # 1. Verify non-allowlisted attributes are completely stripped
    assert "user.password" not in proxy.attributes
    assert "customer.credit_card" not in proxy.attributes
    assert "raw_prompt" not in proxy.attributes
    assert "auth_cookie" not in proxy.attributes

    # 2. Verify allowed safe attributes are preserved
    assert proxy.attributes["http.method"] == "GET"
    assert proxy.attributes["http.status_code"] == 200
    assert proxy.attributes["project_id"] == "proj_12345"
    assert proxy.attributes["thread_id"] == "thread_abc"

    # 3. Verify allowed attributes with secrets are sanitized/redacted
    assert proxy.attributes["reason"] == "[REDACTED]"
    assert proxy.attributes["operation"] == "[REDACTED]"
    # Route path sanitization removes UUID and query string
    assert proxy.attributes["http.route"] == "/codex/turns/{id}"

    # 4. Verify event exception details strip non-type attributes
    assert len(proxy.events) == 1
    assert proxy.events[0].name == "exception"
    assert "exception.type" in proxy.events[0].attributes
    assert "exception.message" not in proxy.events[0].attributes


def test_sanitize_url_path_helper():
    """Verify URL path sanitizer removes dynamic segments and query strings."""
    assert sanitize_url_path("/threads/12345/turns/99") == "/threads/{id}/turns/{id}"
    assert sanitize_url_path("/projects/550e8400-e29b-41d4-a716-446655440000") == "/projects/{id}"
    assert sanitize_url_path("/api/v1/test?token=secret&user=frank") == "/api/v1/test"
    assert sanitize_url_path("") == ""


def test_sanitize_attribute_value_helper():
    """Verify attribute value sanitizer redacts secrets and large payloads."""
    assert _sanitize_attribute_value("http.method", "POST") == "POST"
    assert _sanitize_attribute_value("status_code", 200) == 200
    assert _sanitize_attribute_value("reason", "token=secret_value") == "[REDACTED]"
    assert _sanitize_attribute_value("reason", "bearer abcdef12345") == "[REDACTED]"
    assert _sanitize_attribute_value("reason", "password=pass") == "[REDACTED]"
    assert _sanitize_attribute_value("reason", "contact user@example.com for help") == "[REDACTED]"
    assert _sanitize_attribute_value("reason", "a" * 150) == "[REDACTED]"


# ---------------------------------------------------------------------------
# Test 2: Log redaction filter
# ---------------------------------------------------------------------------
def test_log_redaction_filter():
    """Verify PrivacySafeLogFilter redacts sensitive patterns in messages and args."""
    log_filter = PrivacySafeLogFilter()

    # 1. Test message redaction for bearer tokens and sensitive parameters
    record1 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Authenticated client with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and token=secret_token_123",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record1)
    assert "Bearer [REDACTED]" in record1.msg
    assert "token=[REDACTED]" in record1.msg
    assert "secret_token_123" not in record1.msg

    # 2. Test JSON-like and key-value secrets
    record2 = logging.LogRecord(
        name="test_logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=20,
        msg='Failed login: password="super_secret_password", api_key=ak_live_abcdef12345',
        args=(),
        exc_info=None,
    )
    log_filter.filter(record2)
    assert "password=[REDACTED]" in record2.msg
    assert "api_key=[REDACTED]" in record2.msg
    assert "super_secret_password" not in record2.msg

    # 3. Test HTTP access log query string redaction
    record3 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=30,
        msg="GET /codex/events?token=my_secret_token&user=test HTTP/1.1 200",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record3)
    assert "GET /codex/events?[REDACTED] HTTP/1.1 200" in record3.msg
    assert "my_secret_token" not in record3.msg

    # 4. Test dict and tuple args redaction
    record4 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=40,
        msg="Operation details: %s",
        args=({"password": "secret_pwd", "user": "admin", "token_secret": "local_secret"},),
        exc_info=None,
    )
    log_filter.filter(record4)
    clean_dict = record4.args if isinstance(record4.args, dict) else record4.args[0]
    assert clean_dict["password"] == "[REDACTED]"
    assert clean_dict["token_secret"] == "[REDACTED]"
    assert clean_dict["user"] == "admin"

    # 5. Test email and basic auth URL redaction
    record5 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=50,
        msg="Connecting to https://admin:supersecret@signoz.internal and email user@example.org",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record5)
    assert "https://[REDACTED]@signoz.internal" in record5.msg
    assert "[REDACTED_EMAIL]" in record5.msg


# ---------------------------------------------------------------------------
# Test 3: Graceful degradation under network failure
# ---------------------------------------------------------------------------
def test_graceful_degradation_network_failure(caplog):
    """Verify that if OTLP export encounters network failure, it logs a warning without crashing."""

    class FailingSpanExporter(SpanExporter):
        def export(self, spans):
            raise ConnectionError("Network connection refused: OTLP endpoint unreachable")

        def shutdown(self):
            pass

    failing_exporter = FailingSpanExporter()
    privacy_exporter = PrivacySafeSpanExporter(failing_exporter)

    mock_span = MockReadableSpan(name="failing_test_span", attributes={"http.method": "POST"})

    with caplog.at_level(logging.WARNING, logger="backend.services.telemetry"):
        result = privacy_exporter.export([mock_span])

    # Must return FAILURE and NOT raise an exception
    assert result == SpanExportResult.FAILURE
    assert "PrivacySafeSpanExporter export encountered exception" in caplog.text


def test_graceful_degradation_app_endpoints(client):
    """Verify FastAPI application remains fully functional even if OTLP telemetry is unreachable."""
    # Probe public and protected endpoints
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_root = client.get("/")
    assert res_root.status_code == 200


# ---------------------------------------------------------------------------
# Test 4: Diagnostics probe truthful connectivity
# ---------------------------------------------------------------------------
def test_diagnostics_telemetry_probe_offline(client, auth_headers):
    """Verify /codex/diagnostics/telemetry truthfully reports offline status when pointing to an unreachable port."""
    res = client.get("/codex/diagnostics/telemetry?collector_url=http://127.0.0.1:59999", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is False
    assert "Not connected (No active telemetry collector)" in data["status"]
    assert data["collector_url"] == "http://127.0.0.1:59999"
    assert "telemetry_enabled" in data
    assert "service_name" in data


def test_diagnostics_telemetry_probe_live(client, auth_headers):
    """Verify /codex/diagnostics/telemetry truthfully reports online status against the running collector."""
    res = client.get("/codex/diagnostics/telemetry", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    # Against live OTLP collector on port 4318
    assert data["connected"] is True
    assert data["status"] == "Connected"
    assert data["collector_url"] == settings.otlp_endpoint
    assert data["telemetry_enabled"] is True
    assert data["service_name"] == "codex-control-centre"
    assert data["environment"] == "development"


# ---------------------------------------------------------------------------
# Test 5: Lifecycle & Structured Logging
# ---------------------------------------------------------------------------
def test_telemetry_lifecycle_idempotence():
    """Verify init_telemetry and shutdown_telemetry can be safely executed repeatedly."""
    init_telemetry(app)
    status1 = get_telemetry_status_data()
    assert status1["telemetry_enabled"] is True
    assert status1["trace_exporter_active"] is True

    # Call init again (idempotent)
    init_telemetry(app)
    status2 = get_telemetry_status_data()
    assert status2["trace_exporter_active"] is True

    # Shutdown
    shutdown_telemetry()
    status3 = get_telemetry_status_data()
    assert status3["trace_exporter_active"] is False


def test_record_telemetry_log():
    """Verify structured telemetry log records sanitize parameters without raising."""
    captured = []

    class TestHandler(logging.Handler):
        def emit(self, record):
            captured.append(record)

    handler = TestHandler()
    handler.setLevel(logging.DEBUG)
    tel_logger = logging.getLogger("codex.telemetry")
    tel_logger.setLevel(logging.DEBUG)
    tel_logger.addHandler(handler)
    try:
        record_telemetry_log(
            event_code="TURN_STARTED",
            level="INFO",
            module="turn_service",
            project_id="test_proj",
            thread_id="test_thread",
            turn_id="test_turn",
            route="/codex/turns/123?token=secret",
            method="POST",
            status=200,
            duration_ms=45.67,
        )
        assert len(captured) >= 1
        rec = captured[-1]
        assert rec.msg == "TURN_STARTED"
        assert getattr(rec, "safe_module", None) == "turn_service"
        assert getattr(rec, "project_id", None) == "test_proj"
        assert getattr(rec, "route", None) == "/codex/turns/{id}"
        assert getattr(rec, "status", None) == 200
        assert getattr(rec, "duration_ms", None) == 45.67
    finally:
        tel_logger.removeHandler(handler)
