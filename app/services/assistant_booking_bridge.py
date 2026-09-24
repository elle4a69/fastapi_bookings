"""Booking-domain-only bridge. It deliberately performs no messaging or outbox work."""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.state_machine import BookingStatus
from ..models import Client, Location, Provider, Service
from ..models.booking import Booking
from ..models.assistant_booking_bridge import (
    AssistantBookingBridgeBinding, AssistantBookingBridgeNonce,
    AssistantBookingBridgeProposal, AssistantBookingBridgeReceipt,
)
from . import scheduling_service, slot_allocation_service

_WINDOW = timedelta(minutes=5)
_PROPOSAL_LIFETIME = timedelta(minutes=10)


def _error(code: str, http_status: int) -> None:
    raise HTTPException(http_status, {"code": code})


def canonical_request(method: str, path: str, timestamp: str, nonce: str, body: bytes) -> bytes:
    """Stable HMAC input. Body is represented only by its SHA-256 digest."""
    return "\n".join((method.upper(), path, timestamp, nonce, hashlib.sha256(body).hexdigest())).encode("utf-8")


def authenticate(db: Session, *, method: str, path: str, body: bytes, key_id: Optional[str], timestamp: Optional[str], nonce: Optional[str], signature: Optional[str]) -> AssistantBookingBridgeBinding:
    """Verify a signed, short-lived, replay-protected server-to-server request."""
    if not all((key_id, timestamp, nonce, signature)) or len(nonce) > 96 or len(signature) != 64:
        _error("BRIDGE_UNAUTHORIZED", status.HTTP_401_UNAUTHORIZED)
    try:
        sent_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        _error("BRIDGE_UNAUTHORIZED", status.HTTP_401_UNAUTHORIZED)
    now = datetime.now(timezone.utc)
    if abs(now - sent_at) > _WINDOW:
        _error("BRIDGE_UNAUTHORIZED", status.HTTP_401_UNAUTHORIZED)
    binding = db.query(AssistantBookingBridgeBinding).filter_by(credential_key_id=key_id).first()
    # The client derives this HMAC key as SHA256(raw provisioned secret). The server
    # retains only that verifier, never the raw secret or a bearer header.
    expected = hmac.new((binding.secret_verifier if binding else "").encode("ascii"), canonical_request(method, path, timestamp, nonce, body), hashlib.sha256).hexdigest()
    if not binding or not hmac.compare_digest(expected, signature):
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
    start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start.astimezone(timezone.utc)
    end = end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end.astimezone(timezone.utc)
    if start >= end or start < now or end > now + timedelta(days=31):
        _error("INVALID_AVAILABILITY_WINDOW", status.HTTP_422_UNPROCESSABLE_ENTITY)
    service = _service(db, binding, service_id)
    provider, location = _scope(db, binding)
    return scheduling_service.compute_availability(db, service=service, provider=provider, location=location, start_time=start, end_time=end)


def propose(db: Session, binding: AssistantBookingBridgeBinding, service_id: int, start: datetime) -> AssistantBookingBridgeProposal:
    service = _service(db, binding, service_id)
    start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start.astimezone(timezone.utc)
    end = start + timedelta(minutes=service.duration)
    slots = availability(db, binding, service_id, start, end)
    if not any(slot.get("start_time") == start for slot in slots):
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


def confirm(db: Session, binding: AssistantBookingBridgeBinding, proposal_id: str, request_id: str, name: str, phone: Optional[str], email: Optional[str]) -> Booking:
    existing = db.query(AssistantBookingBridgeReceipt).filter_by(binding_id=binding.id, request_id=request_id).first()
    if existing:
        return db.query(Booking).filter_by(id=existing.booking_id, tenant_id=binding.tenant_id).first()
    proposal = db.query(AssistantBookingBridgeProposal).filter_by(id=proposal_id, binding_id=binding.id).with_for_update().first()
    now = datetime.now(timezone.utc)
    if not proposal or proposal.confirmed_at or proposal.expires_at <= now:
        _error("PROPOSAL_EXPIRED", status.HTTP_409_CONFLICT)
    service = _service(db, binding, proposal.service_id)
    provider, location = _scope(db, binding)
    # A proposal does not reserve; recalculate at the point of confirmation.
    if not any(slot.get("start_time") == proposal.start_time for slot in availability(db, binding, service.id, proposal.start_time, proposal.end_time)):
        _error("SLOT_UNAVAILABLE", status.HTTP_409_CONFLICT)
    client = _resolve_client(db, binding, name, phone, email)
    booking = Booking(tenant_id=binding.tenant_id, client_id=client.id, provider_id=provider.id, service_id=service.id, location_id=location.id if location else None, start_time=proposal.start_time, end_time=proposal.end_time, status=BookingStatus.PENDING, idempotency_key=f"assistant-bridge:{binding.id}:{request_id}")
    db.add(booking); db.flush()
    try:
        slot_allocation_service.create_allocations_for_booking(db, booking=booking, buffer_before=max(15, service.buffer_before or 0), buffer_after=max(15, service.buffer_after or 0))
        scheduling_service.allocate_resources(db, booking=booking, commit=False)
        proposal.confirmed_at = now
        db.add(AssistantBookingBridgeReceipt(binding_id=binding.id, request_id=request_id, booking_id=booking.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        retry = db.query(AssistantBookingBridgeReceipt).filter_by(binding_id=binding.id, request_id=request_id).first()
        if retry:
            return db.query(Booking).filter_by(id=retry.booking_id, tenant_id=binding.tenant_id).first()
        _error("SLOT_UNAVAILABLE", status.HTTP_409_CONFLICT)
    db.refresh(booking); return booking
