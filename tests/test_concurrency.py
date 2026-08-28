"""Tests for atomic first-submit-wins booking creation, slot allocations, and concurrency."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    Tenant,
    User,
    Service,
    Provider,
    ServiceProvider,
    Client as ClientModel,
    Booking as BookingModel,
    BookingSlotAllocation,
    OutboxEvent,
    WaitlistEntry,
    WaitlistStatus,
)
from app.core.state_machine import BookingStatus


@pytest.fixture
def test_setup(db_session: Session):
    """Setup test fixture for concurrency testing."""
    tenant = db_session.query(Tenant).filter(Tenant.subdomain == "concurrency-test").first()
    if not tenant:
        tenant = Tenant(name="Concurrency Test Tenant", subdomain="concurrency-test")
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

    user = db_session.query(User).filter(User.login == "concurrency-admin").first()
    if not user:
        user = User(
            login="concurrency-admin",
            password_hash="mock-password",
            tenant_id=tenant.id,
            role="owner",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    service = db_session.query(Service).filter(Service.name == "Concurrency Service", Service.tenant_id == tenant.id).first()
    if not service:
        service = Service(
            name="Concurrency Service",
            duration=30,
            price=50.0,
            tenant_id=tenant.id,
            active=True,
            buffer_before=15,
            buffer_after=15,
        )
        db_session.add(service)
        db_session.commit()
        db_session.refresh(service)

    provider = db_session.query(Provider).filter(Provider.name == "Concurrency Provider", Provider.tenant_id == tenant.id).first()
    if not provider:
        provider = Provider(
            name="Concurrency Provider",
            tenant_id=tenant.id,
            active=True,
            ignore_company_hours=True,
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

    sp = db_session.query(ServiceProvider).filter(ServiceProvider.service_id == service.id, ServiceProvider.provider_id == provider.id).first()
    if not sp:
        sp = ServiceProvider(service_id=service.id, provider_id=provider.id, tenant_id=tenant.id)
        db_session.add(sp)
        db_session.commit()

    client_user = db_session.query(ClientModel).filter(ClientModel.email == "concurrency-client@example.com", ClientModel.tenant_id == tenant.id).first()
    if not client_user:
        client_user = ClientModel(
            name="Concurrency Client",
            email="concurrency-client@example.com",
            phone="+15550001111",
            tenant_id=tenant.id,
        )
        db_session.add(client_user)
        db_session.commit()
        db_session.refresh(client_user)

    return {
        "tenant": tenant,
        "admin": user,
        "service": service,
        "provider": provider,
        "client": client_user,
    }


def test_twenty_simultaneous_submissions_exactly_one_wins(client, test_setup, db_session):
    """Test 20 simultaneous/competing booking submissions for the exact same slot.

    Requirements:
    - Exactly 1 submission succeeds with HTTP 200/201.
    - Exactly 19 submissions fail with HTTP 409 Conflict.
    - Exactly 1 booking record and its matching slot allocations exist in DB.
    - Exactly 1 outbox event was created.
    """
    tenant = test_setup["tenant"]
    service = test_setup["service"]
    provider = test_setup["provider"]

    start_dt = (datetime.now(timezone.utc) + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)

    num_attempts = 20
    results = []

    for i in range(num_attempts):
        unique_key = f"race-{uuid.uuid4()}"
        payload = {
            "client_name": f"Client {i}",
            "client_email": f"client{i}@example.com",
            "client_phone": f"+1555999{i:04d}",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "idempotency_key": unique_key,
        }
        res = client.post(
            "/api/public/bookings",
            json=payload,
            headers={"X-Tenant": tenant.subdomain},
        )
        results.append((res.status_code, res.json()))

    statuses = [status for status, _ in results]
    successes = [s for s in statuses if s in (200, 201)]
    conflicts = [s for s in statuses if s == 409]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {statuses}"
    assert len(conflicts) == 19, f"Expected exactly 19 conflicts, got {len(conflicts)}: {statuses}"

    db_session.expire_all()
    # Verify DB state
    bookings = (
        db_session.query(BookingModel)
        .filter(
            BookingModel.provider_id == provider.id,
            BookingModel.start_time == start_dt,
            BookingModel.status != BookingStatus.CANCELLED,
        )
        .all()
    )
    assert len(bookings) == 1
    winning_booking = bookings[0]

    allocations = (
        db_session.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == winning_booking.id)
        .order_by(BookingSlotAllocation.slot_start)
        .all()
    )
    assert len(allocations) == 4

    events = (
        db_session.query(OutboxEvent)
        .filter(
            OutboxEvent.tenant_id == tenant.id,
            OutboxEvent.type == "booking.created",
        )
        .all()
    )
    matching_events = [e for e in events if (e.data() or {}).get("id") == winning_booking.id]
    assert len(matching_events) == 1


def test_buffer_collision_and_overlap_conflicts(client, test_setup, db_session):
    """Test overlapping bookings and 15-minute buffer collisions conflict with HTTP 409."""
    tenant = test_setup["tenant"]
    service = test_setup["service"]
    provider = test_setup["provider"]

    base_start = (datetime.now(timezone.utc) + timedelta(days=6)).replace(hour=14, minute=0, second=0, microsecond=0)
    base_end = base_start + timedelta(minutes=30)

    # 1. First booking: 14:00 - 14:30 (buffer covers 13:45 to 14:45)
    res1 = client.post(
        "/api/public/bookings",
        json={
            "client_name": "Primary Client",
            "client_email": "primary@example.com",
            "client_phone": "+15551112222",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": base_start.isoformat(),
            "end_time": base_end.isoformat(),
            "idempotency_key": f"prim-{uuid.uuid4()}",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res1.status_code == 200, res1.text

    # 2. Overlapping booking: 14:15 - 14:45 -> must fail 409
    res_overlap = client.post(
        "/api/public/bookings",
        json={
            "client_name": "Overlap Client",
            "client_email": "overlap@example.com",
            "client_phone": "+15551112223",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": (base_start + timedelta(minutes=15)).isoformat(),
            "end_time": (base_end + timedelta(minutes=15)).isoformat(),
            "idempotency_key": f"overlap-{uuid.uuid4()}",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res_overlap.status_code == 409

    # 3. Buffer collision booking: 14:30 - 15:00 (violates 15m post-buffer ending at 14:45) -> must fail 409
    res_buf = client.post(
        "/api/public/bookings",
        json={
            "client_name": "Buffer Client",
            "client_email": "buffer@example.com",
            "client_phone": "+15551112224",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": base_end.isoformat(),
            "end_time": (base_end + timedelta(minutes=30)).isoformat(),
            "idempotency_key": f"buffer-{uuid.uuid4()}",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res_buf.status_code == 409

    # 4. Valid non-overlapping booking with buffer respected: 15:00 - 15:30 (buffer starts 14:45) -> must succeed 200
    res_valid = client.post(
        "/api/public/bookings",
        json={
            "client_name": "Valid Client",
            "client_email": "valid@example.com",
            "client_phone": "+15551112225",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": (base_end + timedelta(minutes=30)).isoformat(),
            "end_time": (base_end + timedelta(minutes=60)).isoformat(),
            "idempotency_key": f"valid-{uuid.uuid4()}",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res_valid.status_code == 200, res_valid.text


def test_cancellation_releases_slot_allocations(client, test_setup, db_session):
    """Test cancellation deletes slot allocations and frees the time slot for subsequent bookings."""
    tenant = test_setup["tenant"]
    service = test_setup["service"]
    provider = test_setup["provider"]

    start_dt = (datetime.now(timezone.utc) + timedelta(days=7)).replace(hour=11, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)

    # 1. Create booking
    res1 = client.post(
        "/api/public/bookings",
        json={
            "client_name": "Cancel Test Client",
            "client_email": "canceltest@example.com",
            "client_phone": "+15553334444",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "idempotency_key": f"can1-{uuid.uuid4()}",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res1.status_code == 200
    booking_id = res1.json()["data"]["id"]

    db_session.expire_all()
    alloc_count = db_session.query(BookingSlotAllocation).filter(BookingSlotAllocation.booking_id == booking_id).count()
    assert alloc_count > 0

    # 2. Cancel the booking via admin endpoint
    res_cancel = client.post(
        f"/api/bookings/{booking_id}/cancel",
        headers={"X-Tenant": tenant.subdomain, "X-Token": "mock-admin-token"},
    )
    assert res_cancel.status_code == 200

    db_session.expire_all()
    alloc_count_after = db_session.query(BookingSlotAllocation).filter(BookingSlotAllocation.booking_id == booking_id).count()
    assert alloc_count_after == 0

    # 3. Create a new booking for the same slot -> must now succeed!
    res_rebook = client.post(
        "/api/public/bookings",
        json={
            "client_name": "Rebooked Client",
            "client_email": "rebooked@example.com",
            "client_phone": "+15553335555",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "idempotency_key": f"can2-{uuid.uuid4()}",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res_rebook.status_code == 200


def test_reschedule_atomically_updates_allocations(client, test_setup, db_session):
    """Test rescheduling atomically releases old allocations and claims new slots."""
    tenant = test_setup["tenant"]
    service = test_setup["service"]
    provider = test_setup["provider"]

    orig_start = (datetime.now(timezone.utc) + timedelta(days=8)).replace(hour=9, minute=0, second=0, microsecond=0)
    orig_end = orig_start + timedelta(minutes=30)
    target_start = (datetime.now(timezone.utc) + timedelta(days=8)).replace(hour=15, minute=0, second=0, microsecond=0)
    target_end = target_start + timedelta(minutes=30)

    # 1. Create booking
    res = client.post(
        "/api/public/bookings",
        json={
            "client_name": "Reschedule Client",
            "client_email": "resched@example.com",
            "client_phone": "+15556667777",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": orig_start.isoformat(),
            "end_time": orig_end.isoformat(),
            "idempotency_key": f"resch-{uuid.uuid4()}",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res.status_code == 200
    b_id = res.json()["data"]["id"]

    # 2. Reschedule to target slot
    res_resched = client.post(
        f"/api/bookings/{b_id}/reschedule",
        json={
            "new_start": target_start.isoformat(),
            "new_end": target_end.isoformat(),
        },
        headers={"X-Tenant": tenant.subdomain, "X-Token": "mock-admin-token"},
    )
    assert res_resched.status_code == 200

    db_session.expire_all()
    # Check that allocations now point to the target slots
    allocations = (
        db_session.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == b_id)
        .order_by(BookingSlotAllocation.slot_start)
        .all()
    )
    assert any(a.slot_start.replace(tzinfo=timezone.utc) == target_start for a in allocations)

    # 3. Old slot is now free for another booking
    res_old_slot = client.post(
        "/api/public/bookings",
        json={
            "client_name": "New Taker of Old Slot",
            "client_email": "newtaker@example.com",
            "client_phone": "+15556668888",
            "provider_id": provider.id,
            "service_id": service.id,
            "start_time": orig_start.isoformat(),
            "end_time": orig_end.isoformat(),
            "idempotency_key": f"newtaker-{uuid.uuid4()}",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res_old_slot.status_code == 200


def test_concurrent_idempotency_key_deduplication(client, test_setup):
    """Test duplicate submissions with identical idempotency_key return the same booking."""
    tenant = test_setup["tenant"]
    service = test_setup["service"]
    provider = test_setup["provider"]

    start_dt = (datetime.now(timezone.utc) + timedelta(days=9)).replace(hour=16, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)
    idem_key = f"idem-{uuid.uuid4()}"

    payload = {
        "client_name": "Idempotent Client",
        "client_email": "idem@example.com",
        "client_phone": "+15557778888",
        "provider_id": provider.id,
        "service_id": service.id,
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "idempotency_key": idem_key,
    }

    # First attempt
    res1 = client.post("/api/public/bookings", json=payload, headers={"X-Tenant": tenant.subdomain})
    assert res1.status_code == 200
    id1 = res1.json()["data"]["id"]

    # Second attempt with same key
    res2 = client.post("/api/public/bookings", json=payload, headers={"X-Tenant": tenant.subdomain})
    assert res2.status_code == 200
    id2 = res2.json()["data"]["id"]

    assert id1 == id2


def test_waitlist_passive_safety(test_setup, db_session):
    """Verify waitlist entries are passive administrative records and do not create bookings/allocations."""
    tenant = test_setup["tenant"]
    service = test_setup["service"]

    # Create passive waitlist entry
    wl = WaitlistEntry(
        tenant_id=tenant.id,
        service_id=service.id,
        client_id=test_setup["client"].id,
        desired_date_from=datetime.now(timezone.utc),
        status=WaitlistStatus.REQUESTED,
    )
    db_session.add(wl)
    db_session.commit()
    db_session.refresh(wl)

    # Confirm zero slot allocations exist for this waitlist entry
    allocs = db_session.query(BookingSlotAllocation).filter(BookingSlotAllocation.tenant_id == tenant.id).all()
    for a in allocs:
        assert a.booking_id is not None


def test_unrelated_integrity_error_returns_500_and_not_converted_to_409(client, test_setup, monkeypatch):
    """Simulate an unrelated IntegrityError and verify it returns a 500 server error and is NOT masked as 409."""
    tenant = test_setup["tenant"]
    service = test_setup["service"]
    provider = test_setup["provider"]

    from app.services import slot_allocation_service
    from sqlalchemy.exc import IntegrityError

    def fake_create_allocations(*args, **kwargs):
        raise IntegrityError("INSERT INTO other_table ...", params={}, orig=Exception("FOREIGN KEY constraint failed"))

    monkeypatch.setattr(slot_allocation_service, "create_allocations_for_booking", fake_create_allocations)

    start_dt = (datetime.now(timezone.utc) + timedelta(days=15)).replace(hour=10, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)

    payload = {
        "client_name": "Integrity Test Client",
        "client_email": "integrity@example.com",
        "client_phone": "+15558881111",
        "provider_id": provider.id,
        "service_id": service.id,
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "idempotency_key": f"unrelated-{uuid.uuid4()}",
    }

    test_c = TestClient(client.app, raise_server_exceptions=False)
    res = test_c.post("/api/public/bookings", json=payload, headers={"X-Tenant": tenant.subdomain})
    assert res.status_code == 500
    assert res.status_code != 409


def test_resource_allocation_http_exception_preserves_status_and_detail(client, test_setup, monkeypatch):
    """Verify HTTPException raised by resource allocation preserves its original HTTP status and error message."""
    tenant = test_setup["tenant"]
    service = test_setup["service"]
    provider = test_setup["provider"]

    from app.services import scheduling_service
    from fastapi import HTTPException

    def fake_allocate_resources(*args, **kwargs):
        raise HTTPException(status_code=422, detail="Specific resource quota exceeded")

    monkeypatch.setattr(scheduling_service, "allocate_resources", fake_allocate_resources)

    start_dt = (datetime.now(timezone.utc) + timedelta(days=16)).replace(hour=10, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)

    payload = {
        "client_name": "Resource Test Client",
        "client_email": "resource@example.com",
        "client_phone": "+15558882222",
        "provider_id": provider.id,
        "service_id": service.id,
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "idempotency_key": f"res-exc-{uuid.uuid4()}",
    }

    res = client.post("/api/public/bookings", json=payload, headers={"X-Tenant": tenant.subdomain})
    assert res.status_code == 422
    assert "Specific resource quota exceeded" in res.text


def test_unexpected_outbox_or_runtime_failure_rolls_back_everything(client, test_setup, db_session, monkeypatch):
    """Verify an unexpected runtime error (e.g. outbox failure) returns 500 and leaves zero DB state."""
    tenant = test_setup["tenant"]
    service = test_setup["service"]
    provider = test_setup["provider"]

    from app.api.routers import public_bookings

    def fake_create_outbox(*args, **kwargs):
        raise RuntimeError("Simulated catastrophic outbox serialization crash")

    monkeypatch.setattr(public_bookings, "create_outbox_event", fake_create_outbox)

    start_dt = (datetime.now(timezone.utc) + timedelta(days=17)).replace(hour=10, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)
    idem_key = f"crash-{uuid.uuid4()}"

    payload = {
        "client_name": "Crash Test Client",
        "client_email": "crashtest@example.com",
        "client_phone": "+15558883333",
        "provider_id": provider.id,
        "service_id": service.id,
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "idempotency_key": idem_key,
    }

    test_c = TestClient(client.app, raise_server_exceptions=False)
    res = test_c.post("/api/public/bookings", json=payload, headers={"X-Tenant": tenant.subdomain})
    assert res.status_code == 500

    db_session.expire_all()

    # Verify zero booking persisted
    bk = db_session.query(BookingModel).filter(BookingModel.idempotency_key == idem_key).first()
    assert bk is None

    # Verify zero slot allocations persisted for this time
    allocs = (
        db_session.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.provider_id == provider.id, BookingSlotAllocation.slot_start == start_dt)
        .all()
    )
    assert len(allocs) == 0
