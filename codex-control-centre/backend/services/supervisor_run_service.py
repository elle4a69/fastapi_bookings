"""Bounded V2 dispatch bridge.

This module deliberately does not import legacy routers or their HTTP contracts.
It uses the native WorkerManager/worktree primitives only after a durable intent
has been committed. No retry path re-drives an uncertain external launch.
"""
from __future__ import annotations

from datetime import timedelta
import hashlib
import secrets
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from backend.middleware.v2_errors import SupervisorHTTPError
from backend.models.codex import (
    PlanningAuditScope, PlanningBrief, PlanningWorkPackage, Project,
    SupervisorDispatchAttempt, SupervisorRun, SupervisorRunStartAuthorizationGrant,
)
from backend.services.actor_scope import ActorScope
from backend.services.idempotency_service import utc_now
from backend.services.worker_manager import worker_manager
from backend.services.evidence_audit_service import capture_baseline, require_execution_contract


CAPABILITY_PROFILE = "development_worker_v1"
GRANT_LIFETIME_SECONDS = 120


def _scoped_row(connection: Connection, table, identifier: str, actor: ActorScope):
    row = connection.execute(select(table).where(
        table.c.id == identifier, table.c.tenant_id == actor.tenant_id,
        table.c.owner_user_id == actor.user_id,
    )).mappings().first()
    if row is None:
        raise SupervisorHTTPError(404, "resource_not_found")
    return row


def _resolved_execution_material(connection: Connection, work_package_id: str, actor: ActorScope):
    work = _scoped_row(connection, PlanningWorkPackage.__table__, work_package_id, actor)
    brief = connection.execute(select(PlanningBrief.__table__).where(
        PlanningBrief.__table__.c.work_package_id == work_package_id,
        PlanningBrief.__table__.c.tenant_id == actor.tenant_id,
        PlanningBrief.__table__.c.owner_user_id == actor.user_id,
        PlanningBrief.__table__.c.state == "approved",
    ).order_by(PlanningBrief.__table__.c.revision.desc()).limit(1)).mappings().first()
    audit = connection.execute(select(PlanningAuditScope.__table__).where(
        PlanningAuditScope.__table__.c.work_package_id == work_package_id,
        PlanningAuditScope.__table__.c.tenant_id == actor.tenant_id,
        PlanningAuditScope.__table__.c.owner_user_id == actor.user_id,
    )).mappings().first()
    project = _scoped_row(connection, Project.__table__, str(work["project_id"]), actor)
    if work["state"] != "brief_approved" or brief is None:
        raise SupervisorHTTPError(409, "approved_brief_required")
    if audit is None:
        raise SupervisorHTTPError(409, "audit_scope_required")
    if project["scope_state"] != "claimed":
        raise SupervisorHTTPError(404, "resource_not_found")
    return work, brief, audit, project


def _capability_profile() -> dict[str, object]:
    # Server-owned, fixed and intentionally narrower than the legacy turn path.
    return {"name": CAPABILITY_PROFILE, "workspace": "server_owned_worktree", "tool_policy": "no_client_grants"}


def _assert_safe_runtime(project: dict[str, object]) -> Path:
    root = Path(str(project["repo_path"])).resolve()
    if not root.is_dir() or not (root / ".git").exists():
        raise SupervisorHTTPError(503, "dispatch_prerequisite_unavailable")
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=str(root), capture_output=True,
            text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SupervisorHTTPError(503, "dispatch_prerequisite_unavailable") from exc
    if result.returncode != 0 or Path(result.stdout.strip()).resolve() != root:
        raise SupervisorHTTPError(503, "dispatch_prerequisite_unavailable")
    command = getattr(worker_manager, "command", None)
    if not isinstance(command, list) or not command or not callable(getattr(worker_manager, "get_worker_for_thread", None)):
        raise SupervisorHTTPError(503, "dispatch_prerequisite_unavailable")
    return root


def issue_start_authorization(
    connection: Connection, *, work_package_id: str, actor: ActorScope,
    waiver_requested: bool,
) -> tuple[dict[str, object], str]:
    """Create an owner-confirmed grant and reveal its opaque token once.

    The token is returned directly to the request caller and is deliberately
    never placed in a database row, idempotency replay body, event, or log.
    """
    work, brief, audit, project = _resolved_execution_material(connection, work_package_id, actor)
    policy = str(brief["future_execution_authorization_requirement"])
    if policy == "not_required_once_requested" and not waiver_requested:
        raise SupervisorHTTPError(422, "authorization_waiver_not_requested")
    now = utc_now()
    # Issuance intentionally has no replay body because storing/replaying the
    # opaque token would violate the hash-only contract. BEGIN IMMEDIATE at
    # the route serializes this predicate with the insert: a retry sees the
    # active grant and cannot mint another usable token.
    active = connection.execute(select(SupervisorRunStartAuthorizationGrant.__table__.c.id).where(
        SupervisorRunStartAuthorizationGrant.__table__.c.project_id == project["id"],
        SupervisorRunStartAuthorizationGrant.__table__.c.work_package_id == work_package_id,
        SupervisorRunStartAuthorizationGrant.__table__.c.brief_id == brief["id"],
        SupervisorRunStartAuthorizationGrant.__table__.c.audit_scope_id == audit["id"],
        SupervisorRunStartAuthorizationGrant.__table__.c.tenant_id == actor.tenant_id,
        SupervisorRunStartAuthorizationGrant.__table__.c.owner_user_id == actor.user_id,
        SupervisorRunStartAuthorizationGrant.__table__.c.consumed_at.is_(None),
        SupervisorRunStartAuthorizationGrant.__table__.c.expires_at > now,
    )).first()
    if active is not None:
        raise SupervisorHTTPError(409, "start_authorization_already_issued")
    token = secrets.token_urlsafe(32)
    grant = {
        "id": "sag_" + uuid.uuid4().hex, "project_id": project["id"],
        "work_package_id": work_package_id, "brief_id": brief["id"],
        "audit_scope_id": audit["id"], "tenant_id": actor.tenant_id,
        "owner_user_id": actor.user_id,
        "authorization_hash": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "policy": policy, "issued_at": now,
        "expires_at": now + timedelta(seconds=GRANT_LIFETIME_SECONDS),
        "consumed_at": None, "run_id": None,
    }
    connection.execute(SupervisorRunStartAuthorizationGrant.__table__.insert().values(**grant))
    return grant, token


def create_intent(
    connection: Connection, *, work_package_id: str, actor: ActorScope,
    request_id: str, grant_token: str,
) -> dict[str, object]:
    """Atomically create/consume a server-only grant and one dispatch intent."""
    work, brief, audit, project = _resolved_execution_material(connection, work_package_id, actor)
    # Legacy planning/run rows have no immutable fixed-code contract and are
    # deliberately ineligible. This also avoids treating free-text audit scope
    # as executable acceptance criteria.
    require_execution_contract(connection, work_package_id=work_package_id, actor=actor)
    active = connection.execute(select(SupervisorRun.__table__.c.id).where(
        SupervisorRun.__table__.c.work_package_id == work_package_id,
        SupervisorRun.__table__.c.tenant_id == actor.tenant_id,
        SupervisorRun.__table__.c.owner_user_id == actor.user_id,
        SupervisorRun.__table__.c.status.in_(("dispatching", "dispatch_acknowledged", "dispatch_unknown")),
    )).first()
    if active is not None:
        raise SupervisorHTTPError(409, "active_run_exists")
    now = utc_now()
    run_id = "run_" + uuid.uuid4().hex
    if not isinstance(grant_token, str) or not grant_token or len(grant_token) > 256:
        raise SupervisorHTTPError(422, "invalid_start_authorization")
    grant = connection.execute(select(SupervisorRunStartAuthorizationGrant.__table__).where(
        SupervisorRunStartAuthorizationGrant.__table__.c.authorization_hash == hashlib.sha256(grant_token.encode("ascii")).hexdigest(),
        SupervisorRunStartAuthorizationGrant.__table__.c.project_id == project["id"],
        SupervisorRunStartAuthorizationGrant.__table__.c.work_package_id == work_package_id,
        SupervisorRunStartAuthorizationGrant.__table__.c.brief_id == brief["id"],
        SupervisorRunStartAuthorizationGrant.__table__.c.audit_scope_id == audit["id"],
        SupervisorRunStartAuthorizationGrant.__table__.c.tenant_id == actor.tenant_id,
        SupervisorRunStartAuthorizationGrant.__table__.c.owner_user_id == actor.user_id,
        SupervisorRunStartAuthorizationGrant.__table__.c.consumed_at.is_(None),
        SupervisorRunStartAuthorizationGrant.__table__.c.expires_at > now,
    )).mappings().first()
    if grant is None:
        raise SupervisorHTTPError(409, "start_authorization_unavailable")
    grant_id = str(grant["id"])
    consumed = connection.execute(update(SupervisorRunStartAuthorizationGrant.__table__).where(
        SupervisorRunStartAuthorizationGrant.__table__.c.id == grant_id,
        SupervisorRunStartAuthorizationGrant.__table__.c.consumed_at.is_(None),
        SupervisorRunStartAuthorizationGrant.__table__.c.expires_at > now,
    ).values(consumed_at=now, run_id=run_id))
    if consumed.rowcount != 1:
        raise SupervisorHTTPError(409, "start_authorization_unavailable")
    connection.execute(SupervisorRun.__table__.insert().values(
        id=run_id, project_id=project["id"], work_package_id=work_package_id,
        brief_id=brief["id"], audit_scope_id=audit["id"], grant_id=grant_id,
        tenant_id=actor.tenant_id, owner_user_id=actor.user_id,
        brief_content_digest=brief["content_digest"], capability_profile=CAPABILITY_PROFILE,
        status="dispatching", request_id=request_id, created_at=now, dispatched_at=now,
    ))
    connection.execute(SupervisorDispatchAttempt.__table__.insert().values(
        id="dpa_" + uuid.uuid4().hex, run_id=run_id, tenant_id=actor.tenant_id,
        owner_user_id=actor.user_id, attempt_number=1, state="intent_persisted", created_at=now,
    ))
    # Structural Git identity is captured in the same transaction as the
    # dispatch intent. A failed preflight rolls the entire intent back, so the
    # external worker is never reached without a durable baseline.
    capture_baseline(connection, run_id=run_id, project=dict(project), actor=actor)
    return {"run_id": run_id, "brief_content": str(brief["content"]), "project": dict(project)}


async def launch_intent(intent: dict[str, object]) -> str:
    """Call the real app-server primitive once. No fallback or automatic retry."""
    project = intent["project"]
    root = _assert_safe_runtime(project)
    run_id = str(intent["run_id"])
    try:
        worker = await worker_manager.get_worker_for_thread(
            run_id, repo_path=str(root), base_branch=str(project["default_branch"]),
        )
        workspace = str((root / "worktrees" / f"wt-{run_id}").resolve())
        thread_ack = await worker.send_request("thread/start", {"cwd": workspace})
        thread = thread_ack.get("thread", {}) if isinstance(thread_ack, dict) else {}
        thread_id = thread.get("id") if isinstance(thread, dict) else None
        if not isinstance(thread_id, str) or not thread_id:
            raise RuntimeError("invalid_app_server_thread_ack")
        ack = await worker.send_request("turn/start", {
            "threadId": thread_id, "prompt": str(intent["brief_content"]),
            "input": [{"type": "text", "text": str(intent["brief_content"])}],
            "workspaceRoot": workspace, "cwd": workspace,
            "capabilityProfile": _capability_profile(),
        })
        if not isinstance(ack, dict):
            raise RuntimeError("invalid_app_server_turn_ack")
        return "dispatch_acknowledged"
    except SupervisorHTTPError:
        raise
    except Exception:
        # The caller records this as unknown because process/transport failure
        # does not establish whether app-server accepted the launch.
        return "dispatch_unknown"


def record_launch_outcome(connection: Connection, *, run_id: str, actor: ActorScope, outcome: str) -> None:
    now = utc_now()
    if outcome not in {"dispatch_acknowledged", "dispatch_unknown", "dispatch_rejected"}:
        raise SupervisorHTTPError(500, "internal_error")
    attempt_state = {"dispatch_acknowledged": "acknowledged", "dispatch_unknown": "dispatch_unknown", "dispatch_rejected": "rejected"}[outcome]
    connection.execute(update(SupervisorRun.__table__).where(
        SupervisorRun.__table__.c.id == run_id, SupervisorRun.__table__.c.tenant_id == actor.tenant_id,
        SupervisorRun.__table__.c.owner_user_id == actor.user_id, SupervisorRun.__table__.c.status == "dispatching",
    ).values(status=outcome, acknowledged_at=now if outcome == "dispatch_acknowledged" else None))
    connection.execute(update(SupervisorDispatchAttempt.__table__).where(
        SupervisorDispatchAttempt.__table__.c.run_id == run_id, SupervisorDispatchAttempt.__table__.c.tenant_id == actor.tenant_id,
        SupervisorDispatchAttempt.__table__.c.owner_user_id == actor.user_id,
    ).values(state=attempt_state, acknowledged_at=now if outcome == "dispatch_acknowledged" else None))


def public_run(connection: Connection, run_id: str, actor: ActorScope) -> dict[str, object]:
    row = _scoped_row(connection, SupervisorRun.__table__, run_id, actor)
    return {"run_id": row["id"], "work_package_id": row["work_package_id"], "brief_id": row["brief_id"], "audit_scope_id": row["audit_scope_id"], "capability_profile": row["capability_profile"], "status": row["status"], "created_at": row["created_at"].isoformat()}
