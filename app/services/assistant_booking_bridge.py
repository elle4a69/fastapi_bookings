"""Booking-domain-only bridge. It deliberately performs no messaging or outbox work."""
from __future__ import annotations

import hashlib
import uuid
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from ..core.state_machine import BookingStatus
from ..models import Client, Location, Provider, Service, Tenant
from ..models.booking import Booking
from ..models.assistant_booking_bridge import (
    AssistantBookingBridgeBinding, AssistantBookingBridgeNonce,
    AssistantBookingBridgeProposal, AssistantBookingBridgeReceipt,
)
from . import scheduling_service, slot_allocation_service

_WINDOW = timedelta(minutes=5)
_PROPOSAL_LIFETIME = timedelta(minutes=10)
_BOOKING_IDEMPOTENCY_PREFIX = "assistant-bridge"
_FINGERPRINT_NOTE_PREFIX = "assistant_bridge_request_sha256:"

def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _error(code: str, http_status: int) -> None:
    raise HTTPException(http_status, {"code": code})


def canonical_request(method: str, path: str, timestamp: str, nonce: str, body: bytes) -> bytes:
    """Stable Ed25519 input. Body is represented only by its SHA-256 digest."""
    return "\n".join((method.upper(), path, timestamp, nonce, hashlib.sha256(body).hexdigest())).encode("utf-8")


def authenticate(db: Session, *, method: str, path: str, body: bytes, key_id: Optional[str], timestamp: Optional[str], nonce: Optional[str], signature: Optional[str]) -> AssistantBookingBridgeBinding:
    """Verify a signed, short-lived, replay-protected server-to-server request."""
    if not all((key_id, timestamp, nonce, signature)) or len(nonce) > 96 or len(signature) > 128:
        _error("BRIDGE_UNAUTHORIZED", status.HTTP_401_UNAUTHORIZED)
    try:
        sent_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        _error("BRIDGE_UNAUTHORIZED", status.HTTP_401_UNAUTHORIZED)
    now = datetime.now(timezone.utc)
    if abs(now - sent_at) > _WINDOW:
        _error("BRIDGE_UNAUTHORIZED", status.HTTP_401_UNAUTHORIZED)
    binding = db.query(AssistantBookingBridgeBinding).filter_by(credential_key_id=key_id).first()
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(binding.public_key, validate=True)) if binding else None
        public_key.verify(base64.b64decode(signature, validate=True), canonical_request(method, path, timestamp, nonce, body))
    except (ValueError, InvalidSignature, TypeError):
        _error("BRIDGE_UNAUTHORIZED", status.HTTP_401_UNAUTHORIZED)
    if not binding.enabled or binding.line_key != "primary":
        _error("BRIDGE_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE)
    db.query(AssistantBookingBridgeNonce).filter(AssistantBookingBridgeNonce.expires_at <= now).delete(synchronize_session=False)
    db.add(AssistantBookingBridgeNonce(binding_id=binding.id, nonce=nonce, expires_at=now + _WINDOW))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _error("BRIDGE_REPLAY", status.HTTP_409_CONFLICT)
    return binding


def _scope(db: Session, binding: AssistantBookingBridgeBinding):
    provider = db.query(Provider).filter(Provider.id == binding.provider_id, Provider.tenant_id == binding.tenant_id, Provider.active.is_(True), Provider.deleted_at.is_(None)).first()
    location = None
    if binding.default_location_id:
        location = db.query(Location).filter(Location.id == binding.default_location_id, Location.tenant_id == binding.tenant_id, Location.active.is_(True)).first()
    if not provider or (binding.default_location_id and not location):
        _error("BRIDGE_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE)
    return provider, location


def business_timezone(db: Session, binding: AssistantBookingBridgeBinding) -> str:
    """Return the configured booking timezone without exposing scope identifiers."""
    _, location = _scope(db, binding)
    tenant = db.query(Tenant).filter(Tenant.id == binding.tenant_id).first()
    timezone_name = (location.timezone if location and location.timezone else getattr(tenant, "timezone", None)) or "UTC"
    try:
        return ZoneInfo(timezone_name).key
    except ZoneInfoNotFoundError:
        _error("BRIDGE_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE)


def proposal_summary(db: Session, binding: AssistantBookingBridgeBinding, proposal: AssistantBookingBridgeProposal) -> dict:
    """Build the customer-safe authoritative summary for a staged proposal."""
    service = _service(db, binding, proposal.service_id)
    provider, location = _scope(db, binding)
    return {
        "service_name": service.name,
        "duration_minutes": service.duration,
        "price": str(service.price) if service.price is not None else None,
        "start_time": _utc(proposal.start_time).isoformat(),
        "end_time": _utc(proposal.end_time).isoformat(),
        "timezone": business_timezone(db, binding),
        "provider_name": provider.name,
        "location_name": location.name if location else None,
    }


def _service(db: Session, binding: AssistantBookingBridgeBinding, service_id: int) -> Service:
    item = db.query(Service).filter(Service.id == service_id, Service.tenant_id == binding.tenant_id, Service.active.is_(True), Service.deleted_at.is_(None)).first()
    if not item:
        _error("SERVICE_UNAVAILABLE", status.HTTP_422_UNPROCESSABLE_ENTITY)
    provider, location = _scope(db, binding)
    if item.providers and provider.id not in {row.provider_id for row in item.providers}:
        _error("SERVICE_UNAVAILABLE", status.HTTP_422_UNPROCESSABLE_ENTITY)
    if location and location.service_ids and item.id not in location.service_ids:
        _error("SERVICE_UNAVAILABLE", status.HTTP_422_UNPROCESSABLE_ENTITY)
    return item


def availability(db: Session, binding: AssistantBookingBridgeBinding, service_id: int, start: datetime, end: datetime) -> list[dict]:
    now = datetime.now(timezone.utc)
    if start.tzinfo is None or end.tzinfo is None:
        _error("INVALID_AVAILABILITY_WINDOW", status.HTTP_422_UNPROCESSABLE_ENTITY)
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if start >= end or start < now or end > now + timedelta(days=31):
        _error("INVALID_AVAILABILITY_WINDOW", status.HTTP_422_UNPROCESSABLE_ENTITY)
    service = _service(db, binding, service_id)
    provider, location = _scope(db, binding)
    return scheduling_service.compute_availability(db, service=service, provider=provider, location=location, start_time=start, end_time=end)


def propose(db: Session, binding: AssistantBookingBridgeBinding, service_id: int, start: datetime) -> AssistantBookingBridgeProposal:
    service = _service(db, binding, service_id)
    if start.tzinfo is None:
        _error("INVALID_AVAILABILITY_WINDOW", status.HTTP_422_UNPROCESSABLE_ENTITY)
    start = start.astimezone(timezone.utc)
    end = start + timedelta(minutes=service.duration)
    slots = availability(db, binding, service_id, start, end)
    if not any(datetime.fromisoformat(str(slot.get("start_time")).replace("Z", "+00:00")).astimezone(timezone.utc) == start for slot in slots):
        _error("SLOT_UNAVAILABLE", status.HTTP_409_CONFLICT)
    proposal = AssistantBookingBridgeProposal(id=str(uuid.uuid4()), binding_id=binding.id, service_id=service.id, start_time=start, end_time=end, expires_at=datetime.now(timezone.utc) + _PROPOSAL_LIFETIME)
    db.add(proposal); db.commit(); db.refresh(proposal)
    return proposal


def _resolve_client(db: Session, binding: AssistantBookingBridgeBinding, name: str, phone: Optional[str], email: Optional[str]) -> Client:
    phone = phone.strip() if phone else None
    email = email.strip().lower() if email else None
    if not phone and not email:
        _error("CUSTOMER_IDENTIFICATION_REQUIRED", status.HTTP_422_UNPROCESSABLE_ENTITY)
    candidates = []
    if phone:
        candidates.extend(db.query(Client).filter(Client.tenant_id == binding.tenant_id, Client.phone == phone, Client.deleted_at.is_(None)).all())
    if email:
        candidates.extend(db.query(Client).filter(Client.tenant_id == binding.tenant_id, Client.email == email, Client.deleted_at.is_(None)).all())
    ids = {item.id for item in candidates}
    if len(ids) > 1:
        _error("CUSTOMER_REVIEW_REQUIRED", status.HTTP_409_CONFLICT)
    if candidates:
        client = candidates[0]
        if client.management_approval_required:
            _error("CUSTOMER_REVIEW_REQUIRED", status.HTTP_409_CONFLICT)
        return client
    client = Client(tenant_id=binding.tenant_id, name=name.strip(), phone=phone, email=email, active=True, management_approval_required=False)
    db.add(client); db.flush(); return client


def _booking_idempotency_key(binding_id: int, request_id: str) -> str:
    return f"{_BOOKING_IDEMPOTENCY_PREFIX}:{binding_id}:{request_id}"


def _request_fingerprint(proposal_id: str, name: str, phone: Optional[str], email: Optional[str]) -> str:
    """Hash canonical command inputs without logging or returning customer data."""
    normalized = {
        "proposal_id": proposal_id,
        "customer_name": name.strip(),
        "customer_phone": phone.strip() if phone else None,
        "customer_email": email.strip().lower() if email else None,
    }
    return hashlib.sha256(
        json.dumps(normalized, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _fingerprint_note(fingerprint: str) -> str:
    return f"{_FINGERPRINT_NOTE_PREFIX}{fingerprint}"


def _existing_idempotent_booking(
    db: Session,
    binding: AssistantBookingBridgeBinding,
    request_id: str,
    fingerprint: str,
) -> Optional[Booking]:
    """Return an equivalent completed command, rejecting altered request reuse."""
    existing = db.query(Booking).filter_by(
        tenant_id=binding.tenant_id,
        idempotency_key=_booking_idempotency_key(binding.id, request_id),
    ).first()
    if not existing:
        return None
    if existing.notes != _fingerprint_note(fingerprint):
        _error("REQUEST_ID_CONFLICT", status.HTTP_409_CONFLICT)
    return existing


def confirm(db: Session, binding: AssistantBookingBridgeBinding, proposal_id: str, request_id: str, name: str, phone: Optional[str], email: Optional[str]) -> Booking:
    fingerprint = _request_fingerprint(proposal_id, name, phone, email)
    existing = _existing_idempotent_booking(db, binding, request_id, fingerprint)
    if existing:
        return existing
    proposal = db.query(AssistantBookingBridgeProposal).filter_by(id=proposal_id, binding_id=binding.id).with_for_update().first()
    # A concurrent command may have committed while this request waited for the
    # proposal lock. The booking's unique idempotency key is the first durable
    # claim, so re-read it before expiry or revalidation checks.
    existing = _existing_idempotent_booking(db, binding, request_id, fingerprint)
    if existing:
        return existing
    now = datetime.now(timezone.utc)
    if not proposal or proposal.confirmed_at or _utc(proposal.expires_at) <= now:
        _error("PROPOSAL_EXPIRED", status.HTTP_409_CONFLICT)
    service = _service(db, binding, proposal.service_id)
    provider, location = _scope(db, binding)
    # A proposal does not reserve; recalculate at the point of confirmation.
    proposal_start = _utc(proposal.start_time)
    proposal_end = _utc(proposal.end_time)
    if not any(datetime.fromisoformat(str(slot.get("start_time")).replace("Z", "+00:00")).astimezone(timezone.utc) == proposal_start for slot in availability(db, binding, service.id, proposal_start, proposal_end)):
        _error("SLOT_UNAVAILABLE", status.HTTP_409_CONFLICT)
    client = _resolve_client(db, binding, name, phone, email)
    from ..models import Resource, ServiceResourceRequirement, AuditLog
    # Lock all applicable exclusive-capacity resources in stable order before recheck/allocation.
    db.query(Resource).join(ServiceResourceRequirement, ServiceResourceRequirement.resource_type == Resource.type).filter(ServiceResourceRequirement.service_id == service.id, Resource.tenant_id == binding.tenant_id, Resource.active.is_(True)).order_by(Resource.id).with_for_update().all()
    booking = Booking(
        tenant_id=binding.tenant_id,
        client_id=client.id,
        provider_id=provider.id,
        service_id=service.id,
        location_id=location.id if location else None,
        start_time=proposal_start,
        end_time=proposal_end,
        status=BookingStatus.PENDING,
        idempotency_key=_booking_idempotency_key(binding.id, request_id),
        notes=_fingerprint_note(fingerprint),
    )
    try:
        with db.begin_nested():
            # Flush the unique booking key before allocation work. This is the
            # durable command claim; the receipt commits atomically with it.
            db.add(booking)
            db.flush()
            db.add(AssistantBookingBridgeReceipt(binding_id=binding.id, request_id=request_id, booking_id=booking.id))
            db.flush()
            slot_allocation_service.create_allocations_for_booking(db, booking=booking, buffer_before=max(15, service.buffer_before or 0), buffer_after=max(15, service.buffer_after or 0))
            scheduling_service.allocate_resources(db, booking=booking, commit=False)
            proposal.confirmed_at = now
            db.add(AuditLog(tenant_id=binding.tenant_id, action="assistant_bridge.booking_created", target_type="booking", target_id=booking.id, details="bridge_line=primary;status=pending"))
        db.commit()
    except IntegrityError:
        db.rollback()
        retry = _existing_idempotent_booking(db, binding, request_id, fingerprint)
        if retry:
            return retry
        _error("SLOT_UNAVAILABLE", status.HTTP_409_CONFLICT)
    db.refresh(booking); return booking
