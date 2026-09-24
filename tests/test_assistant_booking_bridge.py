import base64
import json
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException

from app.models.assistant_booking_bridge import AssistantBookingBridgeBinding
from app.services import assistant_booking_bridge as bridge
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.models import Provider, Service, Client, AuditLog, Tenant, Location
from app.models.booking import Booking
from app.schemas.assistant_booking_bridge import AvailabilityRequest
from app.models.assistant_booking_bridge import AssistantBookingBridgeProposal, AssistantBookingBridgeReceipt
from pydantic import ValidationError


def _keypair():
    private = Ed25519PrivateKey.generate()
    return private, base64.b64encode(private.public_key().public_bytes_raw()).decode()

def _signature(private, method: str, path: str, stamp: str, nonce: str, body: bytes) -> str:
    return base64.b64encode(private.sign(bridge.canonical_request(method, path, stamp, nonce, body))).decode()


def _signed_api(client, private, method: str, path: str, payload, nonce: str):
    body = b"" if payload is None else json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    stamp = str(int(datetime.now(timezone.utc).timestamp()))
    return client.request(
        method,
        path,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Assistant-Bridge-Key-Id": "api-synthetic-key",
            "X-Assistant-Bridge-Timestamp": stamp,
            "X-Assistant-Bridge-Nonce": nonce,
            "X-Assistant-Bridge-Signature": _signature(private, method, path, stamp, nonce, body),
        },
    )


def _api_scope(db_session, private):
    tenant = Tenant(id=101, name="Bridge Synthetic Tenant", subdomain="bridge-synthetic", timezone="Australia/Hobart")
    provider = Provider(id=102, tenant_id=tenant.id, name="Bridge Provider", active=True)
    location = Location(id=103, tenant_id=tenant.id, name="Bridge Location", timezone="Australia/Sydney", active=True)
    service = Service(id=104, tenant_id=tenant.id, name="Bridge Service", duration=30, price="42.50", active=True)
    foreign_service = Service(id=105, tenant_id=999, name="Other Tenant Service", duration=30, active=True)
    binding = AssistantBookingBridgeBinding(
        line_key="primary", tenant_id=tenant.id, provider_id=provider.id,
        default_location_id=location.id, credential_key_id="api-synthetic-key",
        public_key=base64.b64encode(private.public_key().public_bytes_raw()).decode(), enabled=True,
    )
    db_session.add_all((tenant, provider, location, service, foreign_service, binding))
    db_session.commit()
    return binding, service, foreign_service


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


def test_existing_booking_claim_is_a_stable_retry_and_rejects_payload_reuse(db_session):
    private, _ = _keypair()
    binding, service, _ = _api_scope(db_session, private)
    client = Client(tenant_id=binding.tenant_id, name="Synthetic Customer", phone="+61000000000", active=True)
    db_session.add(client)
    db_session.flush()
    request_id = "synthetic-existing-claim"
    proposal_id = "00000000-0000-0000-0000-000000000111"
    fingerprint = bridge._request_fingerprint(proposal_id, "Synthetic Customer", "+61000000000", None)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    booking = Booking(
        tenant_id=binding.tenant_id,
        client_id=client.id,
        provider_id=binding.provider_id,
        service_id=service.id,
        start_time=start,
        end_time=start + timedelta(minutes=service.duration),
        status="pending",
        idempotency_key=bridge._booking_idempotency_key(binding.id, request_id),
        notes=bridge._fingerprint_note(fingerprint),
    )
    db_session.add(booking)
    db_session.commit()

    assert bridge.confirm(
        db_session, binding, proposal_id, request_id, "Synthetic Customer", "+61000000000", None,
    ).id == booking.id
    with pytest.raises(HTTPException) as conflict:
        bridge.confirm(
            db_session, binding, proposal_id, request_id, "Changed Customer", "+61000000000", None,
        )
    assert conflict.value.detail["code"] == "REQUEST_ID_CONFLICT"


def test_signed_api_rejects_missing_auth_replay_invalid_schema_and_foreign_scope(client, db_session, monkeypatch):
    private, _ = _keypair()
    _, service, foreign_service = _api_scope(db_session, private)
    path = "/api/internal/assistant-booking-bridge/availability"
    now = datetime.now(timezone.utc) + timedelta(days=1)

    assert client.post(path, json={}).status_code == 401
    invalid = _signed_api(client, private, "POST", path, {
        "service_id": service.id,
        "start_time": "2030-01-01T10:00:00",
        "end_time": "2030-01-01T11:00:00",
    }, "api-invalid-schema")
    assert invalid.status_code == 422

    foreign = _signed_api(client, private, "POST", path, {
        "service_id": foreign_service.id,
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(hours=1)).isoformat(),
    }, "api-foreign-service")
    assert foreign.status_code == 422
    assert foreign.json()["error"]["message"]["code"] == "SERVICE_UNAVAILABLE"

    monkeypatch.setattr(bridge, "availability", lambda *_args: [])
    valid_payload = {
        "service_id": service.id,
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(hours=1)).isoformat(),
    }
    first = _signed_api(client, private, "POST", path, valid_payload, "api-replay")
    assert first.status_code == 200
    replay = _signed_api(client, private, "POST", path, valid_payload, "api-replay")
    assert replay.status_code == 409
    assert replay.json()["error"]["message"]["code"] == "BRIDGE_REPLAY"


def test_signed_catalog_and_proposal_expose_summary_timezone_not_scope_ids(client, db_session, monkeypatch):
    private, _ = _keypair()
    _, service, _ = _api_scope(db_session, private)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=1)
    monkeypatch.setattr(bridge, "availability", lambda *_args: [{"start_time": now.isoformat()}])

    catalog = _signed_api(client, private, "GET", "/api/internal/assistant-booking-bridge/catalog", None, "api-catalog")
    assert catalog.status_code == 200
    assert catalog.json()["data"] == {
        "services": [{"id": service.id, "name": "Bridge Service", "duration_minutes": 30, "price": "42.50"}],
        "timezone": "Australia/Sydney",
    }

    proposal = _signed_api(client, private, "POST", "/api/internal/assistant-booking-bridge/proposals", {
        "service_id": service.id,
        "start_time": now.isoformat(),
    }, "api-proposal")
    assert proposal.status_code == 200
    data = proposal.json()["data"]
    assert set(data) == {"proposal_id", "summary", "expires_at", "status"}
    assert data["summary"] == {
        "service_name": "Bridge Service",
        "duration_minutes": 30,
        "price": "42.50",
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(minutes=30)).isoformat(),
        "timezone": "Australia/Sydney",
        "provider_name": "Bridge Provider",
        "location_name": "Bridge Location",
    }


def test_api_confirmation_requires_proposal_then_claims_request_idempotently(client, db_session, monkeypatch):
    private, _ = _keypair()
    binding, service, _ = _api_scope(db_session, private)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=1)
    monkeypatch.setattr(bridge, "availability", lambda *_args: [{"start_time": now.isoformat()}])
    monkeypatch.setattr(bridge.slot_allocation_service, "create_allocations_for_booking", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bridge.scheduling_service, "allocate_resources", lambda *_args, **_kwargs: None)

    early = _signed_api(client, private, "POST", "/api/internal/assistant-booking-bridge/confirmations", {
        "proposal_id": "00000000-0000-0000-0000-000000000104",
        "request_id": "synthetic-inbound-104",
        "customer_name": "Synthetic Customer",
        "customer_phone": "+61000000000",
    }, "api-confirm-early")
    assert early.status_code == 409
    assert db_session.query(Booking).count() == 0

    proposal_response = _signed_api(client, private, "POST", "/api/internal/assistant-booking-bridge/proposals", {
        "service_id": service.id,
        "start_time": now.isoformat(),
    }, "api-confirm-proposal")
    proposal_id = proposal_response.json()["data"]["proposal_id"]
    command = {
        "proposal_id": proposal_id,
        "request_id": "synthetic-inbound-104",
        "customer_name": "Synthetic Customer",
        "customer_phone": "+61000000000",
    }
    first = _signed_api(client, private, "POST", "/api/internal/assistant-booking-bridge/confirmations", command, "api-confirm-first")
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "pending"
    retry = _signed_api(client, private, "POST", "/api/internal/assistant-booking-bridge/confirmations", command, "api-confirm-retry")
    assert retry.status_code == 200
    assert retry.json()["data"]["booking_id"] == first.json()["data"]["booking_id"]
    changed = dict(command, customer_name="Different Synthetic Customer")
    conflict = _signed_api(client, private, "POST", "/api/internal/assistant-booking-bridge/confirmations", changed, "api-confirm-conflict")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["message"]["code"] == "REQUEST_ID_CONFLICT"
    assert db_session.query(Booking).filter_by(tenant_id=binding.tenant_id).count() == 1
    assert db_session.query(AssistantBookingBridgeReceipt).filter_by(binding_id=binding.id, request_id=command["request_id"]).count() == 1
