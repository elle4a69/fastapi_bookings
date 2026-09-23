"""Authoritative, tenant-scoped booking creation command.

This module owns the final revalidation and atomic persistence boundary shared
by booking entry points.  It deliberately performs no external network work.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.state_machine import BookingStatus
from ..models import Client, Location, Provider, Service
from ..models.audit import AuditLog
from ..models.booking import Booking
from ..schemas.booking import BookingCreate
from . import scheduling_service, slot_allocation_service
from .booking_relationship_resolver import pair_allowed
from .outbox_service import create_outbox_event


logger = logging.getLogger(__name__)


class BookingCommandError(Exception):
    """Safe application error mapped to the existing public HTTP contract."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical_phone(value: str | None) -> str | None:
    """Normalize a supplied phone number to an E.164-style digit string."""

    if value is None or not value.strip():
        return None
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("6104") and len(digits) == 12:
        digits = "614" + digits[4:]
    elif digits.startswith("04") and len(digits) == 10:
        digits = "61" + digits[1:]
    elif digits.startswith("4") and len(digits) == 9:
        digits = "61" + digits
    if not re.fullmatch(r"[1-9]\d{7,14}", digits):
        raise BookingCommandError(400, "Client phone number is invalid.")
    return digits


def _stored_canonical_phone(value: str | None) -> str | None:
    """Best-effort normalization for legacy client rows with malformed data."""

    try:
        return _canonical_phone(value)
    except BookingCommandError:
        return None


def _existing_idempotent_booking(
    db: Session,
    *,
    tenant_id: int,
    idempotency_key: str | None,
) -> Booking | None:
    if not idempotency_key:
        return None
    return (
        db.query(Booking)
        .filter(
            Booking.tenant_id == tenant_id,
            Booking.idempotency_key == idempotency_key,
        )
        .first()
    )


def _reject_cross_tenant_key_collision(
    db: Session,
    *,
    tenant_id: int,
    idempotency_key: str | None,
) -> None:
    """Fail before mutation while the database key remains globally unique."""

    if not idempotency_key:
        return
    collision = (
        db.query(Booking.id)
        .filter(
            Booking.tenant_id != tenant_id,
            Booking.idempotency_key == idempotency_key,
        )
        .first()
    )
    if collision:
        raise BookingCommandError(409, "Idempotency key is already in use.")


def _resolve_client(
    db: Session,
    *,
    tenant_id: int,
    command: BookingCreate,
) -> Client:
    if command.client_id is not None:
        client = (
            db.query(Client)
            .filter(
                Client.id == command.client_id,
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
            .first()
        )
        if not client:
            raise BookingCommandError(404, "Client not found")
    else:
        canonical_phone = _canonical_phone(command.client_phone)
        normalized_email = command.client_email.strip().lower() if command.client_email else None
        client = None

        if canonical_phone:
            candidates = (
                db.query(Client)
                .filter(
                    Client.tenant_id == tenant_id,
                    Client.phone.isnot(None),
                    Client.deleted_at.is_(None),
                )
                .all()
            )
            client = next(
                (
                    candidate
                    for candidate in candidates
                    if _stored_canonical_phone(candidate.phone) == canonical_phone
                ),
                None,
            )
        if client is None and normalized_email:
            client = (
                db.query(Client)
                .filter(
                    Client.tenant_id == tenant_id,
                    Client.email == normalized_email,
                    Client.deleted_at.is_(None),
                )
                .first()
            )

        if client is None:
            if not (command.client_name or normalized_email or canonical_phone):
                raise BookingCommandError(
                    400,
                    "Client identification (client_id or client_name/email/phone) is required.",
                )
            fallback_name = normalized_email.split("@", 1)[0] if normalized_email else "Guest Client"
            client = Client(
                tenant_id=tenant_id,
                name=(command.client_name or "").strip() or fallback_name,
                email=normalized_email,
                phone=canonical_phone,
                active=True,
                management_approval_required=False,
            )
            db.add(client)
            db.flush()

    if client.management_approval_required:
        raise BookingCommandError(
            403,
            "Client requires management approval before booking.",
        )
    return client


def _resolve_booking_entities(
    db: Session,
    *,
    tenant_id: int,
    command: BookingCreate,
) -> tuple[Service, Provider, Location | None]:
    service = (
        db.query(Service)
        .filter(
            Service.id == command.service_id,
            Service.tenant_id == tenant_id,
            Service.deleted_at.is_(None),
        )
        .first()
    )
    if not service:
        raise BookingCommandError(404, "Service not found")
    if not service.active:
        raise BookingCommandError(400, "Service is not active")

    provider = (
        db.query(Provider)
        .filter(
            Provider.id == command.provider_id,
            Provider.tenant_id == tenant_id,
            Provider.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not provider:
        raise BookingCommandError(404, "Provider not found")
    if not provider.active:
        raise BookingCommandError(400, "Provider is not active")
    if not pair_allowed(db, tenant_id, "service", service.id, "provider", provider.id):
        raise BookingCommandError(400, "Provider is not eligible for this service")

    location = None
    if command.location_id is not None:
        location = (
            db.query(Location)
            .filter(
                Location.id == command.location_id,
                Location.tenant_id == tenant_id,
                Location.active.is_(True),
            )
            .first()
        )
        if not location:
            raise BookingCommandError(404, "Location not found")
        if not pair_allowed(db, tenant_id, "location", location.id, "provider", provider.id):
            raise BookingCommandError(400, "Provider is not eligible for this location")
        if not pair_allowed(db, tenant_id, "location", location.id, "service", service.id):
            raise BookingCommandError(400, "Service is not available at this location")

    return service, provider, location


def _revalidate_exact_slot(
    db: Session,
    *,
    service: Service,
    provider: Provider,
    location: Location | None,
    start_time: datetime,
    end_time: datetime,
) -> None:
    search_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    search_end = max(search_start + timedelta(days=1), end_time)
    slots = scheduling_service.compute_availability(
        db,
        service=service,
        provider=provider,
        location=location,
        start_time=search_start,
        end_time=search_end,
    )
    exact_match = any(
        _utc(datetime.fromisoformat(slot["start_time"])) == start_time
        and _utc(datetime.fromisoformat(slot["end_time"])) == end_time
        and slot.get("provider", {}).get("id") == provider.id
        for slot in slots
    )
    if not exact_match:
        raise BookingCommandError(
            409,
            "The requested time slot is no longer available. Please choose another time.",
        )


def create_authoritative_booking(
    db: Session,
    *,
    tenant_id: int,
    command: BookingCreate,
) -> Booking:
    """Validate and atomically create one pending FastAPI Bookings booking."""

    try:
        existing = _existing_idempotent_booking(
            db,
            tenant_id=tenant_id,
            idempotency_key=command.idempotency_key,
        )
        if existing:
            return existing
        _reject_cross_tenant_key_collision(
            db,
            tenant_id=tenant_id,
            idempotency_key=command.idempotency_key,
        )

        service, provider, location = _resolve_booking_entities(
            db,
            tenant_id=tenant_id,
            command=command,
        )

        start_time = _utc(command.start_time)
        supplied_end = _utc(command.end_time)
        end_time = start_time + timedelta(minutes=service.duration)
        if start_time >= supplied_end:
            raise BookingCommandError(400, "Booking start time must be before end time.")
        if supplied_end != end_time:
            raise BookingCommandError(
                400,
                "Booking end time must match the authoritative service duration.",
            )
        if start_time < datetime.now(timezone.utc) + timedelta(minutes=30):
            raise BookingCommandError(400, "Bookings must be made at least 30 minutes in advance.")

        # Resolve ownership/restriction errors before reporting slot state. Any
        # newly constructed client remains inside this transaction and is
        # rolled back if subsequent availability validation fails.
        client = _resolve_client(db, tenant_id=tenant_id, command=command)
        _revalidate_exact_slot(
            db,
            service=service,
            provider=provider,
            location=location,
            start_time=start_time,
            end_time=end_time,
        )

        booking = Booking(
            tenant_id=tenant_id,
            client_id=client.id,
            provider_id=provider.id,
            service_id=service.id,
            location_id=location.id if location else None,
            start_time=start_time,
            end_time=end_time,
            notes=command.notes,
            idempotency_key=command.idempotency_key,
            status=BookingStatus.PENDING,
        )
        db.add(booking)
        db.flush()

        buffer_before = max(15, service.buffer_before or 0)
        buffer_after = max(15, service.buffer_after or 0)
        slot_allocation_service.create_allocations_for_booking(
            db,
            booking=booking,
            buffer_before=buffer_before,
            buffer_after=buffer_after,
        )
        scheduling_service.allocate_resources(db, booking=booking, commit=False)

        payload = {
            "id": booking.id,
            "client_id": booking.client_id,
            "provider_id": booking.provider_id,
            "service_id": booking.service_id,
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
            "status": booking.status.value,
        }
        create_outbox_event(db, "booking.created", payload, tenant_id=tenant_id)
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                action="booking.created",
                target_type="booking",
                target_id=booking.id,
                details=json.dumps({"status": booking.status.value, "source": "public_booking"}),
            )
        )
        db.commit()
        db.refresh(booking)
        return booking
    except BookingCommandError:
        db.rollback()
        raise
    except HTTPException as exc:
        db.rollback()
        raise BookingCommandError(exc.status_code, str(exc.detail)) from exc
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_idempotent_booking(
            db,
            tenant_id=tenant_id,
            idempotency_key=command.idempotency_key,
        )
        if existing:
            return existing
        if slot_allocation_service.is_slot_allocation_conflict(exc):
            raise BookingCommandError(
                409,
                "The requested time slot or buffer has just been booked. Please select another available time.",
            ) from exc
        if command.idempotency_key:
            collision = (
                db.query(Booking.id)
                .filter(Booking.idempotency_key == command.idempotency_key)
                .first()
            )
            if collision:
                raise BookingCommandError(409, "Idempotency key is already in use.") from exc
        logger.error("booking_creation_integrity_error tenant_id=%s", tenant_id)
        raise
    except Exception:
        db.rollback()
        logger.error("booking_creation_failed tenant_id=%s", tenant_id)
        raise
