"""Safe response/error helpers isolated to the supervisor v2 prefix."""

from collections.abc import Mapping
import json
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import Response


PREFIX = "/api/admin/codex/v2"
SAFE_MESSAGES = {
    "authentication_required": "Authentication is required.",
    "authentication_unavailable": "Authentication is temporarily unavailable.",
    "forbidden": "Platform owner authority is required.",
    "validation_failed": "Request validation failed.",
    "precondition_required": "Required request preconditions are missing.",
    "precondition_mismatch": "Request preconditions do not agree.",
    "resource_not_found": "The requested resource was not found.",
    "idempotency_conflict": "The idempotency key is already used for another request.",
    "invalid_state": "The resource is not in a valid state for this action.",
    "claim_guard_failed": "The configured project claim guard failed.",
    "supervisor_owned": "The project is owned by the supervisor control plane.",
    "supervisor_quarantined": "The configured project requires operator recovery.",
    "revision_conflict": "The resource version has changed.",
    "supervisor_unconfigured": "The supervisor project is not configured.",
    "database_migration_required": "The Control Centre database requires migration.",
    "dependency_unavailable": "A required dependency is unavailable.",
    "unsupported_media_type": "Content-Type must be application/json.",
    "internal_error": "An unexpected internal error occurred.",
}


class SupervisorHTTPError(HTTPException):
    def __init__(self, status_code: int, code: str, details: Mapping[str, object] | None = None):
        super().__init__(
            status_code=status_code,
            detail={"v2_code": code, "details": dict(details or {})},
        )
        self.code = code
        self.safe_details = dict(details or {})


def request_id_for(request: Request) -> str:
    existing = getattr(request.state, "supervisor_request_id", None)
    if isinstance(existing, str) and existing.startswith("req_") and len(existing) > 4:
        return existing
    request_id = f"req_{secrets.token_hex(16)}"
    request.state.supervisor_request_id = request_id
    return request_id


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def json_response_bytes(
    body: dict[str, object],
    *,
    status_code: int,
    request_id: str,
    headers: Mapping[str, str] | None = None,
) -> Response:
    response_headers = {
        "Cache-Control": "no-store",
        "X-Request-ID": request_id,
        **dict(headers or {}),
    }
    return Response(
        content=canonical_json_bytes(body),
        status_code=status_code,
        media_type="application/json",
        headers=response_headers,
    )


def error_body(request_id: str, code: str, details: Mapping[str, object] | None = None) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": SAFE_MESSAGES.get(code, SAFE_MESSAGES["internal_error"]),
            "details": dict(details or {}),
        },
        "meta": {"request_id": request_id, "schema_version": "0.1"},
    }


def error_response(
    request: Request,
    status_code: int,
    code: str,
    details: Mapping[str, object] | None = None,
) -> Response:
    request_id = request_id_for(request)
    return json_response_bytes(
        error_body(request_id, code, details),
        status_code=status_code,
        request_id=request_id,
    )


def code_for_http_exception(exc: HTTPException) -> str:
    if isinstance(exc, SupervisorHTTPError):
        return exc.code
    if exc.status_code == 401:
        return "authentication_required"
    if exc.status_code == 403:
        return "forbidden"
    if exc.status_code == 503 and isinstance(exc.detail, str) and "bypass" in exc.detail.lower():
        return "authentication_unavailable"
    return {
        404: "resource_not_found",
        409: "invalid_state",
        412: "revision_conflict",
        415: "unsupported_media_type",
        422: "validation_failed",
        428: "precondition_required",
        500: "internal_error",
        503: "dependency_unavailable",
    }.get(exc.status_code, "internal_error")
