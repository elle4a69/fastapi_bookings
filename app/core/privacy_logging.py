"""Process-wide privacy boundary for HTTP access and client logs.

Protected records are neutralized by the record factory before any handler can
format their message.  A handler filter then runs after ``extra`` has been
merged, removes arbitrary attributes, and publishes only bounded structural
HTTP fields.
"""

from __future__ import annotations

import inspect
import json
import logging
import traceback
from typing import Final

from opentelemetry import trace

try:
    from opentelemetry.instrumentation.logging.handler import (
        LoggingHandler as _OpenTelemetryLoggingHandler,
    )
except ImportError:
    from opentelemetry.sdk._logs import LoggingHandler as _OpenTelemetryLoggingHandler


SAFE_HTTP_METHODS: Final = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
)
SAFE_DURATION_LABELS: Final = frozenset(
    {"lt_10ms", "lt_50ms", "lt_250ms", "lt_1s", "lt_5s", "gte_5s"}
)
_PROTECTED_NAMESPACES: Final = (
    "app.access",
    "uvicorn.access",
    "httpx",
    "httpcore",
)
_STANDARD_LOG_RECORD_FIELDS: Final = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
)
_PRIVATE_STRUCTURE_FIELD: Final = "_fastapi_bookings_privacy_structure"


def logger_is_in_namespace(logger_name: str, namespace: str) -> bool:
    """Match one logger namespace without matching lookalike prefixes."""

    normalized = logger_name.lower()
    return normalized == namespace or normalized.startswith(f"{namespace}.")


def protected_logger_family(logger_name: str) -> str | None:
    """Return the exact protected family for a logger or ``None``."""

    for namespace in _PROTECTED_NAMESPACES:
        if logger_is_in_namespace(logger_name, namespace):
            return namespace
    return None


def safe_http_method(value) -> str:
    method = value.upper() if isinstance(value, str) else ""
    return method if method in SAFE_HTTP_METHODS else "OTHER"


def safe_http_status(value) -> int:
    return value if isinstance(value, int) and 100 <= value <= 599 else 0


def safe_route_template(value) -> str:
    """Return only a bounded code-owned route template, never a raw URL."""

    if value in {"<unmatched>", "<external>"}:
        return value
    if not isinstance(value, str) or not value.startswith("/") or len(value) > 200:
        return "<unmatched>"
    if "?" in value or "#" in value:
        return "<unmatched>"
    if not all(character.isalnum() or character in "/_-.:{}" for character in value):
        return "<unmatched>"
    return value


def is_safe_request_id(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _structure_from_record(record: logging.LogRecord) -> tuple:
    family = protected_logger_family(record.name)
    if family is None:
        return ()

    args = record.args if isinstance(record.args, tuple) else ()
    method = "OTHER"
    status_code = 0
    event = "http_access_record"
    route = "<external>"
    duration = None
    request_id = None

    if family == "app.access":
        event = "http_request_completed"
        route = "<unmatched>"
        if len(args) >= 5:
            method = safe_http_method(args[0])
            route = safe_route_template(args[1])
            status_code = safe_http_status(args[2])
            duration = (
                args[3]
                if isinstance(args[3], str) and args[3] in SAFE_DURATION_LABELS
                else None
            )
            request_id = args[4] if is_safe_request_id(args[4]) else None
    elif family == "uvicorn.access":
        event = "http_server_access"
        route = "<unmatched>"
        if len(args) >= 5:
            method = safe_http_method(args[1])
            status_code = safe_http_status(args[4])
    elif family == "httpx":
        event = "http_client_access"
        if len(args) >= 4:
            method = safe_http_method(args[0])
            status_code = safe_http_status(args[3])
    else:
        event = "http_client_transport"

    return event, method, route, status_code, duration, request_id


def sanitize_record_factory_stage(record: logging.LogRecord) -> None:
    """Neutralize protected payloads without creating ``extra`` collisions."""

    family = protected_logger_family(record.name)
    structure = _structure_from_record(record)
    if family is None or not structure:
        return
    # The factory runs before ``extra`` is merged. A caller therefore cannot
    # replace this private field: logging rejects a colliding ``extra`` key.
    # The handler filter retains it for every configured handler but the OTel
    # translation below never exports it.
    setattr(record, _PRIVATE_STRUCTURE_FIELD, structure)
    record.name = family
    record.msg = structure[0]
    record.args = ()
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None


def install_privacy_safe_record_factory() -> None:
    """Install an idempotent, process-local protected-record factory."""

    current_factory = logging.getLogRecordFactory()
    if getattr(current_factory, "privacy_safe_access", False):
        return

    def privacy_safe_factory(*args, **kwargs):
        record = current_factory(*args, **kwargs)
        sanitize_record_factory_stage(record)
        return record

    setattr(privacy_safe_factory, "privacy_safe_access", True)
    logging.setLogRecordFactory(privacy_safe_factory)


def _private_structure(record: logging.LogRecord) -> tuple:
    """Return only factory/filter-owned structure, never caller public extras."""

    structure = getattr(record, _PRIVATE_STRUCTURE_FIELD, ())
    if not isinstance(structure, tuple) or len(structure) != 6:
        return ()
    return structure


class PrivacySafeAccessFilter(logging.Filter):
    """Make the protected record allowlist final after caller ``extra`` merge."""

    def filter(self, record: logging.LogRecord) -> bool:
        family = protected_logger_family(record.name)
        if family is None:
            return True

        structure = _private_structure(record)
        if not structure:
            sanitize_record_factory_stage(record)
            structure = _private_structure(record)
        if not structure:
            # A protected record without trustworthy private structure is
            # still neutralized rather than passed through with public extras.
            structure = (
                "http_access_record",
                "OTHER",
                (
                    "<external>"
                    if family in {"httpx", "httpcore"}
                    else "<unmatched>"
                ),
                0,
                None,
                None,
            )
            setattr(record, _PRIVATE_STRUCTURE_FIELD, structure)

        for key in tuple(record.__dict__):
            if (
                key not in _STANDARD_LOG_RECORD_FIELDS
                and key != _PRIVATE_STRUCTURE_FIELD
            ):
                del record.__dict__[key]

        event, method, route, status_code, duration, request_id = structure
        record.name = family
        record.msg = event
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        record.http_method = safe_http_method(method)
        record.http_route = safe_route_template(route)
        record.http_status = safe_http_status(status_code)
        if duration in SAFE_DURATION_LABELS:
            record.duration_bucket = duration
        if is_safe_request_id(request_id):
            record.request_id = request_id
        return True


def _protected_otel_attributes(record: logging.LogRecord) -> dict[str, object]:
    """Build the exact protected-record attribute allowlist."""

    structure = _private_structure(record)
    if not structure:
        return {}
    _event, method, route, status_code, duration, request_id = structure
    attributes: dict[str, object] = {
        "http_method": safe_http_method(method),
        "http_route": safe_route_template(route),
        "http_status": safe_http_status(status_code),
    }
    if duration in SAFE_DURATION_LABELS:
        attributes["duration_bucket"] = duration
    if is_safe_request_id(request_id):
        attributes["request_id"] = request_id
    return attributes


class PrivacySafeOTelLoggingHandler(_OpenTelemetryLoggingHandler):
    """Translate protected records with an exact fail-closed attribute set."""

    def __init__(self, *args, **kwargs):
        translator = getattr(_OpenTelemetryLoggingHandler, "_get_attributes", None)
        parameters = (
            tuple(inspect.signature(translator).parameters)
            if callable(translator)
            else ()
        )
        if parameters != ("record",):
            raise RuntimeError("Unsupported OpenTelemetry logging handler API.")
        super().__init__(*args, **kwargs)

    @staticmethod
    def _get_attributes(record: logging.LogRecord):
        if protected_logger_family(record.name) is None:
            return _OpenTelemetryLoggingHandler._get_attributes(record)
        try:
            return _protected_otel_attributes(record)
        except Exception:
            # SDK/export translation must never recover caller extras or code
            # location fields after a protected record has been recognized.
            return {}


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        current_span = trace.get_current_span()
        if current_span and current_span.get_span_context().is_valid:
            ctx = current_span.get_span_context()
            log_data["trace_id"] = f"{ctx.trace_id:032x}"
            log_data["span_id"] = f"{ctx.span_id:016x}"
        if record.exc_info:
            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))
        if protected_logger_family(record.name) is not None:
            log_data["http_method"] = safe_http_method(
                getattr(record, "http_method", None)
            )
            log_data["http_route"] = safe_route_template(
                getattr(record, "http_route", None)
            )
            log_data["http_status"] = safe_http_status(
                getattr(record, "http_status", None)
            )
            duration = getattr(record, "duration_bucket", None)
            if duration in SAFE_DURATION_LABELS:
                log_data["duration_bucket"] = duration
            request_id = getattr(record, "request_id", None)
            if is_safe_request_id(request_id):
                log_data["request_id"] = request_id
        return json.dumps(log_data)


def configure_privacy_safe_logging(*, include_server_loggers: bool) -> None:
    """Configure the process console boundary and install the record factory."""

    install_privacy_safe_record_factory()
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.addFilter(PrivacySafeAccessFilter())
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    if not include_server_loggers:
        return
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(name)
        for existing_handler in logger.handlers[:]:
            logger.removeHandler(existing_handler)
        logger.addHandler(handler)
        logger.propagate = False


__all__ = [
    "JSONFormatter",
    "PrivacySafeAccessFilter",
    "PrivacySafeOTelLoggingHandler",
    "SAFE_DURATION_LABELS",
    "configure_privacy_safe_logging",
    "install_privacy_safe_record_factory",
    "is_safe_request_id",
    "logger_is_in_namespace",
    "protected_logger_family",
    "safe_http_method",
    "safe_http_status",
    "safe_route_template",
]
