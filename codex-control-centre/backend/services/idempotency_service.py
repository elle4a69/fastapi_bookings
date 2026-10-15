"""Durable two-phase idempotency reservations for supervisor actions."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import time
import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from backend import database
from backend.middleware.v2_errors import SupervisorHTTPError, canonical_json_bytes, error_body
from backend.models.codex import IdempotencyRecord
from backend.services.actor_scope import ActorScope


LEASE_SECONDS = 30
RETENTION_HOURS = 24


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def new_request_id() -> str:
    return f"req_{secrets.token_hex(16)}"


def _lease_material() -> tuple[str, str, str]:
    raw_token = secrets.token_hex(32)
    return (
        f"exe_{secrets.token_hex(16)}",
        raw_token,
        hashlib.sha256(raw_token.encode("ascii")).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class Reservation:
    mode: str
    request_id: str
    record_id: str | None = None
    raw_lease_token: str | None = None
    response_status: int | None = None
    response_body: bytes | None = None
    response_headers: dict[str, str] | None = None


def canonical_fingerprint(
    *,
    actor: ActorScope,
    project_id: str,
    expected_version: int,
    confirmation: bool,
) -> str:
    material = {
        "action": "claim_project",
        "actor_tenant_id": actor.tenant_id,
        "actor_user_id": actor.user_id,
        "confirmation": confirmation,
        "expected_version": expected_version,
        "method": "POST",
        "project_id": project_id,
        "registry_version": "0.2",
        "route": "/api/admin/codex/v2/projects/{project_id}/claim",
        "schema_version": "0.1",
    }
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _row_to_result(row, fingerprint: str, now: datetime) -> Reservation | None:
    if row is None:
        return None
    mapping = row._mapping
    if mapping["status"] == "in_progress":
        if mapping["request_fingerprint"] != fingerprint:
            return Reservation("conflict", mapping["request_id"])
        lease_expires = as_utc(mapping["lease_expires_at"])
        if lease_expires is not None and lease_expires > now:
            return Reservation("in_progress", mapping["request_id"])
        return None
    expires_at = as_utc(mapping["expires_at"])
    if expires_at is not None and expires_at > now:
        if mapping["request_fingerprint"] != fingerprint:
            return Reservation("conflict", mapping["request_id"])
        headers = json.loads(mapping["response_headers"])
        return Reservation(
            "replay",
            mapping["request_id"],
            response_status=mapping["response_status"],
            response_body=bytes(mapping["response_body"]),
            response_headers={str(key): str(value) for key, value in headers.items()},
        )
    return None


def _select_scoped(connection: Connection, actor: ActorScope, idempotency_key: str, action_code: str = "claim_project"):
    table = IdempotencyRecord.__table__
    return connection.execute(
        select(table).where(
            table.c.tenant_id == actor.tenant_id,
            table.c.user_id == actor.user_id,
            table.c.action_code == action_code,
            table.c.idempotency_key == idempotency_key,
        )
    ).first()


def _begin_immediate(connection: Connection) -> None:
    if connection.dialect.name != "sqlite":
        raise SupervisorHTTPError(503, "dependency_unavailable")
    connection.exec_driver_sql("PRAGMA busy_timeout=5000")
    connection.commit()
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def reserve(
    *,
    actor: ActorScope,
    idempotency_key: str,
    fingerprint: str,
    action_code: str = "claim_project",
    db_engine: Engine | None = None,
) -> Reservation:
    """Read first, then commit a short reservation or CAS reclaim."""
    selected_engine = db_engine or database.engine
    now = utc_now()
    started = time.monotonic()
    try:
        with selected_engine.connect() as connection:
            if connection.dialect.name != "sqlite":
                raise SupervisorHTTPError(503, "dependency_unavailable")
            try:
                connection.exec_driver_sql("PRAGMA query_only=ON")
                connection.exec_driver_sql("PRAGMA busy_timeout=1000")
                row = _select_scoped(connection, actor, idempotency_key, action_code)
                readable = _row_to_result(row, fingerprint, now)
            finally:
                connection.rollback()
                connection.exec_driver_sql("PRAGMA query_only=OFF")
                connection.commit()
        if time.monotonic() - started > 1.0:
            raise SupervisorHTTPError(503, "dependency_unavailable")
        if readable is not None:
            return readable

        lease_owner, raw_token, token_hash = _lease_material()
        request_id = new_request_id()
        acquired_at = utc_now()
        lease_expires_at = acquired_at + timedelta(seconds=LEASE_SECONDS)
        table = IdempotencyRecord.__table__
        with selected_engine.connect() as connection:
            _begin_immediate(connection)
            current = _select_scoped(connection, actor, idempotency_key, action_code)
            current_result = _row_to_result(current, fingerprint, utc_now())
            if current_result is not None:
                connection.rollback()
                return current_result

            values = {
                "request_fingerprint": fingerprint,
                "status": "in_progress",
                "completed_at": None,
                "expires_at": None,
                "lease_owner": lease_owner,
                "lease_token_hash": token_hash,
                "lease_acquired_at": acquired_at,
                "lease_expires_at": lease_expires_at,
                "response_status": None,
                "response_body": None,
                "response_headers": None,
            }
            if current is None:
                record_id = f"idem_{uuid.uuid4().hex}"
                connection.execute(
                    insert(table).values(
                        id=record_id,
                        tenant_id=actor.tenant_id,
                        user_id=actor.user_id,
                        action_code=action_code,
                        idempotency_key=idempotency_key,
                        request_id=request_id,
                        created_at=acquired_at,
                        **values,
                    )
                )
            else:
                old = current._mapping
                record_id = old["id"]
                old_status = old["status"]
                if old_status == "in_progress":
                    # Different fingerprints never reclaim an expired in-progress record.
                    if old["request_fingerprint"] != fingerprint:
                        connection.rollback()
                        return Reservation("conflict", old["request_id"])
                    preserved_request_id = old["request_id"]
                    result = connection.execute(
                        update(table)
                        .where(
                            table.c.id == record_id,
                            table.c.status == "in_progress",
                            table.c.lease_token_hash == old["lease_token_hash"],
                            table.c.lease_expires_at == old["lease_expires_at"],
                        )
                        .values(request_id=preserved_request_id, **values)
                    )
                    request_id = preserved_request_id
                else:
                    old_expiry = as_utc(old["expires_at"])
                    if old_expiry is None or old_expiry > utc_now():
                        connection.rollback()
                        return _row_to_result(current, fingerprint, utc_now()) or Reservation(
                            "conflict", old["request_id"]
                        )
                    result = connection.execute(
                        update(table)
                        .where(table.c.id == record_id, table.c.expires_at == old["expires_at"])
                        .values(request_id=request_id, created_at=acquired_at, **values)
                    )
                if result.rowcount != 1:
                    connection.rollback()
                    return reserve(
                        actor=actor,
                        idempotency_key=idempotency_key,
                        fingerprint=fingerprint,
                    action_code=action_code,
                        db_engine=selected_engine,
                    )
            connection.commit()
        return Reservation("execute", request_id, record_id, raw_token)
    except SupervisorHTTPError:
        raise
    except SQLAlchemyError as exc:
        raise SupervisorHTTPError(503, "dependency_unavailable") from exc


def verify_live_reservation(
    connection: Connection,
    *,
    record_id: str,
    raw_lease_token: str,
) -> object:
    token_hash = hashlib.sha256(raw_lease_token.encode("ascii")).hexdigest()
    table = IdempotencyRecord.__table__
    row = connection.execute(select(table).where(table.c.id == record_id)).first()
    if row is None:
        raise SupervisorHTTPError(503, "dependency_unavailable")
    mapping = row._mapping
    if (
        mapping["status"] != "in_progress"
        or mapping["lease_token_hash"] != token_hash
        or as_utc(mapping["lease_expires_at"]) <= utc_now()
    ):
        raise SupervisorHTTPError(503, "dependency_unavailable")
    return row


def terminal_values(
    *,
    status: str,
    response_status: int,
    response_body: bytes,
    response_headers: dict[str, str],
) -> dict[str, object]:
    completed_at = utc_now()
    return {
        "status": status,
        "completed_at": completed_at,
        "expires_at": completed_at + timedelta(hours=RETENTION_HOURS),
        "lease_owner": None,
        "lease_token_hash": None,
        "response_status": response_status,
        "response_body": response_body,
        "response_headers": json.dumps(response_headers, sort_keys=True, separators=(",", ":")),
    }


def terminalize_failure(
    *,
    reservation: Reservation,
    code: str,
    status_code: int,
    db_engine: Engine | None = None,
) -> Reservation:
    if not reservation.record_id or not reservation.raw_lease_token:
        raise SupervisorHTTPError(500, "internal_error")
    selected_engine = db_engine or database.engine
    body = canonical_json_bytes(error_body(reservation.request_id, code))
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "X-Request-ID": reservation.request_id,
    }
    try:
        with selected_engine.connect() as connection:
            _begin_immediate(connection)
            verify_live_reservation(
                connection,
                record_id=reservation.record_id,
                raw_lease_token=reservation.raw_lease_token,
            )
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
            connection.commit()
        return Reservation(
            "terminal_failure",
            reservation.request_id,
            response_status=status_code,
            response_body=body,
            response_headers=headers,
        )
    except SupervisorHTTPError:
        raise
    except SQLAlchemyError as exc:
        raise SupervisorHTTPError(503, "dependency_unavailable") from exc
