"""Fail-closed structural evidence services for the V2 supervisor.

This module intentionally has no dependency on worker, turn, item, event-stream,
worktree, or audit-execution services. It stores digests and fixed codes only.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Connection

from backend.middleware.v2_errors import SupervisorHTTPError
from backend.models.codex import (
    PlanningAuditScope, PlanningWorkPackage, Project, SupervisorAcceptanceContract,
    SupervisorAuditCriterionResult, SupervisorAuditRequest, SupervisorRun,
    SupervisorRunBaseline, SupervisorSandboxAttestation,
)
from backend.services.actor_scope import ActorScope
from backend.services.idempotency_service import utc_now

CRITERION_CODES = (
    "repository_identity_bound",
    "baseline_captured",
    "sandbox_attested",
)
CONTRACT_REGISTRY_VERSION = "1"


def _row(connection: Connection, table, identifier: str, actor: ActorScope):
    value = connection.execute(select(table).where(
        table.c.id == identifier, table.c.tenant_id == actor.tenant_id,
        table.c.owner_user_id == actor.user_id,
    )).mappings().first()
    if value is None:
        raise SupervisorHTTPError(404, "resource_not_found")
    return value


def _codes_json() -> str:
    return json.dumps(list(CRITERION_CODES), separators=(",", ":"))


def create_acceptance_contract(connection: Connection, *, work_package_id: str, actor: ActorScope) -> dict[str, object]:
    work = _row(connection, PlanningWorkPackage.__table__, work_package_id, actor)
    audit = connection.execute(select(PlanningAuditScope.__table__).where(
        PlanningAuditScope.__table__.c.work_package_id == work_package_id,
        PlanningAuditScope.__table__.c.tenant_id == actor.tenant_id,
        PlanningAuditScope.__table__.c.owner_user_id == actor.user_id,
    )).mappings().first()
    project = _row(connection, Project.__table__, str(work["project_id"]), actor)
    if work["state"] != "brief_approved" or audit is None or project["scope_state"] != "claimed":
        raise SupervisorHTTPError(409, "acceptance_contract_prerequisite_required")
    if connection.execute(select(SupervisorAcceptanceContract.__table__.c.id).where(
        SupervisorAcceptanceContract.__table__.c.work_package_id == work_package_id
    )).first() is not None:
        raise SupervisorHTTPError(409, "acceptance_contract_exists")
    now = utc_now()
    codes = _codes_json()
    row = {
        "id": "acc_" + uuid.uuid4().hex, "project_id": project["id"],
        "work_package_id": work_package_id, "audit_scope_id": audit["id"],
        "tenant_id": actor.tenant_id, "owner_user_id": actor.user_id,
        "registry_version": CONTRACT_REGISTRY_VERSION, "criterion_codes": codes,
        "criterion_digest": hashlib.sha256(codes.encode("utf-8")).hexdigest(),
        "state": "approved", "created_at": now, "approved_at": now,
    }
    connection.execute(SupervisorAcceptanceContract.__table__.insert().values(**row))
    return row


def require_execution_contract(connection: Connection, *, work_package_id: str, actor: ActorScope) -> dict[str, object]:
    row = connection.execute(select(SupervisorAcceptanceContract.__table__).where(
        SupervisorAcceptanceContract.__table__.c.work_package_id == work_package_id,
        SupervisorAcceptanceContract.__table__.c.tenant_id == actor.tenant_id,
        SupervisorAcceptanceContract.__table__.c.owner_user_id == actor.user_id,
        SupervisorAcceptanceContract.__table__.c.state == "approved",
        SupervisorAcceptanceContract.__table__.c.registry_version == CONTRACT_REGISTRY_VERSION,
        SupervisorAcceptanceContract.__table__.c.criterion_codes == _codes_json(),
    )).mappings().first()
    if row is None:
        raise SupervisorHTTPError(409, "approved_acceptance_contract_required")
    return row


def capture_baseline(connection: Connection, *, run_id: str, project: dict[str, object], actor: ActorScope) -> dict[str, object]:
    """Capture only Git object identifiers; fail closed before any dispatch."""
    root = Path(str(project["repo_path"])).resolve()
    try:
        values = []
        # `HEAD^{tree}` is read-only. Do not use `write-tree`: even if it
        # usually returns an existing object, it is not an acceptable baseline
        # probe for a supervisor that must not mutate a repository.
        for args in (("rev-parse", "--show-toplevel"), ("rev-parse", "HEAD"), ("rev-parse", "HEAD^{tree}")):
            result = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, timeout=5, check=False)
            if result.returncode != 0:
                raise OSError("git_preflight_failed")
            values.append(result.stdout.strip())
        actual_root, head, tree = values
        if Path(actual_root).resolve() != root or len(head) not in {40, 64} or len(tree) not in {40, 64}:
            raise OSError("git_preflight_invalid")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise SupervisorHTTPError(503, "baseline_preflight_unavailable") from exc
    # SHA-256 makes the representation stable without recording a filesystem path.
    digest = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    now = utc_now()
    row = {"id": "rbl_" + uuid.uuid4().hex, "run_id": run_id, "tenant_id": actor.tenant_id,
           "owner_user_id": actor.user_id, "repository_identity_digest": digest(actual_root),
           "head_commit_digest": digest(head), "tree_digest": digest(tree), "captured_at": now}
    connection.execute(SupervisorRunBaseline.__table__.insert().values(**row))
    return row


def request_independent_audit(connection: Connection, *, run_id: str, actor: ActorScope) -> dict[str, object]:
    """Record an honest unavailable state; this package cannot run an auditor."""
    run = _row(connection, SupervisorRun.__table__, run_id, actor)
    existing = connection.execute(select(SupervisorAuditRequest.__table__).where(
        SupervisorAuditRequest.__table__.c.run_id == run_id,
        SupervisorAuditRequest.__table__.c.tenant_id == actor.tenant_id,
        SupervisorAuditRequest.__table__.c.owner_user_id == actor.user_id,
    )).mappings().first()
    if existing is not None:
        return existing
    contract = require_execution_contract(connection, work_package_id=str(run["work_package_id"]), actor=actor)
    baseline = connection.execute(select(SupervisorRunBaseline.__table__).where(
        SupervisorRunBaseline.__table__.c.run_id == run_id,
        SupervisorRunBaseline.__table__.c.tenant_id == actor.tenant_id,
        SupervisorRunBaseline.__table__.c.owner_user_id == actor.user_id,
    )).mappings().first()
    if baseline is None:
        raise SupervisorHTTPError(409, "run_baseline_required")
    # No host-enforced sandbox issuer exists in this package. Checking the
    # ledger is deliberately not a substitute for executing a sandbox.
    now = utc_now()
    state = "sandbox_unavailable"
    request = {"id": "arq_" + uuid.uuid4().hex, "run_id": run_id,
               "tenant_id": actor.tenant_id, "owner_user_id": actor.user_id,
               "contract_id": contract["id"], "baseline_id": baseline["id"],
               "state": state, "requested_at": now}
    connection.execute(SupervisorAuditRequest.__table__.insert().values(**request))
    for code in CRITERION_CODES:
        connection.execute(SupervisorAuditCriterionResult.__table__.insert().values(
            id="acr_" + uuid.uuid4().hex, audit_request_id=request["id"], criterion_code=code,
            outcome="not_evaluated", evidence_digest=None, recorded_at=now,
        ))
    return request


def public_contract(row: dict[str, object]) -> dict[str, object]:
    return {"contract_id": row["id"], "work_package_id": row["work_package_id"],
            "registry_version": row["registry_version"], "criterion_codes": list(CRITERION_CODES),
            "state": row["state"], "created_at": row["created_at"].isoformat()}


def public_audit_request(row: dict[str, object]) -> dict[str, object]:
    return {"audit_request_id": row["id"], "run_id": row["run_id"], "state": row["state"],
            "requested_at": row["requested_at"].isoformat()}
