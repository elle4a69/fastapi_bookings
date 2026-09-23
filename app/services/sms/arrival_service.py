"""Secure booking-linked arrival sessions and deduplicated staff alerts."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models.booking import Booking
from ...models.client import Client
from ...models.outbox import OutboxEvent
from ...models.provider import Provider
from ...models.service import Service
from ...models.sms_account import SmsAccount
from ...models.sms_arrival import SmsArrivalSession
from ...models.sms_conversation import SmsConversation
from ...models.sms_outbox import SmsConversationEvent

logger = logging.getLogger(__name__)

ARRIVAL_TOKEN_MAX_AGE = timedelta(days=7)
ARRIVAL_POST_BOOKING_GRACE = timedelta(hours=4)
ARRIVAL_ALERT_INTERVAL_SECONDS = 60


class ArrivalNotFoundError(LookupError):
    """No session is available within the requested security scope."""


class ArrivalExpiredError(LookupError):
    """The arrival capability is no longer valid."""


class ArrivalStateError(ValueError):
    """The lifecycle transition is not permitted."""


@dataclass(frozen=True)
class ArrivalInvitation:
    """One-time return value for an invitation producer.

    ``token`` is never persisted or logged. The eventual reminder/link producer
    must commit the session and invitation atomically before exposing the token.
    """

    session: SmsArrivalSession
    token: str
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


def _validate_scope(
    *,
    tenant_id: int,
    booking: Booking,
    conversation: SmsConversation,
    account: SmsAccount,
    client_tenant_id: int,
    provider_tenant_id: int,
    service_tenant_id: int,
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
        )
        .join(Booking, Booking.id == SmsArrivalSession.booking_id)
        .join(SmsConversation, SmsConversation.id == SmsArrivalSession.conversation_id)
        .join(SmsAccount, SmsAccount.id == SmsConversation.sms_account_id)
        .join(Client, Client.id == Booking.client_id)
        .join(Provider, Provider.id == Booking.provider_id)
        .join(Service, Service.id == Booking.service_id)
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
    ) = row
    _validate_scope(
        tenant_id=booking.tenant_id,
        booking=booking,
        conversation=conversation,
        account=account,
        client_tenant_id=client_tenant_id,
        provider_tenant_id=provider_tenant_id,
        service_tenant_id=service_tenant_id,
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
    if client_scope is None or provider_scope is None or service_scope is None:
        raise ArrivalNotFoundError("arrival session is unavailable")
    _validate_scope(
        tenant_id=tenant_id,
        booking=booking,
        conversation=conversation,
        account=account,
        client_tenant_id=tenant_id,
        provider_tenant_id=tenant_id,
        service_tenant_id=tenant_id,
    )
    if _booking_status(booking) != "confirmed":
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

    raw_token = secrets.token_urlsafe(32)
    arrival = SmsArrivalSession(
        conversation_id=conversation_id,
        booking_id=booking_id,
        token=hash_arrival_token(raw_token),
        created_at=current_time,
    )
    db.add(arrival)
    db.flush()
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
        .filter(or_(SmsArrivalSession.token == digest, SmsArrivalSession.token == raw_token))
        .first()
    )
    if row is None:
        raise ArrivalNotFoundError("arrival session is unavailable")
    scoped = _to_scoped(row)
    current_time = _as_utc(now or datetime.now(timezone.utc))
    if arrival_expires_at(scoped.session, scoped.booking) <= current_time:
        raise ArrivalExpiredError("arrival session is unavailable")
    if _booking_status(scoped.booking) != "confirmed":
        raise ArrivalStateError("booking is not eligible for arrival")
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
    changed = scoped.session.arrived_at is None
    if changed:
        scoped.session.arrived_at = current_time
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
        logger.info("customer_arrival_recorded")
    return ArrivalMutation(scoped=scoped, changed=changed)


def acknowledge_arrival(
    db: Session,
    *,
    tenant_id: int,
    arrival_id: int,
    actor_user_id: int,
    now: Optional[datetime] = None,
) -> ArrivalMutation:
    """Idempotently acknowledge/close an arrived tenant-scoped session."""

    row = (
        _scoped_query(db)
        .filter(
            SmsArrivalSession.id == arrival_id,
            Booking.tenant_id == tenant_id,
            SmsConversation.tenant_id == tenant_id,
            SmsAccount.tenant_id == tenant_id,
        )
        .first()
    )
    if row is None:
        raise ArrivalNotFoundError("arrival session is unavailable")
    scoped = _to_scoped(row)
    if scoped.session.arrived_at is None:
        raise ArrivalStateError("arrival must be recorded before acknowledgement")
    changed = scoped.session.acknowledged_at is None
    if changed:
        scoped.session.acknowledged_at = _as_utc(now or datetime.now(timezone.utc))
        db.add(
            SmsConversationEvent(
                conversation_id=scoped.conversation.id,
                type="arrival_acknowledged",
                meta={
                    "arrival_session_id": scoped.session.id,
                    "booking_id": scoped.booking.id,
                    "actor_user_id": actor_user_id,
                    "closure": True,
                },
            )
        )
        db.flush()
        logger.info("arrival_acknowledged")
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
        and arrival_expires_at(item.session, item.booking) > now
    ]


def _alert_sequence(arrived_at: datetime, now: datetime) -> int:
    elapsed = int((_as_utc(now) - _as_utc(arrived_at)).total_seconds())
    return elapsed // ARRIVAL_ALERT_INTERVAL_SECONDS


def process_repeated_arrival_alerts(
    db: Session,
    *,
    now: Optional[datetime] = None,
) -> int:
    """Enqueue one durable structural alert per elapsed interval.

    The outbox unique idempotency key is the concurrency backstop. No bearer
    token, customer identity, phone number or message content enters the event.
    """

    current_time = _as_utc(now or datetime.now(timezone.utc))
    rows = (
        _scoped_query(db)
        .filter(
            SmsArrivalSession.arrived_at.isnot(None),
            SmsArrivalSession.acknowledged_at.is_(None),
        )
        .all()
    )
    created = 0
    for row in rows:
        try:
            scoped = _to_scoped(row)
        except ArrivalNotFoundError:
            logger.warning("arrival_scope_mismatch_skipped")
            continue
        if _booking_status(scoped.booking) != "confirmed":
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
        db.commit()
        logger.info("arrival_alerts_enqueued count=%s", created)
    return created
