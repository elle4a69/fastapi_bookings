import re
import time
import uuid
import logging
from contextvars import ContextVar
from typing import Optional, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("codex.access")

request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
thread_id_ctx_var: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)

SENSITIVE_PARAM_PATTERN = re.compile(r'((?:[?&\s]|^)(?:token|secret|token_secret|password|api_key|access_token|auth|key)=)[^&#\s]+', re.IGNORECASE)
BEARER_PATTERN = re.compile(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', re.IGNORECASE)
SENSITIVE_KEYS = {
    "authorization",
    "token",
    "token_secret",
    "secret",
    "password",
    "api_key",
    "access_token",
    "refresh_token",
    "credentials",
    "cookie",
    "x-token",
    "proxy-authorization"
}


def redact_secrets(text: str) -> str:
    """Redacts bearer tokens and sensitive query parameters from strings."""
    if not isinstance(text, str):
        return text
    text = BEARER_PATTERN.sub(r'\1[REDACTED]', text)
    text = SENSITIVE_PARAM_PATTERN.sub(r'\1[REDACTED]', text)
    return text


def redact_dict(data: Any) -> Any:
    """Recursively redacts sensitive keys from dictionaries and lists."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                sanitized[k] = redact_dict(v)
            elif isinstance(v, str):
                sanitized[k] = redact_secrets(v)
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(data, list):
        return [redact_dict(item) for item in data]
    elif isinstance(data, str):
        return redact_secrets(data)
    return data


class RedactingFilter(logging.Filter):
    """Logging filter that sanitizes log message text and arguments to prevent leaking secrets."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = redact_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_dict(a) if isinstance(a, dict) else (redact_secrets(a) if isinstance(a, str) else a) for a in record.args)
        return True


class CorrelationLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Extracts or generates correlation identifiers (request_id, thread_id, project_id).
    2. Attaches X-Request-ID (and X-Thread-ID if present) to response headers.
    3. Logs structured request details with latency and sanitized URLs/parameters.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()

        # 1. Extract or generate request_id
        req_id = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
        if not req_id:
            req_id = f"req_{uuid.uuid4().hex[:12]}"

        # 2. Extract thread_id if available (from headers, query, or path)
        thread_id = request.headers.get("x-thread-id") or request.query_params.get("thread_id")
        if not thread_id:
            # Check path patterns like /events/{project_id}/{thread_id} or /threads/{thread_id}
            path_parts = request.url.path.strip("/").split("/")
            if "threads" in path_parts:
                idx = path_parts.index("threads")
                if idx + 1 < len(path_parts) and not path_parts[idx + 1].startswith("?"):
                    thread_id = path_parts[idx + 1]
            elif "events" in path_parts and len(path_parts) >= 3:
                # /codex/events/{project_id}/{thread_id}
                thread_id = path_parts[-1]
            elif "subagents" in path_parts and len(path_parts) >= 3:
                # /codex/governance/subagents/{thread_id}
                thread_id = path_parts[-1]

        # 3. Extract project_id if available
        project_id = request.headers.get("x-project-id") or request.query_params.get("project_id")

        # Set context variables & request state
        request_id_ctx_var.set(req_id)
        thread_id_ctx_var.set(thread_id)
        request.state.request_id = req_id
        request.state.thread_id = thread_id
        request.state.project_id = project_id

        # Sanitized URL for safe logging
        sanitized_url = redact_secrets(str(request.url))

        # Log request start at DEBUG level
        logger.debug(
            f"[{req_id}] --> {request.method} {sanitized_url}",
            extra={"request_id": req_id, "thread_id": thread_id, "project_id": project_id}
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Attach headers
            response.headers["X-Request-ID"] = req_id
            if thread_id:
                response.headers["X-Thread-ID"] = thread_id

            logger.info(
                f"[{req_id}] {request.method} {sanitized_url} {response.status_code} ({duration_ms}ms)",
                extra={
                    "request_id": req_id,
                    "thread_id": thread_id,
                    "project_id": project_id,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms
                }
            )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"[{req_id}] Unhandled error processing {request.method} {sanitized_url} ({duration_ms}ms): {exc}",
                extra={
                    "request_id": req_id,
                    "thread_id": thread_id,
                    "project_id": project_id,
                    "duration_ms": duration_ms
                }
            )
            raise
