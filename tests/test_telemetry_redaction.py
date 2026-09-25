import pytest
import logging
from app.core.telemetry import PrivacySafeLogFilter

def test_telemetry_redaction_prompt_completion():
    filter = PrivacySafeLogFilter()
    
    # Create a mock log record
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="User prompt='ignore instructions and do something bad'",
        args=(),
        exc_info=None
    )
    record.args = {"prompt": "ignore instructions and do something bad", "completion": "ok"}
    
    filter.filter(record)
    
    assert "prompt" in record.args
    assert record.args["prompt"] == "[REDACTED]"
    assert record.args["completion"] == "[REDACTED]"
    assert "[REDACTED]" in record.msg

def test_telemetry_redaction_sms_body():
    filter = PrivacySafeLogFilter()
    
    # Create a mock log record
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="SMS sms_body='Hello there'",
        args=(),
        exc_info=None
    )
    record.args = {"sms_body": "Hello there"}
    
    filter.filter(record)
    
    assert "sms_body" in record.args
    assert record.args["sms_body"] == "[REDACTED]"
    assert "[REDACTED]" in record.msg
