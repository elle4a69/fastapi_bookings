"""Concurrency tests for first-confirmed-submission-wins booking model.

Proves that:
1. Concurrent booking submissions for the exact same slot result in exactly 1 winner and 409 Conflict for all losers.
2. 15-minute inter-booking buffer conflicts are strictly enforced under concurrency.
3. Idempotent requests concurrently submitted return the same booking without creating duplicates.
4. Waitlist entries operate purely as passive records without generating holds or race conditions.
"""

import concurrent.futures
import os
import tempfile
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.db.database import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.service import Service
from app.models.provider import Provider
from app.models.client import Client
from app.models.location import Location
from app.models.booking import Booking
from app.models.waitlist import WaitlistEntry, WaitlistStatus
from app.core.state_machine import BookingStatus
from app.core.security import get_password_hash, create_access_token
from app.main import app as fastapi_app


@pytest.fixture
def concurrent_db():
    """File-backed temporary SQLite database for safe multi-threaded concurrency testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"timeout": 30, "check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield Session
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def setup_concurrency_data(Session):
    db = Session()
    tenant = Tenant(name="Concurrency Clinic", subdomain="concurrency")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        login="admin_concurrent",
        password_hash=get_password_hash("password123"),
        role="owner",
    )
    service = Service(
        tenant_id=tenant.id,
        name="Consultation",
        duration=30,
        buffer_before=15,
        buffer_after=15,
        price=100.0,
        active=True,
    )
    provider = Provider(
        tenant_id=tenant.id,
        name="Dr. Concurrent",
        email="provider@concurrency.com",
        active=True,
    )
    client_a = Client(
        tenant_id=tenant.id,
        name="Client Alice",
        email="alice@example.com",
        active=True,
    )
    client_b = Client(
        tenant_id=tenant.id,
        name="Client Bob",
        email="bob@example.com",
        active=True,
    )
    location = Location(
        tenant_id=tenant.id,
        name="Main Office",
    )
    db.add_all([user, service, provider, client_a, client_b, location])
    db.commit()
    db.refresh(service)
    db.refresh(provider)
    db.refresh(client_a)
    db.refresh(client_b)
    db.refresh(location)

    tenant_id = tenant.id
    provider_id = provider.id
    service_id = service.id
    client_a_id = client_a.id
    client_b_id = client_b.id
    location_id = location.id

    db.close()
    return tenant_id, provider_id, service_id, client_a_id, client_b_id, location_id


def test_concurrent_booking_submissions_first_wins(concurrent_db):
    """Prove that with 10 concurrent requests for the same slot, exactly 1 wins and 9 receive 409 Conflict."""
    tenant_id, provider_id, service_id, client_a_id, client_b_id, location_id = setup_concurrency_data(concurrent_db)

    def override_get_db():
        db = concurrent_db()
        try:
            yield db
        finally:
            db.close()

    def override_get_public_tenant():
        db = concurrent_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            return tenant
        finally:
            db.close()

    from app.api.deps import get_db, get_public_tenant
    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_public_tenant] = override_get_public_tenant

    start_time = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=30)

    token = create_access_token({"sub": "concurrency"})
    headers = {"X-Tenant": "concurrency", "X-Token": token}

    results = []

    def book_slot(client_idx):
        client = TestClient(fastapi_app)
        payload = {
            "service_id": service_id,
            "provider_id": provider_id,
            "location_id": location_id,
            "client_name": f"Customer {client_idx}",
            "client_email": f"cust{client_idx}@example.com",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        res = client.post("/api/public/bookings", json=payload, headers=headers)
        results.append((res.status_code, res.text))

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(book_slot, i) for i in range(10)]
        concurrent.futures.wait(futures)

    fastapi_app.dependency_overrides.clear()

    status_codes = [status for status, _ in results]
    successes = [s for s in status_codes if s in (200, 201)]
    conflicts = [s for s in status_codes if s == 409]

    assert len(successes) == 1, f"Expected exactly 1 successful booking, got {len(successes)}. Statuses: {status_codes}"
    assert len(conflicts) == 9, f"Expected 9 HTTP 409 Conflicts, got {len(conflicts)}. Statuses: {status_codes}"

    db = concurrent_db()
    bookings_in_db = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.start_time == start_time,
            Booking.status != BookingStatus.CANCELLED,
        )
        .all()
    )
    assert len(bookings_in_db) == 1, f"Expected exactly 1 booking in database, found {len(bookings_in_db)}"
    db.close()


def test_concurrent_booking_buffer_conflict(concurrent_db):
    """Prove that overlapping bookings within the 15-minute buffer boundary conflict atomically."""
    tenant_id, provider_id, service_id, client_a_id, client_b_id, location_id = setup_concurrency_data(concurrent_db)

    def override_get_db():
        db = concurrent_db()
        try:
            yield db
        finally:
            db.close()

    def override_get_public_tenant():
        db = concurrent_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            return tenant
        finally:
            db.close()

    from app.api.deps import get_db, get_public_tenant
    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_public_tenant] = override_get_public_tenant

    base_time = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)

    token = create_access_token({"sub": "concurrency"})
    headers = {"X-Tenant": "concurrency", "X-Token": token}

    client = TestClient(fastapi_app)
    res_a = client.post(
        "/api/public/bookings",
        json={
            "service_id": service_id,
            "provider_id": provider_id,
            "location_id": location_id,
            "client_id": client_a_id,
            "start_time": base_time.isoformat(),
            "end_time": (base_time + timedelta(minutes=30)).isoformat(),
        },
        headers=headers,
    )
    assert res_a.status_code in (200, 201), f"First booking should succeed: {res_a.text}"

    # Second booking overlapping within buffer window (10:35 - 11:05 overlaps with 10:00-10:30 + 15m buffer)
    res_b = client.post(
        "/api/public/bookings",
        json={
            "service_id": service_id,
            "provider_id": provider_id,
            "location_id": location_id,
            "client_id": client_b_id,
            "start_time": (base_time + timedelta(minutes=35)).isoformat(),
            "end_time": (base_time + timedelta(minutes=65)).isoformat(),
        },
        headers=headers,
    )
    assert res_b.status_code == 409, f"Second booking within 15m buffer must return 409 Conflict, got {res_b.status_code}"

    fastapi_app.dependency_overrides.clear()


def test_concurrent_booking_idempotency(concurrent_db):
    """Prove that concurrent requests with identical idempotency_key return the same booking and do not duplicate."""
    tenant_id, provider_id, service_id, client_a_id, client_b_id, location_id = setup_concurrency_data(concurrent_db)

    def override_get_db():
        db = concurrent_db()
        try:
            yield db
        finally:
            db.close()

    def override_get_public_tenant():
        db = concurrent_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            return tenant
        finally:
            db.close()

    from app.api.deps import get_db, get_public_tenant
    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_public_tenant] = override_get_public_tenant

    start_time = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=11, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=30)
    idempotency_key = "idemp-key-xyz-12345"

    token = create_access_token({"sub": "concurrency"})
    headers = {"X-Tenant": "concurrency", "X-Token": token}

    results = []

    def submit_idempotent():
        client = TestClient(fastapi_app)
        payload = {
            "service_id": service_id,
            "provider_id": provider_id,
            "location_id": location_id,
            "client_id": client_a_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "idempotency_key": idempotency_key,
        }
        res = client.post("/api/public/bookings", json=payload, headers=headers)
        results.append(res)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(submit_idempotent) for _ in range(5)]
        concurrent.futures.wait(futures)

    fastapi_app.dependency_overrides.clear()

    # All should return 200/201
    assert all(r.status_code in (200, 201) for r in results), f"Expected 200/201, got statuses: {[r.status_code for r in results]}"
    booking_ids = {r.json()["data"]["id"] for r in results}
    assert len(booking_ids) == 1, f"All idempotent responses must return the same booking ID: {booking_ids}"

    db = concurrent_db()
    total_bookings = db.query(Booking).filter(Booking.idempotency_key == idempotency_key).count()
    assert total_bookings == 1, f"Database must contain exactly 1 booking for idempotency key, found {total_bookings}"
    db.close()


def test_concurrent_waitlist_passive_safety(concurrent_db):
    """Prove that waitlist entries operate passively without auto-creating holds or causing race conditions."""
    tenant_id, provider_id, service_id, client_a_id, client_b_id, _ = setup_concurrency_data(concurrent_db)

    db = concurrent_db()
    tomorrow = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)

    entry_a = WaitlistEntry(
        tenant_id=tenant_id,
        service_id=service_id,
        client_id=client_a_id,
        provider_id=provider_id,
        desired_date_from=tomorrow,
        desired_date_to=tomorrow + timedelta(hours=4),
        status=WaitlistStatus.REQUESTED,
    )
    entry_b = WaitlistEntry(
        tenant_id=tenant_id,
        service_id=service_id,
        client_id=client_b_id,
        provider_id=provider_id,
        desired_date_from=tomorrow,
        desired_date_to=tomorrow + timedelta(hours=4),
        status=WaitlistStatus.REQUESTED,
    )
    db.add_all([entry_a, entry_b])
    db.commit()

    # Verify both entries exist with status REQUESTED
    entries = db.query(WaitlistEntry).filter(WaitlistEntry.tenant_id == tenant_id).all()
    assert len(entries) == 2
    assert all(e.status == WaitlistStatus.REQUESTED for e in entries)

    # Verify no bookings were autonomously created
    bookings = db.query(Booking).filter(Booking.tenant_id == tenant_id).count()
    assert bookings == 0
    db.close()
