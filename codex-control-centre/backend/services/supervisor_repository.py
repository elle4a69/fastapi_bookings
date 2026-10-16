"""Scoped configured-project resolution and atomic claim transaction."""

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
from typing import Callable

from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from backend import database
from backend.middleware.v2_errors import SupervisorHTTPError, canonical_json_bytes, error_body
from backend.models.codex import IdempotencyRecord, Project
from backend.schemas.v2_supervisor import claim_descriptor
from backend.services.actor_scope import ActorScope
from backend.services.idempotency_service import (
    Reservation,
    _begin_immediate,
    terminal_values,
    verify_live_reservation,
)
from backend.services.legacy_adoption_service import (
    ConfiguredProject,
    load_configured_project,
    paths_are_same,
)
from backend.services.supervisor_event_service import append_claim_event, append_planning_event

# WP-UI-01B planning ledger helpers.  They deliberately contain no worker,
# execution, filesystem, Git, tool, or evidence capability.
from backend.models.codex import PlanningMission, PlanningWorkPackage, PlanningBrief, PlanningContextCheckpoint, PlanningAuditScope
import hashlib
import re

# Planning text is a deliberately small, structural vocabulary.  It is not a
# prompt, a work log, source material, or a place to retain personal data.
_STRUCTURAL_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,.?!&'()_-]*$")
_FORBIDDEN_TEXT_TOKENS = frozenset({
    "address", "apikey", "auth", "authorization", "code", "command", "credential",
    "credentials", "directory", "email", "evidence", "file", "filepath", "finding",
    "key", "keys", "log", "logs", "output", "outcome", "password", "path", "phone",
    "pii", "prompt", "prompts", "result", "results", "secret", "secrets", "shell",
    "source", "token", "tokens", "transcript", "verdict", "class", "def", "function",
    "import", "print", "return", "system", "assistant", "instruction", "instructions",
})
_SHELL_TOKENS = frozenset({"bash", "cd", "cmd", "curl", "dir", "docker", "git", "ls", "mkdir", "npm", "pip", "powershell", "py", "pytest", "python", "rm", "sh"})
_PROMPT_FRAMES = ("you are ", "act as ", "ignore previous", "follow these", "as an ai")
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_PHONE = re.compile(r"(?:\+?61|0)\s*4\d(?:[\s-]*\d){7}\b|\b\d{8,}\b")

def _safe_text(value: object, maximum: int, field: str) -> str:
    """Allow only bounded structural planning prose, never operational material."""
    if not isinstance(value, str):
        raise SupervisorHTTPError(422, "validation_failed")
    normalized = value.strip()
    lowered = normalized.lower()
    tokens = set(re.findall(r"[a-z]+", lowered))
    # A field name is intentionally accepted only as a schema selector; all
    # fields use the same privacy-safe structural grammar in v0.2.
    if field not in {"title", "summary", "scope", "content", "decisions", "constraints", "open_questions", "criteria", "exclusions"}:
        raise SupervisorHTTPError(422, "validation_failed")
    if (not normalized or len(normalized) > maximum or not _STRUCTURAL_TEXT.fullmatch(normalized)
            or bool(tokens & _FORBIDDEN_TEXT_TOKENS) or bool(tokens & _SHELL_TOKENS)
            or any(frame in lowered for frame in _PROMPT_FRAMES)
            or _EMAIL.search(normalized) or _PHONE.search(normalized)):
        raise SupervisorHTTPError(422, "validation_failed")
    return normalized

def _scoped(connection: Connection, table, identifier: str, actor: ActorScope):
    row = connection.execute(select(table).where(table.c.id == identifier, table.c.tenant_id == actor.tenant_id, table.c.owner_user_id == actor.user_id)).first()
    if row is None:
        raise SupervisorHTTPError(404, "resource_not_found")
    return row._mapping

def _claimed_project(connection: Connection, project_id: str, actor: ActorScope):
    row = connection.execute(select(Project.__table__).where(Project.__table__.c.public_id == project_id, Project.__table__.c.tenant_id == actor.tenant_id, Project.__table__.c.owner_user_id == actor.user_id, Project.__table__.c.scope_state == "claimed")).first()
    if row is None:
        raise SupervisorHTTPError(404, "resource_not_found")
    return row._mapping

def _parent(connection: Connection, action: str, identifier: str, actor: ActorScope):
    if action == "create_mission":
        return _claimed_project(connection, identifier, actor), "project"
    if action in {"create_work_package", "record_context_checkpoint"}:
        mission = _scoped(connection, PlanningMission.__table__, identifier, actor)
        project = _scoped(connection, Project.__table__, mission["project_id"], actor)
        if project["scope_state"] != "claimed": raise SupervisorHTTPError(404, "resource_not_found")
        return mission, "mission"
    if action == "approve_brief":
        brief = _scoped(connection, PlanningBrief.__table__, identifier, actor)
        work = _scoped(connection, PlanningWorkPackage.__table__, brief["work_package_id"], actor)
        mission = _scoped(connection, PlanningMission.__table__, work["mission_id"], actor)
        project = _scoped(connection, Project.__table__, mission["project_id"], actor)
        if project["scope_state"] != "claimed": raise SupervisorHTTPError(404, "resource_not_found")
        return brief, "brief"
    work = _scoped(connection, PlanningWorkPackage.__table__, identifier, actor)
    mission = _scoped(connection, PlanningMission.__table__, work["mission_id"], actor)
    project = _scoped(connection, Project.__table__, mission["project_id"], actor)
    if project["scope_state"] != "claimed": raise SupervisorHTTPError(404, "resource_not_found")
    return work, "work_package"

def planning_parent_version(action: str, identifier: str, actor: ActorScope) -> int:
    with database.engine.connect() as connection:
        parent, _ = _parent(connection, action, identifier, actor)
        return int(parent["version"])

def planning_parent_version_in_transaction(connection: Connection, action: str, identifier: str, actor: ActorScope) -> int:
    parent, _ = _parent(connection, action, identifier, actor)
    return int(parent["version"])

def planning_get(kind: str, identifier: str, actor: ActorScope) -> dict[str, object]:
    action = {"mission":"create_work_package", "work_package":"create_brief", "brief":"approve_brief"}[kind]
    with database.engine.connect() as connection:
        parent, _ = _parent(connection, action, identifier, actor)
        return dict(parent)

def planning_list(kind: str, parent_id: str, actor: ActorScope) -> list[dict[str, object]]:
    action = {"mission":"create_mission", "work_package":"create_work_package", "brief":"create_brief", "checkpoint":"record_context_checkpoint", "audit_scope":"define_audit_scope"}[kind]
    table, field = {"mission":(PlanningMission.__table__, "project_id"), "work_package":(PlanningWorkPackage.__table__, "mission_id"), "brief":(PlanningBrief.__table__, "work_package_id"), "checkpoint":(PlanningContextCheckpoint.__table__, "mission_id"), "audit_scope":(PlanningAuditScope.__table__, "work_package_id")}[kind]
    with database.engine.connect() as connection:
        parent, _ = _parent(connection, action, parent_id, actor)
        key = parent["id"]
        return [dict(row._mapping) for row in connection.execute(select(table).where(table.c.tenant_id == actor.tenant_id, table.c.owner_user_id == actor.user_id, getattr(table.c, field) == key).order_by(table.c.created_at)).all()]

def planning_create_in_transaction(connection: Connection, kind: str, parent_id: str, payload: dict[str, object], actor: ActorScope) -> tuple[dict[str, object], str, int]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    action = {"mission":"create_mission", "work_package":"create_work_package", "brief":"create_brief", "checkpoint":"record_context_checkpoint", "audit_scope":"define_audit_scope"}[kind]
    parent, _ = _parent(connection, action, parent_id, actor)
    if kind == "mission":
        values = {"id":"mis_"+uuid.uuid4().hex, "project_id":parent["id"], "tenant_id":actor.tenant_id, "owner_user_id":actor.user_id, "title":_safe_text(payload.get("title"),160,"title"), "summary":_safe_text(payload.get("summary"),1200,"summary"), "state":"draft", "version":1, "created_at":now}; table=PlanningMission.__table__; project_id=parent["public_id"]; project_version=int(parent["version"])
    elif kind == "work_package":
        values = {"id":"wpk_"+uuid.uuid4().hex,"mission_id":parent["id"],"project_id":parent["project_id"],"tenant_id":actor.tenant_id,"owner_user_id":actor.user_id,"title":_safe_text(payload.get("title"),160,"title"),"scope":_safe_text(payload.get("scope"),1600,"scope"),"state":"draft","version":1,"created_at":now}; table=PlanningWorkPackage.__table__; project_id=_scoped(connection,Project.__table__,parent["project_id"],actor)["public_id"]; project_version=int(_scoped(connection,Project.__table__,parent["project_id"],actor)["version"])
    elif kind == "brief":
        auth=payload.get("future_execution_authorization_requirement", "requires_authorization")
        if auth not in {"requires_authorization", "not_required_once_requested"}: raise SupervisorHTTPError(422,"validation_failed")
        revision=(connection.execute(select(PlanningBrief.__table__.c.revision).where(PlanningBrief.__table__.c.work_package_id==parent["id"]).order_by(PlanningBrief.__table__.c.revision.desc()).limit(1)).scalar() or 0)+1
        content=_safe_text(payload.get("content"),4000,"content"); values={"id":"brf_"+uuid.uuid4().hex,"work_package_id":parent["id"],"project_id":parent["project_id"],"tenant_id":actor.tenant_id,"owner_user_id":actor.user_id,"revision":int(revision),"content":content,"content_digest":hashlib.sha256(content.encode()).hexdigest(),"future_execution_authorization_requirement":auth,"state":"draft","version":1,"approved_by_user_id":None,"approved_at":None,"created_at":now}; table=PlanningBrief.__table__; project_id=_scoped(connection,Project.__table__,parent["project_id"],actor)["public_id"]; project_version=int(_scoped(connection,Project.__table__,parent["project_id"],actor)["version"])
    elif kind == "checkpoint":
        sequence=(connection.execute(select(PlanningContextCheckpoint.__table__.c.sequence).where(PlanningContextCheckpoint.__table__.c.mission_id==parent["id"]).order_by(PlanningContextCheckpoint.__table__.c.sequence.desc()).limit(1)).scalar() or 0)+1
        values={"id":"ctx_"+uuid.uuid4().hex,"mission_id":parent["id"],"project_id":parent["project_id"],"tenant_id":actor.tenant_id,"owner_user_id":actor.user_id,"sequence":int(sequence),"summary":_safe_text(payload.get("summary"),1600,"summary"),"decisions":_safe_text(payload.get("decisions"),1600,"decisions"),"constraints":_safe_text(payload.get("constraints"),1600,"constraints"),"open_questions":_safe_text(payload.get("open_questions"),1600,"open_questions"),"created_at":now}; table=PlanningContextCheckpoint.__table__; project_id=_scoped(connection,Project.__table__,parent["project_id"],actor)["public_id"]; project_version=int(_scoped(connection,Project.__table__,parent["project_id"],actor)["version"])
    else:
        approved=connection.execute(select(PlanningBrief.__table__.c.id).where(PlanningBrief.__table__.c.work_package_id==parent["id"],PlanningBrief.__table__.c.state=="approved")).first()
        if approved is None: raise SupervisorHTTPError(409,"approved_brief_required")
        values={"id":"asc_"+uuid.uuid4().hex,"work_package_id":parent["id"],"project_id":parent["project_id"],"tenant_id":actor.tenant_id,"owner_user_id":actor.user_id,"criteria":_safe_text(payload.get("criteria"),2000,"criteria"),"exclusions":_safe_text(payload.get("exclusions"),1200,"exclusions"),"created_at":now}; table=PlanningAuditScope.__table__; project_id=_scoped(connection,Project.__table__,parent["project_id"],actor)["public_id"]; project_version=int(_scoped(connection,Project.__table__,parent["project_id"],actor)["version"])
    connection.execute(table.insert().values(**values))
    if kind == "brief" and parent["state"] == "brief_approved":
        connection.execute(update(PlanningWorkPackage.__table__).where(PlanningWorkPackage.__table__.c.id == parent["id"]).values(state="brief_ready", version=int(parent["version"]) + 1))
    return values, str(project_id), project_version

def planning_approve_in_transaction(connection: Connection, brief_id: str, actor: ActorScope) -> tuple[dict[str, object], str, int]:
    brief, _ = _parent(connection, "approve_brief", brief_id, actor)
    if brief["state"] != "draft": raise SupervisorHTTPError(409,"brief_not_draft")
    now=datetime.now(timezone.utc).replace(microsecond=0)
    connection.execute(update(PlanningBrief.__table__).where(PlanningBrief.__table__.c.id==brief_id).values(state="approved",approved_by_user_id=actor.user_id,approved_at=now,version=int(brief["version"])+1))
    connection.execute(update(PlanningBrief.__table__).where(PlanningBrief.__table__.c.work_package_id==brief["work_package_id"],PlanningBrief.__table__.c.id!=brief_id,PlanningBrief.__table__.c.state=="approved").values(state="superseded"))
    connection.execute(update(PlanningWorkPackage.__table__).where(PlanningWorkPackage.__table__.c.id==brief["work_package_id"]).values(state="brief_approved",version=PlanningWorkPackage.__table__.c.version+1))
    project=_scoped(connection,Project.__table__,brief["project_id"],actor)
    return {**dict(brief),"state":"approved","version":int(brief["version"])+1,"approved_by_user_id":actor.user_id,"approved_at":now}, str(project["public_id"]), int(project["version"])


MAX_PROJECT_IDENTITY_ROWS = 512
DETERMINISTIC_FAILURES = {
    "resource_not_found",
    "invalid_state",
    "claim_guard_failed",
    "supervisor_quarantined",
    "revision_conflict",
    "supervisor_unconfigured",
    "resource_not_found",
    "validation_failed",
    "approved_brief_required",
    "brief_not_draft",
}


@dataclass(frozen=True, slots=True)
class ProjectResolution:
    state: str
    reason_codes: tuple[str, ...]
    configured: ConfiguredProject
    row_id: str | None = None

    def public_resolution(self) -> dict[str, object]:
        if self.state == "hidden":
            # Preserve an absence-like public state without exposing a count,
            # scope, identifier, conflict reason or claim action.
            return {"state": "claim_required", "reason_codes": []}
        return {"state": self.state, "reason_codes": list(self.reason_codes)}

    def public_summary(self) -> dict[str, object] | None:
        if self.state not in {"claim_required", "claimed", "hidden"}:
            return None
        claimed = self.state == "claimed"
        return {
            "project_id": self.configured.public_id,
            "display_name": self.configured.display_name,
            "default_branch": self.configured.default_branch,
            "state": "ready" if claimed else "claim_required",
            "version": 1 if claimed else 0,
            "control_plane": "legacy",
            "claim_action": None if claimed else claim_descriptor(),
        }


def _is_pristine_legacy_candidate(row) -> bool:
    return (
        row["scope_state"] == "unclaimed"
        and row["control_plane"] == "legacy"
        and row["version"] == 0
        and row["public_id"] is None
        and row["tenant_id"] is None
        and row["owner_user_id"] is None
        and row["configured_fingerprint"] is None
        and row["claimed_at"] is None
    )


def resolve_project(
    connection: Connection,
    *,
    actor: ActorScope,
    configured: ConfiguredProject,
) -> ProjectResolution:
    table = Project.__table__
    visible_scope = or_(
        and_(table.c.tenant_id.is_(None), table.c.owner_user_id.is_(None)),
        and_(
            table.c.tenant_id == actor.tenant_id,
            table.c.owner_user_id == actor.user_id,
        ),
    )
    configured_identity = or_(
        table.c.public_id == configured.public_id,
        table.c.configured_fingerprint == configured.fingerprint,
        table.c.root_identity_digest == configured.root_identity_digest,
    )
    rows = connection.execute(
        select(table)
        .where(visible_scope, configured_identity)
        .order_by(table.c.id)
        .limit(MAX_PROJECT_IDENTITY_ROWS + 1)
    ).all()
    if len(rows) > MAX_PROJECT_IDENTITY_ROWS:
        # ``root_identity_digest`` is intentionally non-unique: a legacy ledger
        # can contain several rows for the same physical checkout.  The bounded
        # ``+ 1`` probe therefore proves an ambiguous same-scope identity set; it
        # does not mean that root inspection became unavailable.  Failing closed
        # as quarantine preserves the invariant that an ambiguous configured
        # root can never be claimed, while keeping the query bounded.
        return ProjectResolution(
            "quarantined", ("same_scope_candidate_ambiguous",), configured
        )

    configured_row = None
    visible_candidates: list[str] = []
    same_scope_conflict = False
    uncertain_visible_identity = False

    for result_row in rows:
        row = result_row._mapping
        public_id_match = row["public_id"] == configured.public_id
        fingerprint_match = row["configured_fingerprint"] == configured.fingerprint
        root_identity_match = (
            row["root_identity_digest"] == configured.root_identity_digest
        )

        if public_id_match:
            configured_row = row
            continue
        if fingerprint_match:
            same_scope_conflict = True
        if not root_identity_match:
            continue
        same_path = paths_are_same(row["repo_path"], configured)
        if same_path is True:
            if _is_pristine_legacy_candidate(row):
                visible_candidates.append(str(row["id"]))
            else:
                same_scope_conflict = True
        else:
            uncertain_visible_identity = True

    if configured_row is not None:
        row = configured_row
        same_path = paths_are_same(row["repo_path"], configured)
        invariants_match = (
            same_path is True
            and row["root_identity_digest"] == configured.root_identity_digest
            and row["name"] == configured.display_name
            and row["default_branch"] == configured.default_branch
            and row["configured_fingerprint"] == configured.fingerprint
            and row["control_plane"] == "legacy"
        )
        if row["scope_state"] == "claimed":
            if (
                invariants_match
                and row["tenant_id"] == actor.tenant_id
                and row["owner_user_id"] == actor.user_id
                and row["claimed_at"] is not None
                and row["version"] == 1
            ):
                return ProjectResolution("claimed", (), configured, str(row["id"]))
            return ProjectResolution(
                "quarantined", ("claimed_invariant_mismatch",), configured
            )
        unclaimed_invariants_match = (
            invariants_match
            and row["scope_state"] == "unclaimed"
            and row["tenant_id"] is None
            and row["owner_user_id"] is None
            and row["claimed_at"] is None
            and row["version"] == 0
        )
        if not unclaimed_invariants_match:
            return ProjectResolution(
                "quarantined", ("same_scope_identity_conflict",), configured
            )
        return ProjectResolution("claim_required", (), configured, str(row["id"]))

    if same_scope_conflict or uncertain_visible_identity:
        return ProjectResolution(
            "quarantined", ("same_scope_identity_conflict",), configured
        )
    if len(visible_candidates) > 1:
        return ProjectResolution(
            "quarantined", ("same_scope_candidate_ambiguous",), configured
        )

    # Hidden row volume must never affect the visible bounded lookup. Every
    # collision key is persisted and indexed, so this lookup stays constant in
    # row count even when another scope owns many unrelated projects.
    hidden_scope = and_(
        or_(table.c.tenant_id.is_not(None), table.c.owner_user_id.is_not(None)),
        or_(
            table.c.tenant_id.is_(None),
            table.c.tenant_id != actor.tenant_id,
            table.c.owner_user_id.is_(None),
            table.c.owner_user_id != actor.user_id,
        ),
    )
    hidden_direct = connection.execute(
        select(
            table.c.public_id,
            table.c.configured_fingerprint,
            table.c.root_identity_digest,
            table.c.repo_path,
        )
        .where(hidden_scope, configured_identity)
        .order_by(table.c.id)
        .limit(1)
    ).mappings().first()
    if hidden_direct is not None:
        if (
            hidden_direct["root_identity_digest"]
            == configured.root_identity_digest
        ):
            # Final canonical/same-file verification is deliberately performed
            # after the indexed candidate lookup. A corrupted or inconclusive
            # colliding digest still fails closed without disclosing why.
            paths_are_same(hidden_direct["repo_path"], configured)
        return ProjectResolution("hidden", (), configured)
    return ProjectResolution(
        "claim_required",
        (),
        configured,
        visible_candidates[0] if visible_candidates else None,
    )


def resolve_project_read_only(
    *, actor: ActorScope, configured: ConfiguredProject, db_engine: Engine | None = None
) -> ProjectResolution:
    selected_engine = db_engine or database.engine
    try:
        with selected_engine.connect() as connection:
            try:
                if connection.dialect.name == "sqlite":
                    connection.exec_driver_sql("PRAGMA query_only=ON")
                    connection.exec_driver_sql("PRAGMA busy_timeout=1000")
                return resolve_project(connection, actor=actor, configured=configured)
            finally:
                if connection.dialect.name == "sqlite":
                    connection.rollback()
                    connection.exec_driver_sql("PRAGMA query_only=OFF")
                    connection.commit()
    except SupervisorHTTPError:
        raise
    except SQLAlchemyError as exc:
        raise SupervisorHTTPError(503, "dependency_unavailable") from exc


def claim_reserved_project(
    *,
    actor: ActorScope,
    configured: ConfiguredProject | None = None,
    project_id: str | None = None,
    reservation: Reservation,
    idempotency_key: str,
    expected_version: int,
    db_engine: Engine | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> Reservation:
    if not reservation.record_id or not reservation.raw_lease_token:
        raise SupervisorHTTPError(500, "internal_error")
    requested_project_id = project_id or (configured.public_id if configured else None)
    if requested_project_id is None:
        raise SupervisorHTTPError(500, "internal_error")
    selected_engine = db_engine or database.engine
    table = Project.__table__
    try:
        with selected_engine.connect() as connection:
            _begin_immediate(connection)
            verify_live_reservation(
                connection,
                record_id=reservation.record_id,
                raw_lease_token=reservation.raw_lease_token,
            )
            side_effects = connection.begin_nested()
            try:
                current_configuration = load_configured_project()
                if current_configuration.state == "unconfigured":
                    raise SupervisorHTTPError(503, "supervisor_unconfigured")
                if current_configuration.state == "quarantined":
                    raise SupervisorHTTPError(409, "supervisor_quarantined")
                if (
                    current_configuration.state == "dependency_unavailable"
                    or current_configuration.project is None
                ):
                    raise SupervisorHTTPError(503, "dependency_unavailable")
                if configured is not None and current_configuration.project != configured:
                    raise SupervisorHTTPError(409, "supervisor_quarantined")
                configured = current_configuration.project
                if requested_project_id != configured.public_id:
                    raise SupervisorHTTPError(404, "resource_not_found")
                resolution = resolve_project(connection, actor=actor, configured=configured)
                if resolution.state == "hidden":
                    raise SupervisorHTTPError(404, "resource_not_found")
                if resolution.state == "claimed":
                    raise SupervisorHTTPError(409, "invalid_state")
                if resolution.state == "quarantined":
                    raise SupervisorHTTPError(409, "supervisor_quarantined")
                if resolution.state == "dependency_unavailable":
                    raise SupervisorHTTPError(503, "dependency_unavailable")
                if expected_version != 0:
                    raise SupervisorHTTPError(412, "revision_conflict")

                claimed_at = datetime.now(timezone.utc).replace(microsecond=0)
                if failure_injector:
                    failure_injector("before_project_write")
                if resolution.row_id is None:
                    row_id = f"proj_{uuid.uuid4().hex}"
                    connection.execute(
                        table.insert().values(
                            id=row_id,
                            name=configured.display_name,
                            repo_path=configured.canonical_root,
                            default_branch=configured.default_branch,
                            public_id=configured.public_id,
                            tenant_id=actor.tenant_id,
                            owner_user_id=actor.user_id,
                            scope_state="claimed",
                            control_plane="legacy",
                            configured_fingerprint=configured.fingerprint,
                            root_identity_digest=configured.root_identity_digest,
                            claimed_at=claimed_at,
                            version=1,
                            created_at=claimed_at,
                            updated_at=claimed_at,
                        )
                    )
                else:
                    result = connection.execute(
                        update(table)
                        .where(table.c.id == resolution.row_id, table.c.scope_state == "unclaimed")
                        .values(
                            name=configured.display_name,
                            repo_path=configured.canonical_root,
                            default_branch=configured.default_branch,
                            public_id=configured.public_id,
                            tenant_id=actor.tenant_id,
                            owner_user_id=actor.user_id,
                            scope_state="claimed",
                            control_plane="legacy",
                            configured_fingerprint=configured.fingerprint,
                            root_identity_digest=configured.root_identity_digest,
                            claimed_at=claimed_at,
                            version=1,
                            updated_at=claimed_at,
                        )
                    )
                    if result.rowcount != 1:
                        raise SupervisorHTTPError(409, "claim_guard_failed")
                if failure_injector:
                    failure_injector("after_project_write")

                if failure_injector:
                    failure_injector("before_event_write")
                append_claim_event(
                    connection,
                    project_public_id=configured.public_id,
                    actor=actor,
                    project_version=1,
                    request_id=reservation.request_id,
                    idempotency_key=idempotency_key,
                )
                if failure_injector:
                    failure_injector("after_event_write")

                body_object = {
                    "data": {
                        "project": {
                            "project_id": configured.public_id,
                            "display_name": configured.display_name,
                            "default_branch": configured.default_branch,
                            "state": "ready",
                            "version": 1,
                            "control_plane": "legacy",
                        }
                    },
                    "meta": {
                        "request_id": reservation.request_id,
                        "schema_version": "0.1",
                        "resource_version": 1,
                        "idempotency_state": "succeeded",
                    },
                }
                body = canonical_json_bytes(body_object)
                headers = {
                    "Content-Type": "application/json",
                    "ETag": '"project-1"',
                    "Cache-Control": "no-store",
                    "X-Request-ID": reservation.request_id,
                }
                if failure_injector:
                    failure_injector("before_terminal_write")
                connection.execute(
                    update(IdempotencyRecord.__table__)
                    .where(IdempotencyRecord.__table__.c.id == reservation.record_id)
                    .values(
                        **terminal_values(
                            status="succeeded",
                            response_status=200,
                            response_body=body,
                            response_headers=headers,
                        )
                    )
                )
                if failure_injector:
                    failure_injector("after_terminal_write")
                side_effects.commit()
            except (SupervisorHTTPError, IntegrityError) as exc:
                side_effects.rollback()
                code = exc.code if isinstance(exc, SupervisorHTTPError) else "claim_guard_failed"
                status_code = exc.status_code if isinstance(exc, SupervisorHTTPError) else 409
                if code not in DETERMINISTIC_FAILURES:
                    connection.rollback()
                    raise
                body = canonical_json_bytes(error_body(reservation.request_id, code))
                headers = {
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                    "X-Request-ID": reservation.request_id,
                }
                if failure_injector:
                    failure_injector("before_failure_terminal_write")
                connection.execute(
                    update(IdempotencyRecord.__table__)
                    .where(IdempotencyRecord.__table__.c.id == reservation.record_id)
                    .values(
                        **terminal_values(
                            status="failed",
                            response_status=status_code,
                            response_body=body,
                            response_headers=headers,
                        )
                    )
                )
                if failure_injector:
                    failure_injector("after_failure_terminal_write")
                connection.commit()
                return Reservation(
                    "terminal_failure",
                    reservation.request_id,
                    response_status=status_code,
                    response_body=body,
                    response_headers=headers,
                )
            connection.commit()
        return Reservation(
            "success",
            reservation.request_id,
            response_status=200,
            response_body=body,
            response_headers=headers,
        )
    except SupervisorHTTPError:
        raise
    except IntegrityError as exc:
        raise SupervisorHTTPError(409, "claim_guard_failed") from exc
    except SQLAlchemyError as exc:
        raise SupervisorHTTPError(503, "dependency_unavailable") from exc
