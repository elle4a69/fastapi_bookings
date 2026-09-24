import base64
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.assistant_booking_bridge import AssistantBookingBridgeBinding
from app.services import assistant_booking_bridge as bridge
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.models import Provider, Service, Client, AuditLog
from app.models.booking import Booking
from app.schemas.assistant_booking_bridge import AvailabilityRequest
from app.models.assistant_booking_bridge import AssistantBookingBridgeProposal
from datetime import timedelta
from pydantic import ValidationError


def _keypair():
    private = Ed25519PrivateKey.generate()
    return private, base64.b64encode(private.public_key().public_bytes_raw()).decode()

def _signature(private, method: str, path: str, stamp: str, nonce: str, body: bytes) -> str:
    return base64.b64encode(private.sign(bridge.canonical_request(method, path, stamp, nonce, body))).decode()


def test_signed_request_is_one_use_and_does_not_require_raw_secret_storage(db_session):
    private, public_key = _keypair()
    binding = AssistantBookingBridgeBinding(
        line_key="primary", tenant_id=1, provider_id=1, credential_key_id="synthetic-key",
        public_key=public_key, enabled=True,
    )
    db_session.add(binding); db_session.commit()
    stamp = str(int(datetime.now(timezone.utc).timestamp()))
    body = b'{"service_id":1}'
    signature = _signature(private, "POST", "/api/internal/assistant-booking-bridge/availability", stamp, "nonce-1", body)
    authenticated = bridge.authenticate(db_session, method="POST", path="/api/internal/assistant-booking-bridge/availability", body=body, key_id="synthetic-key", timestamp=stamp, nonce="nonce-1", signature=signature)
    assert authenticated.line_key == "primary"
    with pytest.raises(HTTPException) as replay:
        bridge.authenticate(db_session, method="POST", path="/api/internal/assistant-booking-bridge/availability", body=body, key_id="synthetic-key", timestamp=stamp, nonce="nonce-1", signature=signature)
    assert replay.value.detail["code"] == "BRIDGE_REPLAY"


def test_disabled_binding_fails_closed_after_valid_signature(db_session):
    private, public_key = _keypair()
    db_session.add(AssistantBookingBridgeBinding(line_key="primary", tenant_id=1, provider_id=1, credential_key_id="disabled-key", public_key=public_key, enabled=False))
    db_session.commit()
    stamp = str(int(datetime.now(timezone.utc).timestamp()))
    with pytest.raises(HTTPException) as unavailable:
        bridge.authenticate(db_session, method="GET", path="/api/internal/assistant-booking-bridge/catalog", body=b"", key_id="disabled-key", timestamp=stamp, nonce="nonce-disabled", signature=_signature(private, "GET", "/api/internal/assistant-booking-bridge/catalog", stamp, "nonce-disabled", b""))
    assert unavailable.value.status_code == 503


def test_naive_availability_timestamp_is_rejected():
    with pytest.raises(ValidationError):
        AvailabilityRequest(service_id=1, start_time="2030-01-01T10:00:00", end_time="2030-01-01T11:00:00")


def test_iso_slot_proposal_and_pending_confirmation_are_idempotent_and_audited(db_session, monkeypatch):
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=1)
    provider = Provider(id=10, tenant_id=1, name="Provider One", active=True)
    service = Service(id=11, tenant_id=1, name="Service One", duration=30, active=True)
    binding = AssistantBookingBridgeBinding(line_key="primary", tenant_id=1, provider_id=10, credential_key_id="test-key", public_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", enabled=True)
    db_session.add_all((provider, service, binding)); db_session.commit()
    monkeypatch.setattr(bridge, "availability", lambda *_args: [{"start_time": now.isoformat()}])
    proposal = bridge.propose(db_session, binding, service.id, now)
    assert proposal.start_time.replace(tzinfo=timezone.utc) == now
    monkeypatch.setattr(bridge, "_resolve_client", lambda *_args: Client(id=12, tenant_id=1, name="Synthetic"))
    monkeypatch.setattr(bridge.slot_allocation_service, "create_allocations_for_booking", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bridge.scheduling_service, "allocate_resources", lambda *_args, **_kwargs: None)
    first = bridge.confirm(db_session, binding, proposal.id, "request-synthetic-1", "Synthetic", "+61000000000", None)
    second = bridge.confirm(db_session, binding, proposal.id, "request-synthetic-1", "Synthetic", "+61000000000", None)
    assert first.id == second.id
    assert first.status.value == "pending"
    assert db_session.query(AuditLog).filter_by(target_id=first.id, action="assistant_bridge.booking_created").count() == 1


def test_expired_proposal_fails_closed(db_session):
    binding = AssistantBookingBridgeBinding(id=21, line_key="primary", tenant_id=1, provider_id=1, credential_key_id="expiry-key", public_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", enabled=True)
    expired = AssistantBookingBridgeProposal(id="00000000-0000-0000-0000-000000000021", binding_id=21, service_id=1, start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    db_session.add_all((binding, expired)); db_session.commit()
    with pytest.raises(HTTPException) as error:
        bridge.confirm(db_session, binding, expired.id, "request-expired-1", "Synthetic", "+61000000000", None)
    assert error.value.detail["code"] == "PROPOSAL_EXPIRED"
