"""Transactional management of the persisted platform-owner capability.

This module is the sole supported writer for ``User.is_platform_owner``.  It
serializes every applied change across the database, applies the last-active-
owner invariant, and records the capability change in ``audit_logs`` in the
same transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ...models.audit import AuditLog
from ...models.user import User


MAX_INT32_ID = 2_147_483_647
POSTGRES_AUTHORITY_LOCK_KEY = 7_247_691_531_061_001
REASON_CODES = frozenset(
    {
        "initial_provisioning",
        "operator_change",
        "incident_response",
        "access_review",
        "rollback",
    }
)
_CHANGE_REF_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,64}$")


class PlatformOwnerAuthorityError(RuntimeError):
    """A stable, non-sensitive authority-management failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PlatformOwnerAuthorityResult:
    tenant_id: int
    user_id: int
    active: bool
    is_platform_owner: bool
    changed: bool
    applied: bool


def _validate_identity(tenant_id: int, user_id: int) -> None:
    if not (1 <= tenant_id <= MAX_INT32_ID and 1 <= user_id <= MAX_INT32_ID):
        raise PlatformOwnerAuthorityError("invalid_identity")


def _validate_change_metadata(reason_code: str, change_ref: str | None) -> None:
    if reason_code not in REASON_CODES:
        raise PlatformOwnerAuthorityError("invalid_reason_code")
    if change_ref is not None and _CHANGE_REF_RE.fullmatch(change_ref) is None:
        raise PlatformOwnerAuthorityError("invalid_change_ref")


def get_platform_owner_status(
    session: Session,
    *,
    tenant_id: int,
    user_id: int,
) -> PlatformOwnerAuthorityResult:
    """Return non-identifying authority state for one composite identity."""
    _validate_identity(tenant_id, user_id)
    user = (
        session.query(User)
        .filter(User.tenant_id == tenant_id, User.id == user_id)
        .one_or_none()
    )
    if user is None:
        raise PlatformOwnerAuthorityError("target_not_found")
    return PlatformOwnerAuthorityResult(
        tenant_id=tenant_id,
        user_id=user_id,
        active=user.is_active is True,
        is_platform_owner=user.is_platform_owner is True,
        changed=False,
        applied=False,
    )


def preview_platform_owner_change(
    session: Session,
    *,
    tenant_id: int,
    user_id: int,
    grant: bool,
) -> PlatformOwnerAuthorityResult:
    """Preview a change using a read-only lookup and without writing audit."""
    current = get_platform_owner_status(session, tenant_id=tenant_id, user_id=user_id)
    return PlatformOwnerAuthorityResult(
        tenant_id=current.tenant_id,
        user_id=current.user_id,
        active=current.active,
        is_platform_owner=current.is_platform_owner,
        changed=current.is_platform_owner is not grant,
        applied=False,
    )


def _acquire_mutation_lock(session: Session) -> str:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": POSTGRES_AUTHORITY_LOCK_KEY},
        )
    elif dialect == "sqlite":
        # BEGIN IMMEDIATE acquires SQLite's reserved writer lock before target
        # state is read, preventing two writers from passing the invariant.
        session.execute(text("BEGIN IMMEDIATE"))
    else:
        raise PlatformOwnerAuthorityError("unsupported_database")
    return dialect


def set_platform_owner(
    session: Session,
    *,
    tenant_id: int,
    user_id: int,
    grant: bool,
    reason_code: str,
    change_ref: str | None = None,
) -> PlatformOwnerAuthorityResult:
    """Apply one serialized, idempotent, transactionally audited change.

    The caller must supply a fresh session without an active transaction.  The
    function owns commit/rollback so the capability and audit record cannot be
    persisted separately.
    """
    _validate_identity(tenant_id, user_id)
    _validate_change_metadata(reason_code, change_ref)
    if session.in_transaction():
        raise PlatformOwnerAuthorityError("transaction_already_active")

    try:
        dialect = _acquire_mutation_lock(session)
        query = session.query(User).filter(
            User.tenant_id == tenant_id,
            User.id == user_id,
        )
        if dialect == "postgresql":
            query = query.with_for_update()
        user = query.one_or_none()
        if user is None:
            raise PlatformOwnerAuthorityError("target_not_found")

        previous_value = user.is_platform_owner is True
        if previous_value is grant:
            session.commit()
            return PlatformOwnerAuthorityResult(
                tenant_id=tenant_id,
                user_id=user_id,
                active=user.is_active is True,
                is_platform_owner=previous_value,
                changed=False,
                applied=True,
            )

        if not grant and user.is_active is True:
            active_owner_count = (
                session.query(func.count(User.id))
                .filter(
                    User.is_platform_owner.is_(True),
                    User.is_active.is_(True),
                )
                .scalar()
            )
            if active_owner_count == 1:
                raise PlatformOwnerAuthorityError("last_active_platform_owner")

        user.is_platform_owner = grant
        details = {
            "new_value": grant,
            "previous_value": previous_value,
            "reason_code": reason_code,
            "source": "offline_cli",
        }
        if change_ref is not None:
            details["change_ref"] = change_ref
        session.add(
            AuditLog(
                tenant_id=tenant_id,
                user_id=None,
                action="platform_owner.granted" if grant else "platform_owner.revoked",
                target_type="user",
                target_id=user_id,
                details=json.dumps(details, sort_keys=True, separators=(",", ":")),
            )
        )
        session.commit()
        return PlatformOwnerAuthorityResult(
            tenant_id=tenant_id,
            user_id=user_id,
            active=user.is_active is True,
            is_platform_owner=grant,
            changed=True,
            applied=True,
        )
    except PlatformOwnerAuthorityError:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise PlatformOwnerAuthorityError("transaction_failed") from exc
