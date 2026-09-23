"""Authoritative, tenant-scoped booking creation command.

This module owns the final revalidation and atomic persistence boundary shared
by booking entry points.  It deliberately performs no external network work.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session

from ..core.state_machine import BookingStatus
from ..models import (
    BookingResourceAllocation,
    BookingSlotAllocation,
    Client,
    Location,
    Provider,
    Resource,
    Service,
)
from ..models.audit import AuditLog
from ..models.booking import Booking
from ..models.location import LocationProvider, LocationService
from ..schemas.booking import BookingCreate
from . import scheduling_service, slot_allocation_service
from .booking_relationship_resolver import pair_allowed
from .outbox_service import create_outbox_event


logger = logging.getLogger(__name__)
REQUEST_FINGERPRINT_VERSION = 1


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


def _normalized_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalized_email(value: str | None) -> str | None:
    normalized = _normalized_text(value)
    return normalized.lower() if normalized else None


def _fingerprint_phone(value: str | None) -> str | None:
    """Canonicalize valid phones and deterministically hash invalid replay input."""

    try:
        return _canonical_phone(value)
    except BookingCommandError:
        normalized = _normalized_text(value)
        return f"invalid:{normalized}" if normalized else None


def _request_fingerprint(*, tenant_id: int, command: BookingCreate) -> str:
    """Hash a canonical command without retaining its customer-supplied values."""

    canonical = {
        "version": REQUEST_FINGERPRINT_VERSION,
        "tenant_id": tenant_id,
        "idempotency_key": command.idempotency_key,
        "client_id": command.client_id,
        "client_name": _normalized_text(command.client_name),
        "client_email": _normalized_email(command.client_email),
        "client_phone": _fingerprint_phone(command.client_phone),
        "provider_id": command.provider_id,
        "service_id": command.service_id,
        "location_id": command.location_id,
        "start_time": _utc(command.start_time).isoformat(),
        "end_time": _utc(command.end_time).isoformat(),
        "notes": _normalized_text(command.notes),
    }
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stored_request_fingerprint(
    db: Session,
    *,
    tenant_id: int,
    booking_id: int,
) -> str | None:
    """Return the one valid public-booking fingerprint for this booking."""

    records = (
        db.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == "booking.created",
            AuditLog.target_type == "booking",
            AuditLog.target_id == booking_id,
        )
        .order_by(AuditLog.id)
        .all()
    )
    public_records: list[dict] = []
    for record in records:
        try:
            details = json.loads(record.details or "")
        except (TypeError, ValueError):
            continue
        if isinstance(details, dict) and details.get("source") == "public_booking":
            public_records.append(details)
    if len(public_records) != 1:
        return None
    details = public_records[0]
    fingerprint = details.get("request_fingerprint")
    if details.get("request_fingerprint_version") != REQUEST_FINGERPRINT_VERSION:
        return None
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        return None
    return fingerprint


def _assert_replay_matches(
    db: Session,
    *,
    existing: Booking,
    tenant_id: int,
    command: BookingCreate,
) -> None:
    """Reject reuse of a key for a different canonical command."""

    stored = _stored_request_fingerprint(
        db,
        tenant_id=tenant_id,
        booking_id=existing.id,
    )
    requested = _request_fingerprint(tenant_id=tenant_id, command=command)
    if stored is None or not secrets.compare_digest(stored, requested):
        raise BookingCommandError(
            409,
            "Idempotency key was already used for a different booking request.",
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
    canonical_phone = _canonical_phone(command.client_phone)
    normalized_email = _normalized_email(command.client_email)
    id_match: Client | None = None
    if command.client_id is not None:
        id_match = (
            db.query(Client)
            .filter(
                Client.id == command.client_id,
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
            .first()
        )
        if not id_match:
            raise BookingCommandError(404, "Client not found")

    phone_matches: list[Client] = []
    email_matches: list[Client] = []
    if canonical_phone:
        candidates = (
            db.query(Client)
            .filter(
                Client.tenant_id == tenant_id,
                Client.phone.isnot(None),
                Client.deleted_at.is_(None),
            )
            .order_by(Client.id)
            .all()
        )
        phone_matches = [
            candidate
            for candidate in candidates
            if _stored_canonical_phone(candidate.phone) == canonical_phone
        ]
    if normalized_email:
        email_matches = (
            db.query(Client)
            .filter(
                Client.tenant_id == tenant_id,
                func.lower(Client.email) == normalized_email,
                Client.deleted_at.is_(None),
            )
            .order_by(Client.id)
            .all()
        )

    if len(phone_matches) > 1 or len(email_matches) > 1:
        raise BookingCommandError(409, "Client contact details are ambiguous.")
    matched_clients = {
        match.id: match
        for match in ([id_match] if id_match else []) + phone_matches + email_matches
    }
    if len(matched_clients) > 1:
        raise BookingCommandError(409, "Client contact details conflict.")
    client = next(iter(matched_clients.values()), None)
    if client is not None:
        if canonical_phone and _stored_canonical_phone(client.phone) != canonical_phone:
            raise BookingCommandError(409, "Client contact details conflict.")
        if normalized_email and _normalized_email(client.email) != normalized_email:
            raise BookingCommandError(409, "Client contact details conflict.")
    else:
        if not (command.client_name or normalized_email or canonical_phone):
            raise BookingCommandError(
                400,
                "Client identification (client_id or client_name/email/phone) is required.",
            )
        fallback_name = (
            normalized_email.split("@", 1)[0] if normalized_email else "Guest Client"
        )
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

    if not client.active:
        raise BookingCommandError(403, "Client is not active.")
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
    else:
        provider_location_ids = {
            row[0]
            for row in db.query(LocationProvider.location_id)
            .filter(
                LocationProvider.tenant_id == tenant_id,
                LocationProvider.provider_id == provider.id,
            )
            .all()
        }
        service_location_ids = {
            row[0]
            for row in db.query(LocationService.location_id)
            .filter(
                LocationService.tenant_id == tenant_id,
                LocationService.service_id == service.id,
            )
            .all()
        }
        restricted_location_ids: set[int] | None = None
        if provider_location_ids and service_location_ids:
            restricted_location_ids = provider_location_ids & service_location_ids
        elif provider_location_ids:
            restricted_location_ids = provider_location_ids
        elif service_location_ids:
            restricted_location_ids = service_location_ids

        if restricted_location_ids is not None:
            locations = (
                db.query(Location)
                .filter(
                    Location.tenant_id == tenant_id,
                    Location.id.in_(restricted_location_ids),
                    Location.active.is_(True),
                )
                .order_by(Location.id)
                .all()
            )
            if not locations:
                raise BookingCommandError(
                    400,
                    "No active location is compatible with this service and provider.",
                )
            if len(locations) != 1:
                raise BookingCommandError(
                    400,
                    "A location is required for this service and provider.",
                )
            location = locations[0]

    return service, provider, location


def _effective_buffer(value: int | None) -> int:
    return max(15, value or 0)


def _resource_candidates_query(
    db: Session,
    *,
    tenant_id: int,
    resource_type: str,
    location_id: int | None,
) -> Query:
    """Build the deterministic candidate-row lock used by final allocation."""

    query = db.query(Resource).filter(
        Resource.tenant_id == tenant_id,
        Resource.type == resource_type,
        Resource.active.is_(True),
    )
    if location_id is None:
        query = query.filter(Resource.location_id.is_(None))
    else:
        query = query.filter(
            (Resource.location_id.is_(None)) | (Resource.location_id == location_id)
        )
    return query.order_by(Resource.id).with_for_update()


def _allocate_locked_resources(
    db: Session,
    *,
    booking: Booking,
    service: Service,
    location: Location | None,
) -> None:
    """Lock scoped resource rows, recompute capacity, and allocate deterministically."""

    requirements = sorted(
        service.resource_requirements,
        key=lambda requirement: (requirement.resource_type, requirement.id),
    )
    for requirement in requirements:
        candidates = _resource_candidates_query(
            db,
            tenant_id=booking.tenant_id,
            resource_type=requirement.resource_type,
            location_id=location.id if location else None,
        ).all()
        remaining = requirement.quantity or 1
        selected: list[tuple[Resource, int]] = []
        for resource in candidates:
            used = (
                db.query(func.coalesce(func.sum(BookingResourceAllocation.quantity), 0))
                .join(
                    Booking,
                    Booking.id == BookingResourceAllocation.booking_id,
                )
                .filter(
                    BookingResourceAllocation.resource_id == resource.id,
                    Booking.tenant_id == booking.tenant_id,
                    Booking.status != BookingStatus.CANCELLED,
                    Booking.start_time < booking.end_time,
                    Booking.end_time > booking.start_time,
                )
                .scalar()
            )
            free_capacity = resource.capacity - int(used or 0)
            take = min(max(free_capacity, 0), remaining)
            if take:
                selected.append((resource, take))
                remaining -= take
            if remaining == 0:
                break
        if remaining:
            raise BookingCommandError(
                409,
                "No available resources for this service at the requested time.",
            )
        for resource, quantity in selected:
            db.add(
                BookingResourceAllocation(
                    booking_id=booking.id,
                    resource_id=resource.id,
                    quantity=quantity,
                )
            )
        db.flush()


def _revalidate_exact_slot(
    db: Session,
    *,
    service: Service,
    provider: Provider,
    location: Location | None,
    start_time: datetime,
    end_time: datetime,
    buffer_before: int,
    buffer_after: int,
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

    padded_start = start_time - timedelta(minutes=buffer_before)
    padded_end = end_time + timedelta(minutes=buffer_after)
    active_overlap = (
        db.query(Booking.id)
        .filter(
            Booking.tenant_id == service.tenant_id,
            Booking.provider_id == provider.id,
            Booking.status != BookingStatus.CANCELLED,
            Booking.start_time < padded_end,
            Booking.end_time > padded_start,
        )
        .first()
    )
    slot_times = slot_allocation_service.generate_slot_timestamps(
        start_time,
        end_time,
        buffer_before,
        buffer_after,
    )
    allocated_overlap = (
        db.query(BookingSlotAllocation.id)
        .join(Booking, Booking.id == BookingSlotAllocation.booking_id)
        .filter(
            Booking.tenant_id == service.tenant_id,
            Booking.status != BookingStatus.CANCELLED,
            BookingSlotAllocation.provider_id == provider.id,
            BookingSlotAllocation.slot_start.in_(slot_times),
        )
        .first()
    )
    if active_overlap or allocated_overlap:
        raise BookingCommandError(
            409,
            "The requested time slot or buffer is no longer available.",
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
            _assert_replay_matches(
                db,
                existing=existing,
                tenant_id=tenant_id,
                command=command,
            )
            return existing

        _reject_cross_tenant_key_collision(
            db,
            tenant_id=tenant_id,
            idempotency_key=command.idempotency_key,
        )
        with db.begin_nested():
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
                raise BookingCommandError(
                    400,
                    "Bookings must be made at least 30 minutes in advance.",
                )

            client = _resolve_client(db, tenant_id=tenant_id, command=command)
            buffer_before = _effective_buffer(service.buffer_before)
            buffer_after = _effective_buffer(service.buffer_after)
            _revalidate_exact_slot(
                db,
                service=service,
                provider=provider,
                location=location,
                start_time=start_time,
                end_time=end_time,
                buffer_before=buffer_before,
                buffer_after=buffer_after,
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

            slot_allocation_service.create_allocations_for_booking(
                db,
                booking=booking,
                buffer_before=buffer_before,
                buffer_after=buffer_after,
            )
            _allocate_locked_resources(
                db,
                booking=booking,
                service=service,
                location=location,
            )

            payload = {
                "id": booking.id,
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
                    details=json.dumps(
                        {
                            "status": booking.status.value,
                            "source": "public_booking",
                            "request_fingerprint_version": REQUEST_FINGERPRINT_VERSION,
                            "request_fingerprint": _request_fingerprint(
                                tenant_id=tenant_id,
                                command=command,
                            ),
                        }
                    ),
                )
            )
            db.flush()
        return booking
    except BookingCommandError:
        raise
    except HTTPException as exc:
        raise BookingCommandError(exc.status_code, str(exc.detail)) from exc
    except IntegrityError as exc:
        try:
            existing = _existing_idempotent_booking(
                db,
                tenant_id=tenant_id,
                idempotency_key=command.idempotency_key,
            )
            if existing:
                _assert_replay_matches(
                    db,
                    existing=existing,
                    tenant_id=tenant_id,
                    command=command,
                )
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
                    raise BookingCommandError(
                        409,
                        "Idempotency key is already in use.",
                    ) from exc
        except BookingCommandError:
            raise
        except Exception as recovery_error:
            logger.error(
                "booking_creation_integrity_recovery_failed tenant_id=%s error_type=%s",
                tenant_id,
                type(recovery_error).__name__,
            )
            raise BookingCommandError(500, "Unable to create booking.") from None
        logger.error("booking_creation_integrity_error tenant_id=%s", tenant_id)
        raise BookingCommandError(500, "Unable to create booking.") from None
    except Exception as exc:
        logger.error(
            "booking_creation_failed tenant_id=%s error_type=%s",
            tenant_id,
            type(exc).__name__,
        )
        raise BookingCommandError(500, "Unable to create booking.") from None
