"""Five-route WP-UI-01A supervisor facade."""

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import ValidationError

from backend.middleware.v2_errors import (
    SupervisorHTTPError,
    canonical_json_bytes,
    error_response,
    json_response_bytes,
    request_id_for,
)
from backend.schemas.v2_supervisor import (
    BootstrapEnvelope,
    ClaimEnvelope,
    ClaimRequest,
    CutoverEnvelope,
    ErrorEnvelope,
    InProgressEnvelope,
    ProjectsEnvelope,
    ReadinessEnvelope,
    fixed_cutover,
)
from backend.services.actor_scope import ActorScope, get_actor_scope
from backend.services.cutover_service import read_cutover
from backend.services.idempotency_service import (
    Reservation,
    canonical_fingerprint,
    reserve,
)
from backend.services.legacy_adoption_service import PROJECT_ID_RE, load_configured_project
from backend.services.migration_readiness_service import inspect_infrastructure
from backend.services.supervisor_repository import (
    ProjectResolution,
    claim_reserved_project,
    resolve_project_read_only,
)


router = APIRouter(tags=["Codex Supervisor v2"])
BASE_RESPONSE_HEADERS = {
    "Cache-Control": {"schema": {"type": "string", "const": "no-store"}},
    "X-Request-ID": {"schema": {"type": "string", "pattern": "^req_[0-9a-f]{32}$"}},
}
ETAG_HEADER = {"ETag": {"schema": {"type": "string"}}}
RETRY_HEADER = {"Retry-After": {"schema": {"type": "string", "const": "1"}}}
REPLAY_HEADER = {
    "Idempotency-Replayed": {"schema": {"type": "string", "const": "true"}}
}


def _error_responses(*statuses: int) -> dict[int, dict[str, object]]:
    return {
        status: {"model": ErrorEnvelope, "headers": BASE_RESPONSE_HEADERS}
        for status in statuses
    }


READ_ERRORS = _error_responses(401, 403, 422, 500, 503)
PROJECT_ERRORS = _error_responses(401, 403, 409, 422, 500, 503)
CLAIM_ERRORS = _error_responses(400, 401, 403, 404, 409, 412, 415, 422, 428, 500, 503)


def _etag(prefix: str, data: dict[str, object]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(data)).hexdigest()
    return f'"{prefix}-{digest}"'


def _success(
    request: Request,
    data: dict[str, object],
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    meta_extra: dict[str, object] | None = None,
) -> Response:
    request_id = request_id_for(request)
    meta = {"request_id": request_id, "schema_version": "0.1", **(meta_extra or {})}
    return json_response_bytes(
        {"data": data, "meta": meta},
        status_code=status_code,
        request_id=request_id,
        headers=headers,
    )


def _configuration_resolution(actor: ActorScope) -> tuple[object, ProjectResolution | None]:
    configuration = load_configured_project()
    if configuration.state != "ready" or configuration.project is None:
        return configuration, None
    return configuration, resolve_project_read_only(actor=actor, configured=configuration.project)


def _public_project_resolution(configuration, resolution: ProjectResolution | None):
    if configuration.state == "unconfigured":
        return {"state": "unconfigured", "reason_codes": list(configuration.reason_codes)}
    if configuration.state == "quarantined":
        return {"state": "quarantined", "reason_codes": list(configuration.reason_codes)}
    if configuration.state == "dependency_unavailable":
        return {
            "state": "dependency_unavailable",
            "reason_codes": list(configuration.reason_codes),
        }
    if resolution is None:
        raise SupervisorHTTPError(500, "internal_error")
    return resolution.public_resolution()


@router.get(
    "/bootstrap",
    response_model=BootstrapEnvelope,
    responses={
        200: {"model": BootstrapEnvelope, "headers": {**BASE_RESPONSE_HEADERS, **ETAG_HEADER}},
        **READ_ERRORS,
    },
    openapi_extra={"x-operator-action": False},
)
def bootstrap(request: Request, actor: ActorScope = Depends(get_actor_scope)) -> Response:
    infrastructure = inspect_infrastructure()
    if infrastructure.state == "dependency_unavailable":
        raise SupervisorHTTPError(503, "dependency_unavailable")
    if infrastructure.state == "migration_required":
        data = {
            "capabilities": {"can_view_supervisor": True, "can_claim_project": False},
            "action_registry_version": "0.1",
            "infrastructure": infrastructure.public_dict(),
            "project_resolution": None,
            "cutover": None,
            "cutover_absent_reason_code": "migration_required",
            "project": None,
        }
    else:
        configuration, resolution = _configuration_resolution(actor)
        public_resolution = _public_project_resolution(configuration, resolution)
        can_claim = resolution is not None and resolution.state in {
            "claim_required",
            "hidden",
        }
        data = {
            "capabilities": {"can_view_supervisor": True, "can_claim_project": can_claim},
            "action_registry_version": "0.1",
            "infrastructure": infrastructure.public_dict(),
            "project_resolution": public_resolution,
            "cutover": read_cutover(),
            "cutover_absent_reason_code": None,
            "project": resolution.public_summary() if resolution is not None else None,
        }
    return _success(request, data, headers={"ETag": _etag("bootstrap-v1", data)})


@router.get(
    "/operations/readiness",
    response_model=ReadinessEnvelope,
    responses={
        200: {"model": ReadinessEnvelope, "headers": BASE_RESPONSE_HEADERS},
        **READ_ERRORS,
    },
    openapi_extra={"x-operator-action": False},
)
def readiness(request: Request, actor: ActorScope = Depends(get_actor_scope)) -> Response:
    infrastructure = inspect_infrastructure()
    if infrastructure.state == "dependency_unavailable":
        raise SupervisorHTTPError(503, "dependency_unavailable")
    project_resolution = None
    if infrastructure.state == "ready":
        configuration, resolution = _configuration_resolution(actor)
        project_resolution = _public_project_resolution(configuration, resolution)
    return _success(
        request,
        {
            "infrastructure": infrastructure.public_dict(),
            "project_resolution": project_resolution,
        },
    )


@router.get(
    "/operations/cutover-mode",
    response_model=CutoverEnvelope,
    responses={
        200: {"model": CutoverEnvelope, "headers": {**BASE_RESPONSE_HEADERS, **ETAG_HEADER}},
        **READ_ERRORS,
    },
    openapi_extra={"x-operator-action": False},
)
def cutover_mode(request: Request, actor: ActorScope = Depends(get_actor_scope)) -> Response:
    infrastructure = inspect_infrastructure()
    if infrastructure.state == "dependency_unavailable":
        raise SupervisorHTTPError(503, "dependency_unavailable")
    if infrastructure.state != "ready":
        raise SupervisorHTTPError(503, "database_migration_required")
    return _success(
        request,
        read_cutover(),
        headers={"ETag": '"cutover-1"'},
        meta_extra={"resource_version": 1},
    )


@router.get(
    "/projects",
    response_model=ProjectsEnvelope,
    responses={
        200: {"model": ProjectsEnvelope, "headers": {**BASE_RESPONSE_HEADERS, **ETAG_HEADER}},
        **PROJECT_ERRORS,
    },
    openapi_extra={"x-operator-action": False},
)
def projects(request: Request, actor: ActorScope = Depends(get_actor_scope)) -> Response:
    infrastructure = inspect_infrastructure()
    if infrastructure.state == "dependency_unavailable":
        raise SupervisorHTTPError(503, "dependency_unavailable")
    if infrastructure.state != "ready":
        raise SupervisorHTTPError(503, "database_migration_required")
    configuration, resolution = _configuration_resolution(actor)
    if configuration.state == "unconfigured":
        raise SupervisorHTTPError(503, "supervisor_unconfigured")
    if configuration.state == "dependency_unavailable" or (
        resolution is not None and resolution.state == "dependency_unavailable"
    ):
        raise SupervisorHTTPError(503, "dependency_unavailable")
    if configuration.state == "quarantined" or (
        resolution is not None and resolution.state == "quarantined"
    ):
        raise SupervisorHTTPError(409, "supervisor_quarantined")
    if resolution is None:
        raise SupervisorHTTPError(500, "internal_error")
    summary = resolution.public_summary()
    data = {"projects": [] if summary is None else [summary]}
    return _success(request, data, headers={"ETag": _etag("projects-v1", data)})


def _parse_claim_request(request: Request, raw_body: bytes) -> tuple[ClaimRequest, str, str]:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise SupervisorHTTPError(415, "unsupported_media_type")
    idempotency_key = request.headers.get("Idempotency-Key")
    if_match = request.headers.get("If-Match")
    if not idempotency_key or not if_match:
        raise SupervisorHTTPError(428, "precondition_required")
    try:
        parsed_key = uuid.UUID(idempotency_key)
        if parsed_key.version != 4 or str(parsed_key) != idempotency_key.lower():
            raise ValueError
    except (ValueError, AttributeError):
        raise SupervisorHTTPError(422, "validation_failed")
    try:
        payload = ClaimRequest.model_validate_json(raw_body)
    except ValidationError as exc:
        raise SupervisorHTTPError(422, "validation_failed") from exc
    expected_etag = f'"project-{payload.expected_version}"'
    if if_match != expected_etag:
        raise SupervisorHTTPError(400, "precondition_mismatch")
    return payload, idempotency_key.lower(), if_match


def _stored_response(result: Reservation, *, replay: bool = False) -> Response:
    if result.response_body is None or result.response_status is None or result.response_headers is None:
        raise SupervisorHTTPError(500, "internal_error")
    headers = dict(result.response_headers)
    content_type = headers.pop("Content-Type", "application/json")
    if replay:
        headers["Idempotency-Replayed"] = "true"
    return Response(
        content=result.response_body,
        status_code=result.response_status,
        media_type=content_type,
        headers=headers,
    )


@router.post(
    "/projects/{project_id}/claim",
    response_model=ClaimEnvelope,
    responses={
        200: {
            "model": ClaimEnvelope,
            "headers": {**BASE_RESPONSE_HEADERS, **ETAG_HEADER, **REPLAY_HEADER},
        },
        202: {
            "description": "Matching operation is in progress",
            "model": InProgressEnvelope,
            "headers": {**BASE_RESPONSE_HEADERS, **RETRY_HEADER},
        },
        **CLAIM_ERRORS,
    },
    openapi_extra={
        "x-operator-action": True,
        "x-action-code": "claim_project",
        "x-action-registry-version": "0.1",
        "x-backend-permission": "project.claim",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": ClaimRequest.model_json_schema()}},
        },
    },
)
async def claim_project(
    project_id: str,
    request: Request,
    actor: ActorScope = Depends(get_actor_scope),
) -> Response:
    # Body parsing is intentionally inside the function so native authentication
    # and platform authority have already completed.
    raw_body = await request.body()
    payload, idempotency_key, _ = _parse_claim_request(request, raw_body)
    if PROJECT_ID_RE.fullmatch(project_id) is None:
        raise SupervisorHTTPError(422, "validation_failed")
    infrastructure = inspect_infrastructure()
    if infrastructure.state == "dependency_unavailable":
        raise SupervisorHTTPError(503, "dependency_unavailable")
    if infrastructure.state != "ready":
        raise SupervisorHTTPError(503, "database_migration_required")

    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=project_id,
        expected_version=payload.expected_version,
        confirmation=payload.confirmation,
    )
    reservation = reserve(
        actor=actor,
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if reservation.mode == "conflict":
        raise SupervisorHTTPError(409, "idempotency_conflict")
    if reservation.mode == "in_progress":
        request.state.supervisor_request_id = reservation.request_id
        return _success(
            request,
            {
                "operation": {
                    "action": "claim_project",
                    "state": "in_progress",
                    "retry_after_seconds": 1,
                }
            },
            status_code=202,
            headers={"Retry-After": "1"},
            meta_extra={"idempotency_state": "in_progress"},
        )
    if reservation.mode == "replay":
        request.state.supervisor_request_id = reservation.request_id
        return _stored_response(reservation, replay=True)

    request.state.supervisor_request_id = reservation.request_id
    result = claim_reserved_project(
        actor=actor,
        project_id=project_id,
        reservation=reservation,
        idempotency_key=idempotency_key,
        expected_version=payload.expected_version,
    )
    return _stored_response(result)
