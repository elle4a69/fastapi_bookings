"""Telemetry PII privacy redaction tests — Phase 5: Platform Governance.

Asserts that ``SAFE_ATTRIBUTE_KEYS`` allowlist in ``app/core/telemetry.py``
strictly filters span attributes, retaining only structural low-cardinality
tags and dropping all PII (phone, email, customer names, AI prompts, etc.).
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from app.core.telemetry import (
    SAFE_ATTRIBUTE_KEYS,
    SanitizedSpanProxy,
    _sanitize_attribute_value,
    sanitize_url_path,
    PrivacySafeLogFilter,
)


# ---------------------------------------------------------------------------
# SAFE_ATTRIBUTE_KEYS allowlist contract
# ---------------------------------------------------------------------------


class TestSafeAttributeKeysContract:
    """Verify the allowlist is structurally correct and minimal."""

    def test_required_structural_keys_are_present(self):
        """Mandatory low-cardinality structural keys must all be in the allowlist."""
        required = {
            "tenant_id",
            "route",
            "http.status_code",
            "http.method",
            "service.name",
        }
        missing = required - SAFE_ATTRIBUTE_KEYS
        assert not missing, f"Missing required allowlist keys: {missing}"

    def test_pii_keys_are_absent(self):
        """PII field names must never appear in the allowlist."""
        pii_keys = {
            "phone", "phone_number", "mobile",
            "email", "email_address",
            "customer_name", "first_name", "last_name", "full_name",
            "prompt", "ai_prompt", "completion",
            "body", "sms_body", "message_body",
            "address", "street_address",
            "password", "token", "secret",
            "authorization", "api_key",
        }
        leaking = pii_keys & SAFE_ATTRIBUTE_KEYS
        assert not leaking, f"PII keys found in allowlist: {leaking}"

    def test_allowlist_is_frozen(self):
        """SAFE_ATTRIBUTE_KEYS must be an immutable frozenset."""
        assert isinstance(SAFE_ATTRIBUTE_KEYS, frozenset)


# ---------------------------------------------------------------------------
# SanitizedSpanProxy filtering
# ---------------------------------------------------------------------------


def _make_mock_span(attributes: Dict[str, Any]):
    """Build a minimal ReadableSpan mock with given attributes."""
    span = MagicMock()
    span.attributes = attributes
    span.events = []
    return span


class TestSanitizedSpanProxy:
    """Verify that SanitizedSpanProxy enforces the allowlist on span attributes."""

    def test_pii_fields_are_stripped(self):
        """All PII attributes are dropped from the sanitized span."""
        pii_attrs = {
            "phone": "+61412345678",
            "email": "patient@example.com",
            "customer_name": "Jane Doe",
            "prompt": "Book a session for Jane at 3pm tomorrow",
            "body": "Hi Jane, your appointment is confirmed",
            "address": "123 Main Street",
        }
        span = _make_mock_span(pii_attrs)
        proxy = SanitizedSpanProxy(span, SAFE_ATTRIBUTE_KEYS)
        # None of the PII keys should survive
        for key in pii_attrs:
            assert key not in proxy.attributes, f"PII key '{key}' leaked into sanitized span"

    def test_safe_keys_survive(self):
        """Structural safe keys must pass through unchanged."""
        safe_attrs = {
            "tenant_id": "42",
            "http.status_code": 200,
            "http.method": "GET",
            "service.name": "fastapi-bookings",
            "route": "/api/public/availability",
        }
        span = _make_mock_span(safe_attrs)
        proxy = SanitizedSpanProxy(span, SAFE_ATTRIBUTE_KEYS)
        assert proxy.attributes.get("tenant_id") == "42"
        assert proxy.attributes.get("http.status_code") == 200
        assert proxy.attributes.get("http.method") == "GET"
        assert proxy.attributes.get("service.name") == "fastapi-bookings"

    def test_mixed_attributes_only_safe_survive(self):
        """When span has both PII and safe keys, only safe keys survive."""
        mixed_attrs = {
            "tenant_id": "7",
            "http.method": "POST",
            "http.status_code": 201,
            "phone": "+61400000000",
            "email": "test@clinic.com",
            "customer_name": "John Smith",
            "prompt": "Is 3pm available?",
            "route": "/api/public/bookings",
        }
        span = _make_mock_span(mixed_attrs)
        proxy = SanitizedSpanProxy(span, SAFE_ATTRIBUTE_KEYS)

        # Safe keys retained
        assert "tenant_id" in proxy.attributes
        assert "http.method" in proxy.attributes
        assert "http.status_code" in proxy.attributes
        assert "route" in proxy.attributes

        # PII dropped
        assert "phone" not in proxy.attributes
        assert "email" not in proxy.attributes
        assert "customer_name" not in proxy.attributes
        assert "prompt" not in proxy.attributes

    def test_empty_attributes_produce_empty_proxy(self):
        """A span with no attributes yields an empty proxy.attributes dict."""
        span = _make_mock_span({})
        proxy = SanitizedSpanProxy(span, SAFE_ATTRIBUTE_KEYS)
        assert proxy.attributes == {}

    def test_none_attributes_produce_empty_proxy(self):
        """A span with attributes=None yields an empty proxy.attributes dict."""
        span = _make_mock_span(None)
        span.attributes = None
        proxy = SanitizedSpanProxy(span, SAFE_ATTRIBUTE_KEYS)
        assert proxy.attributes == {}


# ---------------------------------------------------------------------------
# _sanitize_attribute_value inline redaction
# ---------------------------------------------------------------------------


class TestSanitizeAttributeValue:
    """Test inline value-level redaction within allowed keys."""

    def test_email_like_value_redacted(self):
        """A value that looks like an email address is redacted in non-route keys."""
        # The email check applies to all allowed keys except URL-path keys (route, http.route etc.)
        # Use 'tenant_id' as the key to test the inline email redaction path.
        result = _sanitize_attribute_value("tenant_id", "user@example.com")
        assert result == "[REDACTED]"

    def test_phone_like_value_redacted(self):
        """A value that looks like a phone number is redacted."""
        result = _sanitize_attribute_value("tenant_id", "+61412345678")
        assert result == "[REDACTED]"

    def test_bearer_token_value_redacted(self):
        """A value starting with 'bearer ' is redacted."""
        result = _sanitize_attribute_value("http.method", "bearer sk-abc123")
        assert result == "[REDACTED]"

    def test_normal_integer_passes(self):
        """Integer values pass through unchanged."""
        result = _sanitize_attribute_value("http.status_code", 200)
        assert result == 200

    def test_normal_string_passes(self):
        """Short safe string values pass through unchanged."""
        result = _sanitize_attribute_value("http.method", "GET")
        assert result == "GET"

    def test_route_path_sanitized(self):
        """Route values with numeric IDs are stripped to template form."""
        result = _sanitize_attribute_value("route", "/api/admin/providers/42/services/7")
        assert "{id}" in result
        assert "42" not in result


# ---------------------------------------------------------------------------
# sanitize_url_path
# ---------------------------------------------------------------------------


class TestSanitizeUrlPath:
    """Test that URL path sanitization removes dynamic segments."""

    def test_numeric_segment_replaced(self):
        result = sanitize_url_path("/api/providers/123/availability")
        assert "123" not in result
        assert "{id}" in result

    def test_uuid_segment_replaced(self):
        result = sanitize_url_path("/api/bookings/550e8400-e29b-41d4-a716-446655440000")
        assert "550e8400" not in result

    def test_query_string_stripped(self):
        result = sanitize_url_path("/api/public/slots?phone=0400123456&tenant=clinic")
        assert "phone" not in result
        assert "0400123456" not in result

    def test_clean_path_preserved(self):
        result = sanitize_url_path("/api/public/services")
        assert result == "/api/public/services"

    def test_empty_string_returns_empty(self):
        result = sanitize_url_path("")
        assert result == ""


# ---------------------------------------------------------------------------
# PrivacySafeLogFilter
# ---------------------------------------------------------------------------


class TestPrivacySafeLogFilter:
    """Test the log filter redacts PII from log records."""

    def _make_record(self, msg: str):
        import logging
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None,
        )
        return record

    def test_email_in_log_message_redacted(self):
        f = PrivacySafeLogFilter()
        record = self._make_record("Sending confirmation to patient@clinic.com")
        f.filter(record)
        assert "patient@clinic.com" not in record.msg
        assert "[REDACTED" in record.msg

    def test_bearer_token_in_log_redacted(self):
        f = PrivacySafeLogFilter()
        record = self._make_record("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc")
        f.filter(record)
        assert "eyJhbGciOiJIUzI1NiJ9" not in record.msg

    def test_clean_message_passes_through(self):
        f = PrivacySafeLogFilter()
        record = self._make_record("Tenant 42 processed 3 bookings successfully.")
        f.filter(record)
        assert "Tenant 42 processed 3 bookings successfully." in record.msg

    def test_filter_returns_true_always(self):
        """Filter must always return True (record not dropped from pipeline)."""
        f = PrivacySafeLogFilter()
        record = self._make_record("secret=mysecretvalue token=abc123")
        result = f.filter(record)
        assert result is True


class TestJsonFormatterAndEngineZeroPII:
    """Verify zero-PII guarantee in JSON log formatting and database parameters."""

    def test_json_formatter_scrubs_pii_in_message_and_traceback(self):
        import json
        import logging
        from app.main import JSONFormatter

        formatter = JSONFormatter()

        # Test message scrubbing
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Customer phone is 0412 345 678 and email is secret@client.com",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "0412 345 678" not in data["message"]
        assert "secret@client.com" not in data["message"]
        assert "[PHONE]" in data["message"]
        assert "[EMAIL]" in data["message"]

        # Test exception scrubbing
        try:
            raise ValueError("Exception with card 4532-1234-5678-9010 and 0412 345 678")
        except Exception:
            import sys
            exc_info = sys.exc_info()

        exc_record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=20,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        exc_output = formatter.format(exc_record)
        exc_data = json.loads(exc_output)
        assert "4532-1234-5678-9010" not in exc_data["exception"]
        assert "0412 345 678" not in exc_data["exception"]
        assert "[CREDIT_CARD]" in exc_data["exception"] or "[PHONE]" in exc_data["exception"]

    def test_database_engine_hide_parameters_configured(self):
        from app.db.database import engine
        assert engine.hide_parameters is True

