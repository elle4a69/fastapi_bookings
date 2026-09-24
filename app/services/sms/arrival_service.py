"""Secure booking-linked arrival sessions and deduplicated staff alerts."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Integer, String, cast, exists, func, literal, null, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.state_machine import BookingStatus
from ...core.config import settings
from ...models.booking import Booking
from ...models.client import Client
from ...models.location import Location
from ...models.outbox import OutboxEvent
from ...models.provider import Provider
from ...models.service import Service
from ...models.sms_account import SmsAccount
from ...models.sms_arrival import SmsArrivalSession
from ...models.sms_conversation import SmsConversation
from ...models.sms_outbox import SmsConversationEvent
from ...models.user import User

logger = logging.getLogger(__name__)

ARRIVAL_TOKEN_MAX_AGE = timedelta(days=7)
ARRIVAL_POST_BOOKING_GRACE = timedelta(hours=4)
ARRIVAL_ALERT_INTERVAL_SECONDS = 60
ARRIVAL_ALERT_BATCH_LIMIT = 100
ARRIVAL_TOKEN_COLLISION_RETRIES = 3
_PENDING_OUTBOX_STATUSES = ("PENDING", "RETRY")
_ARRIVAL_SCOPE_INVALID = "ARRIVAL_SCOPE_INVALID"


class ArrivalNotFoundError(LookupError):
    """No session is available within the requested security scope."""


class ArrivalExpiredError(LookupError):
    """The arrival capability is no longer valid."""


class ArrivalStateError(ValueError):
    """The lifecycle transition is not permitted."""


class ArrivalPersistenceError(RuntimeError):
    """Arrival persistence failed without exposing database error details."""


@dataclass(frozen=True)
class ArrivalInvitation:
    """One-time return value for an invitation producer.

    ``token`` is never persisted or logged. The eventual reminder/link producer
    must commit the session and invitation atomically before exposing the token.
    """

    session: SmsArrivalSession
    token: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class ScopedArrival:
    session: SmsArrivalSession
    booking: Booking
    conversation: SmsConversation
    account: SmsAccount


@dataclass(frozen=True)
class ArrivalMutation:
    scoped: ScopedArrival
    changed: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_arrival_token(token: str) -> str:
    """Return the SHA-256 digest stored for a bearer arrival capability."""

    normalized = (token or "").strip()
    if len(normalized) < 24 or len(normalized) > 512:
        raise ArrivalNotFoundError("arrival session is unavailable")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def arrival_expires_at(arrival: SmsArrivalSession, booking: Booking) -> datetime:
    """Compute bounded expiry without requiring a schema migration."""

    created_at = _as_utc(arrival.created_at)
    booking_end = _as_utc(booking.end_time)
    return min(
        created_at + ARRIVAL_TOKEN_MAX_AGE,
        booking_end + ARRIVAL_POST_BOOKING_GRACE,
    )


def _booking_status(booking: Booking) -> str:
    value = getattr(booking.status, "value", booking.status)
    return str(value or "").lower()


def _arrival_integrity_kind(exc: IntegrityError) -> Optional[str]:
    """Classify only known arrival uniqueness failures without exposing details."""

    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint == "ix_sms_arrival_sessions_booking_id":
        return "booking"
    if constraint == "ix_sms_arrival_sessions_token":
        return "token"

    # SQLite does not expose a constraint name. Inspect only the exact column
    # marker internally; callers and logs receive a structural error instead.
    detail = str(exc.orig).lower()
    if "unique constraint failed: sms_arrival_sessions.booking_id" in detail:
        return "booking"
    if "unique constraint failed: sms_arrival_sessions.token" in detail:
        return "token"
    return None


def arrival_booking_is_eligible(booking: Booking) -> bool:
    """Return whether the booking may still participate in arrival handling."""

    return _booking_status(booking) == "confirmed"


def _validate_scope(
    *,
    tenant_id: int,
    booking: Booking,
    conversation: SmsConversation,
    account: SmsAccount,
    client_tenant_id: int,
    provider_tenant_id: int,
    service_tenant_id: int,
    location_tenant_id: Optional[int],
) -> None:
    """Enforce the transitive tenant/provider/account/client boundary."""

    if tenant_id <= 0:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if booking.tenant_id != tenant_id or conversation.tenant_id != tenant_id:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if account.tenant_id != tenant_id or conversation.sms_account_id != account.id:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if client_tenant_id != tenant_id or provider_tenant_id != tenant_id:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if service_tenant_id != tenant_id:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if booking.location_id is not None and location_tenant_id != tenant_id:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if booking.provider_id != conversation.provider_id:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if account.provider_id != conversation.provider_id:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if conversation.client_id != booking.client_id:
        raise ArrivalNotFoundError("arrival session is unavailable")


def _scoped_query(db: Session):
    return (
        db.query(
            SmsArrivalSession,
            Booking,
            SmsConversation,
            SmsAccount,
            Client.tenant_id.label("client_tenant_id"),
            Provider.tenant_id.label("provider_tenant_id"),
            Service.tenant_id.label("service_tenant_id"),
            Location.tenant_id.label("location_tenant_id"),
        )
        .join(Booking, Booking.id == SmsArrivalSession.booking_id)
        .join(SmsConversation, SmsConversation.id == SmsArrivalSession.conversation_id)
        .join(SmsAccount, SmsAccount.id == SmsConversation.sms_account_id)
        .join(Client, Client.id == Booking.client_id)
        .join(Provider, Provider.id == Booking.provider_id)
        .join(Service, Service.id == Booking.service_id)
        .outerjoin(Location, Location.id == Booking.location_id)
    )


def _valid_scope_predicates():
    """Return scope relationships cheap enough to reject before batching."""

    return (
        Booking.tenant_id == SmsConversation.tenant_id,
        Booking.tenant_id == SmsAccount.tenant_id,
        Booking.tenant_id == Client.tenant_id,
        Booking.tenant_id == Provider.tenant_id,
        Booking.tenant_id == Service.tenant_id,
        or_(Booking.location_id.is_(None), Booking.tenant_id == Location.tenant_id),
        Booking.provider_id == SmsConversation.provider_id,
        SmsAccount.provider_id == SmsConversation.provider_id,
        SmsConversation.client_id == Booking.client_id,
    )


def _to_scoped(row) -> ScopedArrival:
    (
        arrival,
        booking,
        conversation,
        account,
        client_tenant_id,
        provider_tenant_id,
        service_tenant_id,
        location_tenant_id,
    ) = row
    _validate_scope(
        tenant_id=booking.tenant_id,
        booking=booking,
        conversation=conversation,
        account=account,
        client_tenant_id=client_tenant_id,
        provider_tenant_id=provider_tenant_id,
        service_tenant_id=service_tenant_id,
        location_tenant_id=location_tenant_id,
    )
    return ScopedArrival(arrival, booking, conversation, account)


def create_arrival_session(
    db: Session,
    tenant_id: int,
    conversation_id: int,
    booking_id: int,
    *,
    now: Optional[datetime] = None,
) -> ArrivalInvitation:
    """Create a digest-backed arrival capability after verifying all scopes.

    The caller owns the transaction so session creation and invitation dispatch
    can eventually be atomic. Reissuing an existing booking capability is
    rejected because the original plaintext token cannot be recovered.
    """

    current_time = _as_utc(now or datetime.now(timezone.utc))
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id, Booking.tenant_id == tenant_id)
        .first()
    )
    conversation = (
        db.query(SmsConversation)
        .filter(
            SmsConversation.id == conversation_id,
            SmsConversation.tenant_id == tenant_id,
        )
        .first()
    )
    if booking is None or conversation is None or conversation.sms_account_id is None:
        raise ArrivalNotFoundError("arrival session is unavailable")
    account = (
        db.query(SmsAccount)
        .filter(
            SmsAccount.id == conversation.sms_account_id,
            SmsAccount.tenant_id == tenant_id,
        )
        .first()
    )
    if account is None:
        raise ArrivalNotFoundError("arrival session is unavailable")
    client_scope = (
        db.query(Client.id)
        .filter(Client.id == booking.client_id, Client.tenant_id == tenant_id)
        .first()
    )
    provider_scope = (
        db.query(Provider.id)
        .filter(Provider.id == booking.provider_id, Provider.tenant_id == tenant_id)
        .first()
    )
    service_scope = (
        db.query(Service.id)
        .filter(Service.id == booking.service_id, Service.tenant_id == tenant_id)
        .first()
    )
    location_scope = None
    if booking.location_id is not None:
        location_scope = (
            db.query(Location.id)
            .filter(Location.id == booking.location_id, Location.tenant_id == tenant_id)
            .first()
        )
    if (
        client_scope is None
        or provider_scope is None
        or service_scope is None
        or (booking.location_id is not None and location_scope is None)
    ):
        raise ArrivalNotFoundError("arrival session is unavailable")
    _validate_scope(
        tenant_id=tenant_id,
        booking=booking,
        conversation=conversation,
        account=account,
        client_tenant_id=tenant_id,
        provider_tenant_id=tenant_id,
        service_tenant_id=tenant_id,
        location_tenant_id=tenant_id if location_scope is not None else None,
    )
    if not arrival_booking_is_eligible(booking):
        raise ArrivalStateError("arrival invitations require a confirmed booking")
    if _as_utc(booking.end_time) + ARRIVAL_POST_BOOKING_GRACE <= current_time:
        raise ArrivalExpiredError("arrival session is unavailable")
    if (
        db.query(SmsArrivalSession.id)
        .filter(SmsArrivalSession.booking_id == booking_id)
        .first()
        is not None
    ):
        raise ArrivalStateError("arrival session already exists for this booking")

    arrival = None
    raw_token = ""
    for attempt in range(ARRIVAL_TOKEN_COLLISION_RETRIES):
        raw_token = secrets.token_urlsafe(32)
        candidate = SmsArrivalSession(
            conversation_id=conversation_id,
            booking_id=booking_id,
            token=hash_arrival_token(raw_token),
            created_at=current_time,
        )
        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()
                db.add(
                    SmsConversationEvent(
                        conversation_id=conversation.id,
                        type="arrival_invitation_issued",
                        meta={
                            "arrival_session_id": candidate.id,
                            "booking_id": booking.id,
                            "expires_at": arrival_expires_at(
                                candidate, booking
                            ).isoformat(),
                        },
                    )
                )
                db.flush()
            arrival = candidate
            break
        except IntegrityError as exc:
            kind = _arrival_integrity_kind(exc)
            if kind == "booking":
                raise ArrivalStateError(
                    "arrival session already exists for this booking"
                ) from None
            if kind == "token" and attempt + 1 < ARRIVAL_TOKEN_COLLISION_RETRIES:
                continue
            raise ArrivalPersistenceError("arrival session could not be created") from None
    if arrival is None:  # Defensive: the bounded loop either succeeds or raises.
        raise ArrivalPersistenceError("arrival session could not be created")
    expires_at = arrival_expires_at(arrival, booking)
    logger.info("arrival_session_created")
    return ArrivalInvitation(session=arrival, token=raw_token, expires_at=expires_at)


def resolve_arrival_token(
    db: Session,
    token: str,
    *,
    now: Optional[datetime] = None,
) -> ScopedArrival:
    """Resolve a digest-backed token, with temporary legacy raw-row support.

    The raw comparison exists only for rows created before digest storage. It
    must be removed after those rows have expired and the invitation producer
    exclusively uses ``create_arrival_session``.
    """

    raw_token = (token or "").strip()
    digest = hash_arrival_token(raw_token)
    row = (
        _scoped_query(db)
        .filter(SmsArrivalSession.token == digest)
        .with_for_update(of=(SmsArrivalSession, Booking))
        .first()
    )
    legacy_match = False
    if row is None:
        row = (
            _scoped_query(db)
            .filter(SmsArrivalSession.token == raw_token)
            .with_for_update(of=(SmsArrivalSession, Booking))
            .first()
        )
        legacy_match = row is not None
    if row is None:
        # A concurrent resolver may have upgraded the legacy row while this
        # transaction waited for its lock. Recheck only the digest form.
        row = (
            _scoped_query(db)
            .filter(SmsArrivalSession.token == digest)
            .with_for_update(of=(SmsArrivalSession, Booking))
            .first()
        )
    if row is None:
        raise ArrivalNotFoundError("arrival session is unavailable")
    scoped = _to_scoped(row)
    current_time = _as_utc(now or datetime.now(timezone.utc))
    if scoped.session.acknowledged_at is not None:
        raise ArrivalNotFoundError("arrival session is unavailable")
    if arrival_expires_at(scoped.session, scoped.booking) <= current_time:
        raise ArrivalExpiredError("arrival session is unavailable")
    if not arrival_booking_is_eligible(scoped.booking):
        raise ArrivalStateError("booking is not eligible for arrival")
    if legacy_match:
        scoped.session.token = digest
        db.flush()
    return scoped


def mark_customer_arrived(
    db: Session,
    token: str,
    *,
    now: Optional[datetime] = None,
) -> ArrivalMutation:
    """Idempotently mark a valid customer arrival and append one event."""

    current_time = _as_utc(now or datetime.now(timezone.utc))
    scoped = resolve_arrival_token(db, token, now=current_time)
    changed = (
        db.query(SmsArrivalSession)
        .filter(
            SmsArrivalSession.id == scoped.session.id,
            SmsArrivalSession.arrived_at.is_(None),
        )
        .update(
            {SmsArrivalSession.arrived_at: current_time},
            synchronize_session=False,
        )
        == 1
    )
    if changed:
        db.add(
            SmsConversationEvent(
                conversation_id=scoped.conversation.id,
                type="customer_arrived",
                meta={
                    "arrival_session_id": scoped.session.id,
                    "booking_id": scoped.booking.id,
                    "source": "arrival_capability",
                },
            )
        )
        db.flush()
        db.refresh(scoped.session)
        logger.info("customer_arrival_recorded")
    return ArrivalMutation(scoped=scoped, changed=changed)


def _suppress_pending_session_alerts(
    db: Session,
    *,
    scoped: ScopedArrival,
    current_time: datetime,
    error_code: str,
) -> int:
    """Quarantine pending/retry alerts that have not already been leased."""

    prefix = f"arrival-alert:{scoped.session.id}:%"
    suppressed = (
        db.query(OutboxEvent)
        .filter(
            OutboxEvent.tenant_id == scoped.booking.tenant_id,
            OutboxEvent.type == "arrival.alert",
            OutboxEvent.status.in_(_PENDING_OUTBOX_STATUSES),
            OutboxEvent.idempotency_key.like(prefix),
        )
        .update(
            {
                OutboxEvent.status: "QUARANTINED",
                OutboxEvent.processed: True,
                OutboxEvent.processed_at: current_time,
                OutboxEvent.terminal_at: current_time,
                OutboxEvent.error_code: error_code,
                OutboxEvent.next_attempt_at: None,
                OutboxEvent.lease_owner: None,
                OutboxEvent.lease_token: None,
                OutboxEvent.lease_expires_at: None,
            },
            synchronize_session=False,
        )
    )
    if suppressed:
        db.add(
            SmsConversationEvent(
                conversation_id=scoped.conversation.id,
                type="arrival_alerts_suppressed",
                meta={
                    "arrival_session_id": scoped.session.id,
                    "booking_id": scoped.booking.id,
                    "reason": error_code,
                    "suppressed_count": suppressed,
                },
            )
        )
    return suppressed


def acknowledge_arrival(
    db: Session,
    *,
    tenant_id: int,
    arrival_id: int,
    actor_user_id: int,
    now: Optional[datetime] = None,
) -> ArrivalMutation:
    """Idempotently acknowledge/close an arrived tenant-scoped session."""

    actor_exists = (
        db.query(User.id)
        .filter(
            User.id == actor_user_id,
            User.tenant_id == tenant_id,
            User.role.in_(("owner", "admin")),
        )
        .first()
    )
    if actor_exists is None:
        raise ArrivalNotFoundError("arrival session is unavailable")

    row = (
        _scoped_query(db)
        .filter(
            SmsArrivalSession.id == arrival_id,
            Booking.tenant_id == tenant_id,
            SmsConversation.tenant_id == tenant_id,
            SmsAccount.tenant_id == tenant_id,
        )
        .with_for_update(of=(SmsArrivalSession, Booking))
        .first()
    )
    if row is None:
        raise ArrivalNotFoundError("arrival session is unavailable")
    scoped = _to_scoped(row)
    if scoped.session.arrived_at is None:
        raise ArrivalStateError("arrival must be recorded before acknowledgement")
    current_time = _as_utc(now or datetime.now(timezone.utc))
    changed = (
        db.query(SmsArrivalSession)
        .filter(
            SmsArrivalSession.id == scoped.session.id,
            SmsArrivalSession.acknowledged_at.is_(None),
        )
        .update(
            {SmsArrivalSession.acknowledged_at: current_time},
            synchronize_session=False,
        )
        == 1
    )
    suppressed = _suppress_pending_session_alerts(
        db,
        scoped=scoped,
        current_time=current_time,
        error_code="ARRIVAL_ACKNOWLEDGED",
    )
    if changed:
        db.add(
            SmsConversationEvent(
                conversation_id=scoped.conversation.id,
                type="arrival_acknowledged",
                meta={
                    "arrival_session_id": scoped.session.id,
                    "booking_id": scoped.booking.id,
                    "actor_user_id": actor_user_id,
                    "closure": True,
                    "suppressed_alert_count": suppressed,
                },
            )
        )
        db.flush()
        db.refresh(scoped.session)
        logger.info("arrival_acknowledged")
    elif suppressed:
        db.flush()
    return ArrivalMutation(scoped=scoped, changed=changed)


def list_tenant_arrivals(
    db: Session,
    *,
    tenant_id: int,
    limit: int = 50,
) -> list[ScopedArrival]:
    """Return structurally scoped arrival records without capability or PII."""

    rows = (
        _scoped_query(db)
        .filter(
            Booking.tenant_id == tenant_id,
            SmsConversation.tenant_id == tenant_id,
            SmsAccount.tenant_id == tenant_id,
        )
        .order_by(
            SmsArrivalSession.arrived_at.desc().nullslast(),
            SmsArrivalSession.created_at.desc(),
        )
        .limit(max(1, min(limit, 100)))
        .all()
    )
    scoped_rows: list[ScopedArrival] = []
    for row in rows:
        try:
            scoped_rows.append(_to_scoped(row))
        except ArrivalNotFoundError:
            logger.warning("arrival_scope_mismatch_skipped")
    return scoped_rows


def get_active_arrival_sessions(db: Session, tenant_id: int) -> list[SmsArrivalSession]:
    """Return arrived, unacknowledged and unexpired sessions for one tenant."""

    now = datetime.now(timezone.utc)
    return [
        item.session
        for item in list_tenant_arrivals(db, tenant_id=tenant_id, limit=100)
        if item.session.arrived_at is not None
        and item.session.acknowledged_at is None
        and arrival_booking_is_eligible(item.booking)
        and arrival_expires_at(item.session, item.booking) > now
    ]


def _alert_sequence(arrived_at: datetime, now: datetime) -> int:
    elapsed = int((_as_utc(now) - _as_utc(arrived_at)).total_seconds())
    return elapsed // ARRIVAL_ALERT_INTERVAL_SECONDS


def _current_alert_key_expression(db: Session, current_time: datetime):
    """Build the current interval key so deduped rows are excluded pre-LIMIT."""

    if db.get_bind().dialect.name == "sqlite":
        def sqlite_epoch_millis(value):
            whole_seconds = cast(func.strftime("%s", value), Integer) * 1000
            milliseconds = cast(func.substr(func.strftime("%f", value), 4), Integer)
            return whole_seconds + milliseconds

        elapsed_seconds = (
            sqlite_epoch_millis(current_time)
            - sqlite_epoch_millis(SmsArrivalSession.arrived_at)
        ) / 1000
    else:
        elapsed_seconds = func.extract(
            "epoch", literal(current_time) - SmsArrivalSession.arrived_at
        )
    sequence = cast(
        func.floor(elapsed_seconds / ARRIVAL_ALERT_INTERVAL_SECONDS), Integer
    )
    return (
        literal("arrival-alert:")
        + cast(SmsArrivalSession.id, String)
        + literal(":")
        + cast(sequence, String)
    )


def _scope_invalid_key(arrival_id: int) -> str:
    return f"arrival-alert:{arrival_id}:scope-invalid"


def _scope_invalid_key_expression():
    return (
        literal("arrival-alert:")
        + cast(SmsArrivalSession.id, String)
        + literal(":scope-invalid")
    )


def _quarantine_invalid_scope_candidate(
    db: Session,
    *,
    arrival: SmsArrivalSession,
    booking: Booking,
    current_time: datetime,
) -> None:
    """Persist one terminal structural marker for a post-lock scope failure."""

    try:
        with db.begin_nested():
            db.add(
                OutboxEvent(
                    tenant_id=booking.tenant_id,
                    type="arrival.alert",
                    payload=json.dumps(
                        {"arrival_session_id": arrival.id}, sort_keys=True
                    ),
                    status="QUARANTINED",
                    processed=True,
                    processed_at=current_time,
                    terminal_at=current_time,
                    error_code=_ARRIVAL_SCOPE_INVALID,
                    idempotency_key=_scope_invalid_key(arrival.id),
                    created_at=current_time,
                    next_attempt_at=null(),
                )
            )
            db.flush()
    except IntegrityError:
        # Another worker already recorded the same structural quarantine marker.
        return


def _suppress_ineligible_alerts(db: Session, *, current_time: datetime) -> int:
    """Bound cleanup of pending alerts whose session can no longer alert.

    Only PENDING/RETRY rows are eligible. A worker that already leased a row is
    outside this service-level guarantee and must perform its own final guard.
    """

    rows = (
        _scoped_query(db)
        .filter(
            SmsArrivalSession.arrived_at.isnot(None),
            or_(
                SmsArrivalSession.acknowledged_at.isnot(None),
                Booking.status != BookingStatus.CONFIRMED,
                SmsArrivalSession.created_at
                <= current_time - ARRIVAL_TOKEN_MAX_AGE,
                Booking.end_time <= current_time - ARRIVAL_POST_BOOKING_GRACE,
            ),
            exists().where(
                OutboxEvent.tenant_id == Booking.tenant_id,
                OutboxEvent.type == "arrival.alert",
                OutboxEvent.status.in_(_PENDING_OUTBOX_STATUSES),
                OutboxEvent.idempotency_key.like(
                    literal("arrival-alert:")
                    + cast(SmsArrivalSession.id, String)
                    + literal(":%")
                ),
            ),
        )
        .order_by(SmsArrivalSession.id.asc())
        .limit(ARRIVAL_ALERT_BATCH_LIMIT)
        .with_for_update(of=(SmsArrivalSession, Booking), skip_locked=True)
        .all()
    )
    suppressed = 0
    for row in rows:
        try:
            scoped = _to_scoped(row)
        except ArrivalNotFoundError:
            logger.warning("arrival_scope_mismatch_skipped")
            continue

        reason: Optional[str] = None
        if scoped.session.acknowledged_at is not None:
            reason = "ARRIVAL_ACKNOWLEDGED"
        elif not arrival_booking_is_eligible(scoped.booking):
            reason = "ARRIVAL_BOOKING_INELIGIBLE"
        elif arrival_expires_at(scoped.session, scoped.booking) <= current_time:
            reason = "ARRIVAL_EXPIRED"
        if reason is not None:
            suppressed += _suppress_pending_session_alerts(
                db,
                scoped=scoped,
                current_time=current_time,
                error_code=reason,
            )
    return suppressed


def _process_repeated_arrival_alerts(
    db: Session,
    *,
    current_time: datetime,
) -> int:
    _suppress_ineligible_alerts(db, current_time=current_time)
    current_key = _current_alert_key_expression(db, current_time)
    invalid_scope_key = _scope_invalid_key_expression()
    rows = (
        _scoped_query(db)
        .filter(
            SmsArrivalSession.arrived_at.isnot(None),
            SmsArrivalSession.arrived_at
            <= current_time - timedelta(seconds=ARRIVAL_ALERT_INTERVAL_SECONDS),
            SmsArrivalSession.acknowledged_at.is_(None),
            Booking.status == BookingStatus.CONFIRMED,
            SmsArrivalSession.created_at
            > current_time - ARRIVAL_TOKEN_MAX_AGE,
            Booking.end_time > current_time - ARRIVAL_POST_BOOKING_GRACE,
            *_valid_scope_predicates(),
            ~exists()
            .where(OutboxEvent.idempotency_key == current_key)
            .correlate(SmsArrivalSession),
            ~exists()
            .where(OutboxEvent.idempotency_key == invalid_scope_key)
            .correlate(SmsArrivalSession),
        )
        .order_by(
            SmsArrivalSession.arrived_at.desc(),
            SmsArrivalSession.id.asc(),
        )
        .limit(ARRIVAL_ALERT_BATCH_LIMIT)
        .with_for_update(of=(SmsArrivalSession, Booking), skip_locked=True)
        .all()
    )
    created = 0
    for row in rows:
        try:
            scoped = _to_scoped(row)
        except ArrivalNotFoundError:
            _quarantine_invalid_scope_candidate(
                db,
                arrival=row[0],
                booking=row[1],
                current_time=current_time,
            )
            logger.warning("arrival_scope_mismatch_skipped")
            continue
        if not arrival_booking_is_eligible(scoped.booking):
            continue
        if arrival_expires_at(scoped.session, scoped.booking) <= current_time:
            continue
        sequence = _alert_sequence(scoped.session.arrived_at, current_time)
        if sequence < 1:
            continue
        idempotency_key = f"arrival-alert:{scoped.session.id}:{sequence}"
        if (
            db.query(OutboxEvent.id)
            .filter(OutboxEvent.idempotency_key == idempotency_key)
            .first()
            is not None
        ):
            continue
        payload = {
            "arrival_session_id": scoped.session.id,
            "booking_id": scoped.booking.id,
            "conversation_id": scoped.conversation.id,
            "provider_id": scoped.booking.provider_id,
            "sms_account_id": scoped.account.id,
            "alert_sequence": sequence,
        }
        try:
            with db.begin_nested():
                outbox = OutboxEvent(
                    tenant_id=scoped.booking.tenant_id,
                    type="arrival.alert",
                    payload=json.dumps(payload, sort_keys=True),
                    status="PENDING",
                    processed=False,
                    idempotency_key=idempotency_key,
                    created_at=current_time,
                    next_attempt_at=current_time,
                )
                db.add(outbox)
                db.flush()
                db.add(
                    SmsConversationEvent(
                        conversation_id=scoped.conversation.id,
                        type="arrival_alert_triggered",
                        meta={
                            "arrival_session_id": scoped.session.id,
                            "booking_id": scoped.booking.id,
                            "alert_sequence": sequence,
                            "outbox_event_id": outbox.id,
                        },
                    )
                )
                db.flush()
            created += 1
        except IntegrityError:
            # Another worker won the same unique outbox key.
            continue
    if created:
        logger.info("arrival_alerts_enqueued count=%s", created)
    return created


def process_repeated_arrival_alerts(
    db: Session,
    *,
    now: Optional[datetime] = None,
) -> int:
    """Safely enqueue repeated alerts only when the delivery path is enabled.

    The default-disabled path performs no database work. When enabled, this
    function owns and completes a transaction only if the caller does not
    already have one; otherwise it confines its work to a nested savepoint and
    leaves the caller's transaction uncommitted and rollback-capable.
    """

    if not settings.ARRIVAL_ALERT_PRODUCTION_ENABLED:
        return 0

    current_time = _as_utc(now or datetime.now(timezone.utc))
    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        return _process_repeated_arrival_alerts(db, current_time=current_time)
