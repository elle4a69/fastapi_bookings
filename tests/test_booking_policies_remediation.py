import pytest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch, MagicMock
from fastapi import status
import stripe

from app.models.tenant import Tenant
from app.models.client import Client
from app.models.service import Service
from app.models.provider import Provider
from app.models.booking import Booking
from app.models.outbox import OutboxEvent
from app.models.management_review_request import ManagementReviewRequest
from app.core.security import create_access_token

@pytest.fixture(autouse=True)
def mock_stripe():
    with patch.object(stripe.checkout.Session, "retrieve") as mock_retrieve:
        mock_session = MagicMock()
        mock_session.payment_status = "paid"
        mock_retrieve.return_value = mock_session
        yield mock_retrieve

@pytest.fixture
def setup_data(db_session):
    db_session.query(ManagementReviewRequest).delete()
    db_session.query(Booking).delete()
    db_session.query(OutboxEvent).delete()
    db_session.commit()

    tenant = Tenant(name="Tenant A", subdomain="tenant-a", created_at=datetime.now(timezone.utc))
    db_session.add(tenant)
    db_session.commit()

    client_ok = Client(tenant_id=tenant.id, name="Client OK", email="ok@example.com", management_approval_required=False)
    client_restricted = Client(tenant_id=tenant.id, name="Client Restricted", email="res@example.com", management_approval_required=True, restriction_reason="High risk")
    service = Service(tenant_id=tenant.id, name="Therapy", duration=60, active=True, price=100.0, deposit_amount=25.0)
    provider = Provider(tenant_id=tenant.id, name="Dr. Smith", active=True)
    
    db_session.add_all([client_ok, client_restricted, service, provider])
    db_session.commit()
    
    return {
        "tenant": tenant,
        "client_ok": client_ok,
        "client_restricted": client_restricted,
        "service": service,
        "provider": provider,
    }

def test_client_restriction_ordinary_booking(client, setup_data):
    token = create_access_token({"sub": "tenant-a"})
    headers = {"X-Tenant": "tenant-a", "X-Token": token}

    # 1. Non-restricted client succeeds (except slot is not booked yet, we check next constraint or detail)
    # Wait, ordinary booking creation endpoint is POST /api/public/bookings
    # Let's post a booking for restricted client
    payload = {
        "client_id": setup_data["client_restricted"].id,
        "provider_id": setup_data["provider"].id,
        "service_id": setup_data["service"].id,
        "start_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "end_time": (datetime.now(timezone.utc) + timedelta(days=2, hours=1)).isoformat(),
        "notes": "Testing restriction"
    }
    response = client.post("/api/public/bookings", json=payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "management approval" in response.json()["error"]["message"]

def test_client_restriction_invoice_checkout(client, setup_data):
    token = create_access_token({"sub": "tenant-a"})
    headers = {"X-Tenant": "tenant-a", "X-Token": token}

    payload = {
        "client_id": setup_data["client_restricted"].id,
        "quote": {
            "client_id": setup_data["client_restricted"].id,
            "service_id": setup_data["service"].id,
        }
    }
    response = client.post("/api/public/invoices", json=payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "management approval" in response.json()["error"]["message"]

def test_management_review_request_flow(client, setup_data, db_session):
    token = create_access_token({"sub": "tenant-a"})
    headers = {"X-Tenant": "tenant-a", "X-Token": token}

    # 1. Submit review request
    pref_time = (datetime.now(timezone.utc) + timedelta(days=5)).replace(microsecond=0)
    payload = {
        "client_id": setup_data["client_restricted"].id,
        "service_id": setup_data["service"].id,
        "provider_id": setup_data["provider"].id,
        "preferred_time": pref_time.isoformat(),
        "reason": "Please approve me"
    }
    response = client.post("/api/public/management-reviews", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["ok"] is True
    assert data["data"]["state"] == "pending"
    assert data["data"]["slot_reserved"] is False

    # 2. Prevent duplicate pending requests
    response_dup = client.post("/api/public/management-reviews", json=payload, headers=headers)
    assert response_dup.status_code == status.HTTP_409_CONFLICT

    # 3. Admin list requests
    # Generate admin token
    from app.models.user import User
    admin_user = User(tenant_id=setup_data["tenant"].id, login="admin@test.com", password_hash="pwd", role="admin")
    db_session.add(admin_user)
    db_session.commit()
    admin_token = create_access_token({"sub": str(admin_user.id)})
    admin_headers = {"X-Tenant": "tenant-a", "X-Token": admin_token}

    response_list = client.get("/api/admin/management-reviews", headers=admin_headers)
    assert response_list.status_code == status.HTTP_200_OK
    assert len(response_list.json()["data"]) == 1

    # 4. Admin resolve request (approve)
    review_id = data["data"]["id"]
    response_resolve = client.put(
        f"/api/admin/management-reviews/{review_id}/resolve",
        json={"state": "approved", "resolution_notes": "All looks good"},
        headers=admin_headers
    )
    assert response_resolve.status_code == status.HTTP_200_OK
    assert response_resolve.json()["data"]["state"] == "approved"
    assert response_resolve.json()["data"]["resolved_by_id"] == admin_user.id

def test_checkout_commit_atomic(client, setup_data, db_session):

    token = create_access_token({"sub": "tenant-a"})
    headers = {"X-Tenant": "tenant-a", "X-Token": token}

    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    start_time = datetime.combine(target_date, time(hour=9), tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=1)

    # We need a provider schedule or workday for compute_availability to return it as available
    from app.models.schedule import ProviderWorkDay
    workday = ProviderWorkDay(
        tenant_id=setup_data["tenant"].id,
        provider_id=setup_data["provider"].id,
        weekday=start_time.weekday(),
        start_time="08:00",
        end_time="17:00",
        is_working=True
    )
    db_session.add(workday)
    db_session.commit()

    payload = {
        "stripe_session_id": "cs_test_123",
        "client_id": setup_data["client_ok"].id,
        "provider_id": setup_data["provider"].id,
        "service_id": setup_data["service"].id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "idempotency_key": "idemp-key-1"
    }

    # 1. Success Path: Create booking and invoice
    response = client.post("/api/public/checkout/commit", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    res_data = response.json()
    assert res_data["ok"] is True
    booking_id = res_data["data"]["booking_id"]
    invoice_id = res_data["data"]["invoice_id"]

    # 2. Idempotency check: sending the same request again returns same data
    response_dup = client.post("/api/public/checkout/commit", json=payload, headers=headers)
    assert response_dup.status_code == status.HTTP_200_OK
    assert response_dup.json()["data"]["booking_id"] == booking_id
    assert "idempotent" in response_dup.json()["data"]["message"]

    # 3. Slot revalidation / Concurrency: sending with different key but same time slot returns 409 Conflict
    payload_diff = payload.copy()
    payload_diff["idempotency_key"] = "idemp-key-2"
    response_conflict = client.post("/api/public/checkout/commit", json=payload_diff, headers=headers)
    assert response_conflict.status_code == status.HTTP_409_CONFLICT


def test_public_booking_tenant_isolation_and_policies(client, setup_data, db_session):
    """Verify tenant boundary enforcement and restriction policies on POST /api/public/bookings."""
    token_a = create_access_token({"sub": "tenant-a"})
    headers_a = {"X-Tenant": "tenant-a", "X-Token": token_a}

    # Create a second tenant with foreign resources
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b", created_at=datetime.now(timezone.utc))
    db_session.add(tenant_b)
    db_session.commit()

    client_b = Client(tenant_id=tenant_b.id, name="Client B", email="b@example.com")
    service_b = Service(tenant_id=tenant_b.id, name="Service B", duration=60, active=True, price=50.0)
    provider_b = Provider(tenant_id=tenant_b.id, name="Provider B", active=True)
    db_session.add_all([client_b, service_b, provider_b])
    db_session.commit()

    base_time = datetime.now(timezone.utc) + timedelta(days=5)
    valid_payload = {
        "client_id": setup_data["client_ok"].id,
        "provider_id": setup_data["provider"].id,
        "service_id": setup_data["service"].id,
        "start_time": base_time.isoformat(),
        "end_time": (base_time + timedelta(hours=1)).isoformat(),
        "notes": "Valid booking"
    }

    initial_booking_count = db_session.query(Booking).count()
    initial_outbox_count = db_session.query(OutboxEvent).count()

    # 1. Cross-tenant Provider: Tenant A attempts to book Tenant B's provider -> 404
    payload_bad_prov = valid_payload.copy()
    payload_bad_prov["provider_id"] = provider_b.id
    resp = client.post("/api/public/bookings", json=payload_bad_prov, headers=headers_a)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found" in resp.json()["error"]["message"]
    assert db_session.query(Booking).count() == initial_booking_count
    assert db_session.query(OutboxEvent).count() == initial_outbox_count

    # 2. Cross-tenant Service: Tenant A attempts to book Tenant B's service -> 404
    payload_bad_svc = valid_payload.copy()
    payload_bad_svc["service_id"] = service_b.id
    resp = client.post("/api/public/bookings", json=payload_bad_svc, headers=headers_a)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "Service not found" in resp.json()["error"]["message"]
    assert db_session.query(Booking).count() == initial_booking_count
    assert db_session.query(OutboxEvent).count() == initial_outbox_count

    # 3. Cross-tenant Client: Tenant A attempts to book for Tenant B's client -> 404
    payload_bad_client = valid_payload.copy()
    payload_bad_client["client_id"] = client_b.id
    resp = client.post("/api/public/bookings", json=payload_bad_client, headers=headers_a)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "Client not found" in resp.json()["error"]["message"]
    assert db_session.query(Booking).count() == initial_booking_count
    assert db_session.query(OutboxEvent).count() == initial_outbox_count

    # 4. Management Approval Required: restricted client -> 403
    payload_restricted = valid_payload.copy()
    payload_restricted["client_id"] = setup_data["client_restricted"].id
    resp = client.post("/api/public/bookings", json=payload_restricted, headers=headers_a)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "management approval" in resp.json()["error"]["message"]
    assert db_session.query(Booking).count() == initial_booking_count
    assert db_session.query(OutboxEvent).count() == initial_outbox_count

    # 5. Valid same-tenant public booking succeeds -> 200 and exactly 1 booking record + 1 outbox event created
    resp_valid = client.post("/api/public/bookings", json=valid_payload, headers=headers_a)
    assert resp_valid.status_code == status.HTTP_200_OK, resp_valid.text
    assert resp_valid.json()["ok"] is True
    assert db_session.query(Booking).count() == initial_booking_count + 1
    assert db_session.query(OutboxEvent).count() == initial_outbox_count + 1

    # Verify outbox event record properties
    created_outbox = db_session.query(OutboxEvent).order_by(OutboxEvent.id.desc()).first()
    assert created_outbox is not None
    assert created_outbox.type == "booking.created"
    assert created_outbox.tenant_id == setup_data["tenant"].id
    assert isinstance(created_outbox.tenant_id, int)


def test_public_booking_client_resolution_and_creation(client, setup_data, db_session):
    headers_a = {"X-Tenant": "tenant-a", "X-Token": create_access_token({"sub": "tenant-a"})}
    tenant_a = setup_data["tenant"]

    # 1. New Client Registration via Public Booking
    new_client_time = datetime.now(timezone.utc) + timedelta(days=10)
    payload_new_client = {
        "client_name": "Alice Wonderland",
        "client_email": "alice@example.com",
        "client_phone": "+61411222333",
        "provider_id": setup_data["provider"].id,
        "service_id": setup_data["service"].id,
        "start_time": new_client_time.isoformat(),
        "end_time": (new_client_time + timedelta(hours=1)).isoformat(),
        "notes": "New guest booking"
    }
    resp = client.post("/api/public/bookings", json=payload_new_client, headers=headers_a)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    
    # Assert client created in Tenant A
    created_client = db_session.query(Client).filter(
        Client.tenant_id == tenant_a.id,
        Client.email == "alice@example.com"
    ).first()
    assert created_client is not None
    assert created_client.name == "Alice Wonderland"
    assert created_client.phone == "+61411222333"

    # 2. Existing Client matched by email (no duplicate client row created)
    initial_client_count = db_session.query(Client).filter(Client.tenant_id == tenant_a.id).count()
    second_time = new_client_time + timedelta(days=1)
    payload_existing_client = {
        "client_name": "Alice W.",
        "client_email": "alice@example.com",
        "provider_id": setup_data["provider"].id,
        "service_id": setup_data["service"].id,
        "start_time": second_time.isoformat(),
        "end_time": (second_time + timedelta(hours=1)).isoformat(),
    }
    resp2 = client.post("/api/public/bookings", json=payload_existing_client, headers=headers_a)
    assert resp2.status_code == status.HTTP_200_OK, resp2.text
    final_client_count = db_session.query(Client).filter(Client.tenant_id == tenant_a.id).count()
    assert final_client_count == initial_client_count

    # 3. Missing all client identification fields -> 400 Bad Request
    payload_no_client = {
        "provider_id": setup_data["provider"].id,
        "service_id": setup_data["service"].id,
        "start_time": (second_time + timedelta(days=1)).isoformat(),
        "end_time": (second_time + timedelta(days=1, hours=1)).isoformat(),
    }
    resp3 = client.post("/api/public/bookings", json=payload_no_client, headers=headers_a)
    assert resp3.status_code == status.HTTP_400_BAD_REQUEST
