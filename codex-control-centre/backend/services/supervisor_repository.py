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
from backend.services.supervisor_event_service import append_claim_event


MAX_PROJECT_IDENTITY_ROWS = 512
DETERMINISTIC_FAILURES = {
    "resource_not_found",
    "invalid_state",
    "claim_guard_failed",
    "supervisor_quarantined",
    "revision_conflict",
    "supervisor_unconfigured",
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
