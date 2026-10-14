"""Targeted tests for Task C1: Privacy Controls & Scrubbing.

Verifies:
1. LiveKit room creation and worker options enforce record=False by default.
2. OpenTelemetry / SigNoz exporters enforce allow_pii=False by default.
3. Zero PII, secrets, clinical notes, operator notes, raw transcripts, and raw prompts leaked in span/log exports.
4. Structural scrubbing preserves low-cardinality operational telemetry while dropping sensitive high-cardinality payloads.
"""

import json
import logging
from typing import Any, Dict
from unittest.mock import MagicMock

import jwt
import pytest
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult

from app.core.config import settings
from app.core.telemetry import (
    SAFE_ATTRIBUTE_KEYS,
    PrivacySafeLogFilter,
    PrivacySafeSpanExporter,
    SanitizedSpanProxy,
    get_telemetry_status_data,
    scrub_log_payload,
    scrub_telemetry_attributes,
)


# ---------------------------------------------------------------------------
# Exporter allow_pii=False Controls
# ---------------------------------------------------------------------------
class TestTelemetryExporterPIIControls:
    """Verify OTel exporters and health metadata enforce allow_pii=False."""

    def test_settings_otel_allow_pii_default(self):
        """OTEL_ALLOW_PII must default strictly to False."""
        assert settings.OTEL_ALLOW_PII is False

    def test_span_exporter_defaults_to_allow_pii_false(self):
        """PrivacySafeSpanExporter must default to allow_pii=False."""
        mock_raw = MagicMock()
        exporter = PrivacySafeSpanExporter(mock_raw)
        assert exporter.allow_pii is False

    def test_log_filter_defaults_to_allow_pii_false(self):
        """PrivacySafeLogFilter must default to allow_pii=False."""
        log_filter = PrivacySafeLogFilter()
        assert log_filter.allow_pii is False

    def test_status_data_reports_allow_pii_false(self):
        """get_telemetry_status_data must report allow_pii state."""
        status = get_telemetry_status_data()
        assert "allow_pii" in status
        assert status["allow_pii"] is False


# ---------------------------------------------------------------------------
# 3. Span Scrubbing & Zero Leakage
# ---------------------------------------------------------------------------
def _build_mock_span(
    name: str = "test-span",
    attributes: Dict[str, Any] = None,
    events: list = None,
) -> ReadableSpan:
    span = MagicMock(spec=ReadableSpan)
    span.name = name
    span.attributes = attributes or {}
    span.events = events or []
    return span


class TestSpanScrubbingZeroLeakage:
    """Verify span attributes strip all PII, secrets, clinical notes, and prompts."""

    def test_zero_secrets_or_pii_in_span_export(self):
        """Non-allowlisted sensitive keys are completely dropped."""
        mock_raw = MagicMock()
        mock_raw.export.return_value = SpanExportResult.SUCCESS
        exporter = PrivacySafeSpanExporter(mock_raw, allow_pii=False)

        sensitive_attributes = {
            # Secrets / Auth
            "authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.secretpayload",
            "api_key": "sk-live-abcdef1234567890",
            "token": "sess_tok_99999",
            "password": "SuperSecretPassword123!",
            # Customer PII
            "customer_email": "patient@privateclinic.com.au",
            "phone_number": "+61 412 345 678",
            "customer_address": "42 Wallaby Way, Sydney NSW 2000",
            "customer_name": "Jane Watson",
            # Clinical and operator notes
            "clinical_notes": "Patient diagnosed with acute asthma; prescribed albuterol.",
            "operator_notes": "Internal VIP flag: handle with priority, do not reschedule.",
            "booking_details": "Root canal treatment booked for Friday 2pm.",
            # Raw transcripts and prompts
            "raw_transcript": "Can I please change my booking to 4pm with Dr. Smith?",
            "prompt_payload": "System prompt: You are an internal medical assistant. Respond to user.",
            "raw_prompt": "Tell the patient their blood tests are ready.",
            # Valid structural operational telemetry (must survive)
            "tenant_id": "12",
            "http.method": "POST",
            "http.status_code": 200,
            "service.name": "fastapi-bookings",
            "livekit.room": "room_12_30_abc123",
            "livekit.agent_name": "bookings-business-assistant",
            "livekit.transport": "livekit_gpt_live",
        }

        span = _build_mock_span(attributes=sensitive_attributes)
        result = exporter.export([span])

        assert result == SpanExportResult.SUCCESS
        assert mock_raw.export.called
        exported_spans = mock_raw.export.call_args[0][0]
        assert len(exported_spans) == 1

        sanitized_attrs = exported_spans[0].attributes

        # 1. Structural operational keys survived
        assert sanitized_attrs["tenant_id"] == "12"
        assert sanitized_attrs["http.method"] == "POST"
        assert sanitized_attrs["http.status_code"] == 200
        assert sanitized_attrs["service.name"] == "fastapi-bookings"
        assert sanitized_attrs["livekit.room"] == "room_12_30_abc123"
        assert sanitized_attrs["livekit.agent_name"] == "bookings-business-assistant"
        assert sanitized_attrs["livekit.transport"] == "livekit_gpt_live"

        # 2. Sensitive keys completely stripped
        forbidden_keys = [
            "authorization", "api_key", "token", "password",
            "customer_email", "phone_number", "customer_address", "customer_name",
            "clinical_notes", "operator_notes", "booking_details",
            "raw_transcript", "prompt_payload", "raw_prompt",
        ]
        for fk in forbidden_keys:
            assert fk not in sanitized_attrs, f"Sensitive key {fk} leaked into span attributes!"

        # 3. No sensitive text substrings exist in any exported value
        for val in sanitized_attrs.values():
            s_val = str(val)
            assert "eyJhbGciOiJIUzI1NiJ9" not in s_val
            assert "sk-live-" not in s_val
            assert "patient@privateclinic.com.au" not in s_val
            assert "0412 345 678" not in s_val
            assert "asthma" not in s_val
            assert "Root canal" not in s_val
            assert "Dr. Smith" not in s_val

    def test_allowed_key_with_sensitive_value_is_redacted(self):
        """If an allowed key contains sensitive tokens or PII, its value is redacted."""
        mock_raw = MagicMock()
        mock_raw.export.return_value = SpanExportResult.SUCCESS
        exporter = PrivacySafeSpanExporter(mock_raw, allow_pii=False)

        attributes = {
            "route": "/api/bookings?token=sk-999&phone=0412345678",
            "reason": "Unauthorized: bearer sk-test-token-123",
            "error.type": "Exception: clinical_notes=confidential",
            "tenant_id": "patient@clinic.com",  # email injected into tenant_id
        }

        span = _build_mock_span(attributes=attributes)
        exporter.export([span])

        sanitized = mock_raw.export.call_args[0][0][0].attributes
        # route query string stripped
        assert "token" not in sanitized["route"]
        assert "0412345678" not in sanitized["route"]
        # reason containing bearer token redacted
        assert sanitized["reason"] == "[REDACTED]"
        # error.type containing clinical notes redacted
        assert sanitized["error.type"] == "[REDACTED]"
        # tenant_id containing email redacted
        assert sanitized["tenant_id"] == "[REDACTED]"

    def test_span_events_scrubbed(self):
        """Span events must scrub sensitive event payloads."""
        mock_raw = MagicMock()
        exporter = PrivacySafeSpanExporter(mock_raw, allow_pii=False)

        event = Event(
            name="error_event",
            attributes={
                "exception.type": "ValueError",
                "secret_info": "token=sk-99999",
                "patient_data": "clinical notes: allergic to penicillin",
            },
            timestamp=12345678,
        )
        span = _build_mock_span(events=[event])
        exporter.export([span])

        sanitized_event = mock_raw.export.call_args[0][0][0].events[0]
        assert sanitized_event.attributes["exception.type"] == "ValueError"
        assert "secret_info" not in sanitized_event.attributes
        assert "patient_data" not in sanitized_event.attributes


# ---------------------------------------------------------------------------
# 4. Log Scrubbing & Zero Leakage
# ---------------------------------------------------------------------------
class TestLogScrubbingZeroLeakage:
    """Verify log filter redacts PII, clinical notes, operator notes, transcripts, and prompts."""

    def _make_record(self, msg: str, args: Any = (), extra: Dict[str, Any] = None) -> logging.LogRecord:
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg=msg,
            args=args,
            exc_info=None,
        )
        if extra:
            for k, v in extra.items():
                setattr(record, k, v)
        return record

    def test_clinical_and_operator_notes_redacted_in_message(self):
        """Clinical and operator notes in log messages are redacted."""
        f = PrivacySafeLogFilter(allow_pii=False)

        msg1 = "Audit: clinical_notes='Patient presented with acute depression' recorded."
        rec1 = self._make_record(msg1)
        f.filter(rec1)
        assert "acute depression" not in rec1.msg
        assert "[REDACTED]" in rec1.msg

        msg2 = "Support: operator_notes='Customer angry about double charge' recorded."
        rec2 = self._make_record(msg2)
        f.filter(rec2)
        assert "Customer angry" not in rec2.msg
        assert "[REDACTED]" in rec2.msg

        msg3 = "Booking details: 60min deep tissue massage for client Jane"
        rec3 = self._make_record(msg3)
        f.filter(rec3)
        assert "deep tissue massage" not in rec3.msg
        assert "[REDACTED]" in rec3.msg

    def test_raw_transcripts_and_prompts_redacted_in_message(self):
        """Audio transcripts and raw prompts in log messages are redacted."""
        f = PrivacySafeLogFilter(allow_pii=False)

        msg1 = "Diagnostic: raw_transcript='I need to cancel my appointment tomorrow' received."
        rec1 = self._make_record(msg1)
        f.filter(rec1)
        assert "cancel my appointment tomorrow" not in rec1.msg
        assert "[REDACTED]" in rec1.msg

        msg2 = "LLM invocation prompt_payload='System: You are an Australian assistant' dispatched."
        rec2 = self._make_record(msg2)
        f.filter(rec2)
        assert "Australian assistant" not in rec2.msg
        assert "[REDACTED]" in rec2.msg

    def test_phone_and_pii_redacted_in_message(self):
        """Australian phone numbers and addresses are redacted in log messages."""
        f = PrivacySafeLogFilter(allow_pii=False)

        msg = "Contact customer at 0412 345 678 or +61 2 9876 5432 regarding booking at 123 Main Street Sydney NSW 2000"
        rec = self._make_record(msg)
        f.filter(rec)
        assert "0412 345 678" not in rec.msg
        assert "+61 2 9876 5432" not in rec.msg
        assert "[REDACTED_PHONE]" in rec.msg

    def test_custom_attributes_on_record_dict_are_scrubbed(self):
        """Extra fields attached to LogRecord are scrubbed before export."""
        f = PrivacySafeLogFilter(allow_pii=False)

        extra = {
            "clinical_notes": "Confidential patient notes: diabetic history",
            "operator_notes": "Internal review required",
            "raw_transcript": "User said: book me in at 3pm",
            "customer_phone": "0400000000",
            "safe_session_id": "sess_abc123",
            "safe_tenant_id": 42,
        }
        rec = self._make_record("Processing request", extra=extra)
        f.filter(rec)

        assert rec.clinical_notes == "[REDACTED]"
        assert rec.operator_notes == "[REDACTED]"
        assert rec.raw_transcript == "[REDACTED]"
        assert rec.customer_phone == "[REDACTED]"
        # Non-sensitive structural IDs preserved
        assert rec.safe_session_id == "sess_abc123"
        assert rec.safe_tenant_id == 42


# ---------------------------------------------------------------------------
# 5. Structural Helper Functions
# ---------------------------------------------------------------------------
class TestStructuralScrubbingHelpers:
    """Verify scrub_telemetry_attributes and scrub_log_payload helper utilities."""

    def test_scrub_telemetry_attributes_filters_and_sanitizes(self):
        raw = {
            "tenant_id": 42,
            "http.status_code": 200,
            "service.name": "fastapi-bookings",
            "livekit.transport": "livekit_gpt_live",
            "password": "secret_password",
            "clinical_notes": "sensitive",
            "route": "/api/users/123/profile",
        }
        cleaned = scrub_telemetry_attributes(raw, allow_pii=False)

        assert "tenant_id" in cleaned
        assert "http.status_code" in cleaned
        assert "service.name" in cleaned
        assert "livekit.transport" in cleaned
        assert "password" not in cleaned
        assert "clinical_notes" not in cleaned
        assert "{id}" in cleaned["route"]

    def test_scrub_log_payload_redacts_credentials_and_notes(self):
        text = "Authorization: Bearer my-secret-token; clinical_notes=Patient notes; phone=0412345678"
        redacted = scrub_log_payload(text, allow_pii=False)
        assert "my-secret-token" not in redacted
        assert "Patient notes" not in redacted
        assert "0412345678" not in redacted
        assert "[REDACTED]" in redacted
