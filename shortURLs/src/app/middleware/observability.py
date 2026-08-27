import re
import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders

from app.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
)


logger = structlog.get_logger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _request_id(scope) -> str:
    headers = dict(scope.get("headers", []))
    candidate = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
    if REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


class ObservabilityMiddleware:
    def __init__(self, app, service_name: str):
        self.app = app
        self.service_name = service_name

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")
        status_code = 500
        started_at = time.perf_counter()
        failed = False

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            service=self.service_name,
            request_id=request_id,
            method=method,
            path=path,
        )
        HTTP_REQUESTS_IN_PROGRESS.inc()

        async def send_with_request_id(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["x-request-id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            failed = True
            logger.exception(
                "http_request_failed",
                error_type=type(exc).__name__,
            )
            raise
        finally:
            duration = time.perf_counter() - started_at
            route = getattr(scope.get("route"), "path", "unmatched")
            if path != "/metrics":
                HTTP_REQUESTS_TOTAL.labels(method, route, str(status_code)).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(method, route).observe(duration)
                if not failed:
                    log_method = logger.error if status_code >= 500 else logger.info
                    log_method(
                        "http_request_completed",
                        route=route,
                        status_code=status_code,
                        duration_ms=round(duration * 1000, 3),
                    )
            HTTP_REQUESTS_IN_PROGRESS.dec()
            structlog.contextvars.clear_contextvars()
