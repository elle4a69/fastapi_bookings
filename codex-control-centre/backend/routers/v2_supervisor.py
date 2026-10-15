"""Five-route WP-UI-01A supervisor facade."""

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from backend.middleware.v2_errors import (
    SupervisorHTTPError,
    canonical_json_bytes,
    error_body,
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
from backend.services.supervisor_repository import (
    DETERMINISTIC_FAILURES,
    planning_approve_in_transaction,
    planning_create_in_transaction,
    planning_get,
    planning_list,
    planning_parent_version,
    planning_parent_version_in_transaction,
)
from backend.services.supervisor_event_service import append_planning_event
from backend.models.codex import IdempotencyRecord
from backend import database
from backend.services.idempotency_service import terminal_values


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
PLANNING_READ_RESPONSES = {
    200: {"description": "Stable planning representation", "headers": {**BASE_RESPONSE_HEADERS, **ETAG_HEADER}},
    **_error_responses(401, 403, 404, 422, 500, 503),
}
PLANNING_MUTATION_RESPONSES = {
    200: {"description": "Stored planning mutation or byte-exact replay", "headers": {**BASE_RESPONSE_HEADERS, **ETAG_HEADER, **REPLAY_HEADER}},
    202: {"description": "Matching mutation is in progress", "headers": {**BASE_RESPONSE_HEADERS, **RETRY_HEADER}},
    **_error_responses(400, 401, 403, 404, 409, 412, 415, 422, 428, 500, 503),
}


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
            "action_registry_version": "0.2",
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
            "action_registry_version": "0.2",
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
        "x-action-registry-version": "0.2",
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


# Planning-only endpoints. They deliberately have no route to execute a brief.
def _planning_output(row: dict[str, object]) -> dict[str, object]:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}

PLANNING_ACTIONS = {
    "create_mission": ("mission", "project"),
    "create_work_package": ("work_package", "mission"),
    "create_brief": ("brief", "work_package"),
    "approve_brief": ("brief", "brief"),
    "record_context_checkpoint": ("checkpoint", "mission"),
    "define_audit_scope": ("audit_scope", "work_package"),
}
PLANNING_FIELDS = {
    "create_mission": {"action", "registry_version", "confirmation", "title", "summary"},
    "create_work_package": {"action", "registry_version", "confirmation", "title", "scope"},
    "create_brief": {"action", "registry_version", "confirmation", "content", "future_execution_authorization_requirement"},
    "approve_brief": {"action", "registry_version", "confirmation"},
    "record_context_checkpoint": {"action", "registry_version", "confirmation", "summary", "decisions", "constraints", "open_questions"},
    "define_audit_scope": {"action", "registry_version", "confirmation", "criteria", "exclusions"},
}

def _parse_planning_request(request: Request, raw: bytes, action: str) -> tuple[dict[str, object], str, str]:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise SupervisorHTTPError(415, "unsupported_media_type")
    key, if_match = request.headers.get("Idempotency-Key"), request.headers.get("If-Match")
    if not key or not if_match: raise SupervisorHTTPError(428, "precondition_required")
    try:
        parsed=uuid.UUID(key)
        if parsed.version != 4 or str(parsed) != key.lower(): raise ValueError
        payload=json.loads(raw)
    except (ValueError, json.JSONDecodeError, TypeError): raise SupervisorHTTPError(422,"validation_failed")
    if not isinstance(payload, dict) or set(payload) - PLANNING_FIELDS[action] or payload.get("action") != action or payload.get("registry_version") != "0.2" or payload.get("confirmation") is not True:
        raise SupervisorHTTPError(422, "validation_failed")
    return payload, key.lower(), if_match

async def _planning_mutation(request: Request, actor: ActorScope, action: str, parent_id: str) -> Response:
    raw=await request.body(); payload, key, if_match = _parse_planning_request(request, raw, action)
    kind, parent_prefix=PLANNING_ACTIONS[action]
    version=planning_parent_version(action, parent_id, actor)
    fingerprint=hashlib.sha256(canonical_json_bytes({"action":action,"actor_tenant_id":actor.tenant_id,"actor_user_id":actor.user_id,"parent":parent_id,"payload":payload,"registry_version":"0.2","route":request.url.path})).hexdigest()
    reservation=reserve(actor=actor,idempotency_key=key,fingerprint=fingerprint,action_code=action)
    if reservation.mode == "conflict": raise SupervisorHTTPError(409,"idempotency_conflict")
    request.state.supervisor_request_id=reservation.request_id
    if reservation.mode == "in_progress": return _success(request,{"operation":{"action":action,"state":"in_progress","retry_after_seconds":1}},status_code=202,headers={"Retry-After":"1"},meta_extra={"idempotency_state":"in_progress"})
    if reservation.mode == "replay": return _stored_response(reservation,replay=True)
    if not reservation.record_id or not reservation.raw_lease_token: raise SupervisorHTTPError(500,"internal_error")
    try:
        with database.engine.connect() as connection:
            from backend.services.idempotency_service import _begin_immediate, verify_live_reservation
            _begin_immediate(connection); verify_live_reservation(connection,record_id=reservation.record_id,raw_lease_token=reservation.raw_lease_token)
            side_effects=connection.begin_nested()
            try:
                # A new stale request has a durable terminal 412; an existing
                # same-key success returned above before this comparison.
                if if_match != f'"{parent_prefix}-{version}"': raise SupervisorHTTPError(412,"revision_conflict")
                current=planning_parent_version_in_transaction(connection,action,parent_id,actor)
                if current != version: raise SupervisorHTTPError(412,"revision_conflict")
                result, project_id, project_version = (planning_approve_in_transaction(connection,parent_id,actor) if action == "approve_brief" else planning_create_in_transaction(connection,kind,parent_id,payload,actor))
                append_planning_event(connection,project_public_id=project_id,actor=actor,action_code=action,project_version=project_version,request_id=reservation.request_id,idempotency_key=key)
                data={kind:_planning_output(result)}; body=canonical_json_bytes({"data":data,"meta":{"request_id":reservation.request_id,"schema_version":"0.2","resource_version":int(result.get("version",1)),"idempotency_state":"succeeded"}}); headers={"Content-Type":"application/json","ETag":_etag(f"{kind}-v1",data),"Cache-Control":"no-store","X-Request-ID":reservation.request_id}
                connection.execute(IdempotencyRecord.__table__.update().where(IdempotencyRecord.__table__.c.id==reservation.record_id).values(**terminal_values(status="succeeded",response_status=200,response_body=body,response_headers=headers)))
                side_effects.commit(); connection.commit()
                return Response(content=body,status_code=200,media_type="application/json",headers=headers)
            except (SupervisorHTTPError, IntegrityError) as exc:
                side_effects.rollback()
                code = exc.code if isinstance(exc, SupervisorHTTPError) else "revision_conflict"
                status_code = exc.status_code if isinstance(exc, SupervisorHTTPError) else 409
                if code not in DETERMINISTIC_FAILURES | {"approved_brief_required","brief_not_draft","validation_failed"}:
                    connection.rollback(); raise
                body=canonical_json_bytes(error_body(reservation.request_id,code)); headers={"Content-Type":"application/json","Cache-Control":"no-store","X-Request-ID":reservation.request_id}
                connection.execute(IdempotencyRecord.__table__.update().where(IdempotencyRecord.__table__.c.id==reservation.record_id).values(**terminal_values(status="failed",response_status=status_code,response_body=body,response_headers=headers)))
                connection.commit(); return _stored_response(Reservation("terminal_failure",reservation.request_id,response_status=status_code,response_body=body,response_headers=headers))
    except SupervisorHTTPError: raise

@router.get("/projects/{project_id}/missions", responses=PLANNING_READ_RESPONSES, openapi_extra={"x-operator-action":False})
def list_missions(project_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:
    data={"missions":[_planning_output(x) for x in planning_list("mission",project_id,actor)]}; return _success(request,data,headers={"ETag":_etag("missions-v1",data)})
@router.post("/projects/{project_id}/missions", responses=PLANNING_MUTATION_RESPONSES, openapi_extra={"x-operator-action":True,"x-action-code":"create_mission","x-action-registry-version":"0.2","x-backend-permission":"planning.create_mission"})
async def create_mission(project_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response: return await _planning_mutation(request,actor,"create_mission",project_id)
@router.get("/missions/{mission_id}", responses=PLANNING_READ_RESPONSES)
def get_mission(mission_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:
    data={"mission":_planning_output(planning_get("mission",mission_id,actor))}; return _success(request,data,headers={"ETag":_etag("mission-v1",data)})
@router.get("/missions/{mission_id}/work-packages", responses=PLANNING_READ_RESPONSES)
def list_work_packages(mission_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:
    data={"work_packages":[_planning_output(x) for x in planning_list("work_package",mission_id,actor)]}; return _success(request,data,headers={"ETag":_etag("work-packages-v1",data)})
@router.post("/missions/{mission_id}/work-packages",responses=PLANNING_MUTATION_RESPONSES,openapi_extra={"x-operator-action":True,"x-action-code":"create_work_package","x-action-registry-version":"0.2","x-backend-permission":"planning.create_work_package"})
async def create_work_package(mission_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response: return await _planning_mutation(request,actor,"create_work_package",mission_id)
@router.get("/work-packages/{work_package_id}", responses=PLANNING_READ_RESPONSES)
def get_work_package(work_package_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:
    data={"work_package":_planning_output(planning_get("work_package",work_package_id,actor))}; return _success(request,data,headers={"ETag":_etag("work-package-v1",data)})
@router.get("/work-packages/{work_package_id}/briefs", responses=PLANNING_READ_RESPONSES)
def list_briefs(work_package_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:
    data={"briefs":[_planning_output(x) for x in planning_list("brief",work_package_id,actor)]}; return _success(request,data,headers={"ETag":_etag("briefs-v1",data)})
@router.post("/work-packages/{work_package_id}/briefs",responses=PLANNING_MUTATION_RESPONSES,openapi_extra={"x-operator-action":True,"x-action-code":"create_brief","x-action-registry-version":"0.2","x-backend-permission":"planning.create_brief"})
async def create_brief(work_package_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:return await _planning_mutation(request,actor,"create_brief",work_package_id)
@router.get("/briefs/{brief_id}", responses=PLANNING_READ_RESPONSES)
def get_brief(brief_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:
    data={"brief":_planning_output(planning_get("brief",brief_id,actor))}; return _success(request,data,headers={"ETag":_etag("brief-v1",data)})
@router.post("/briefs/{brief_id}/approve",responses=PLANNING_MUTATION_RESPONSES,openapi_extra={"x-operator-action":True,"x-action-code":"approve_brief","x-action-registry-version":"0.2","x-backend-permission":"planning.approve_brief"})
async def approve_brief(brief_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:return await _planning_mutation(request,actor,"approve_brief",brief_id)
@router.get("/missions/{mission_id}/context-checkpoints", responses=PLANNING_READ_RESPONSES)
def list_checkpoints(mission_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:
    data={"context_checkpoints":[_planning_output(x) for x in planning_list("checkpoint",mission_id,actor)]}; return _success(request,data,headers={"ETag":_etag("checkpoints-v1",data)})
@router.post("/missions/{mission_id}/context-checkpoints",responses=PLANNING_MUTATION_RESPONSES,openapi_extra={"x-operator-action":True,"x-action-code":"record_context_checkpoint","x-action-registry-version":"0.2","x-backend-permission":"planning.record_context_checkpoint"})
async def create_checkpoint(mission_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:return await _planning_mutation(request,actor,"record_context_checkpoint",mission_id)
@router.get("/work-packages/{work_package_id}/audit-scope", responses=PLANNING_READ_RESPONSES)
def list_audit_scope(work_package_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:
    scopes=planning_list("audit_scope",work_package_id,actor)
    data={"audit_scope":None if not scopes else _planning_output(scopes[0])}; return _success(request,data,headers={"ETag":_etag("audit-scope-v1",data)})
@router.post("/work-packages/{work_package_id}/audit-scope",responses=PLANNING_MUTATION_RESPONSES,openapi_extra={"x-operator-action":True,"x-action-code":"define_audit_scope","x-action-registry-version":"0.2","x-backend-permission":"planning.define_audit_scope"})
async def create_audit_scope(work_package_id:str,request:Request,actor:ActorScope=Depends(get_actor_scope))->Response:return await _planning_mutation(request,actor,"define_audit_scope",work_package_id)
