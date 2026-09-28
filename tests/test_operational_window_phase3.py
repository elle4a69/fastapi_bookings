"""Comprehensive tests for Phase 3: 5-Segment Operational Window & Availability Engine.

Tests:
1. Backward-chaining availability for an out-call slot (rejecting slots that collide with prior bookings).
2. Forward availability gap between two consecutive out-call bookings (transit + buffers fit check).
3. Atomic slot allocation across the full operational window (5:10 PM - 7:50 PM for a 6:00 PM - 7:00 PM appointment).
4. Canonical travel ownership principle (Booking B owns A -> B inbound transit).
5. In-call booking availability remains 100% backward-compatible.
6. Public API endpoints: GET /api/public/availability and POST /api/public/availability.
"""

from datetime import datetime, timedelta, timezone, time
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.tenant import Tenant, TravelChargeOrigin
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.booking import Booking, ServiceMode
from app.models.booking_slot_allocation import BookingSlotAllocation
from app.models.schedule import ProviderWorkDay
from app.core.state_machine import BookingStatus
from app.services.booking.operational_window import (
    OperationalWindow,
    OperationalWindowCalculator,
    get_operational_window_calculator,
)
from app.services.booking.availability_service import get_available_slots
from app.services.booking.slot_allocation_service import (
    create_allocations_for_booking,
    generate_slot_timestamps,
    generate_operational_slot_timestamps,
    is_slot_allocation_conflict,
)
from app.services.routing.geocoding import register_test_location, clear_test_locations


@pytest.fixture(autouse=True)
def clean_geocoding_registry():
    """Ensure clean test location registry for each test."""
    clear_test_locations()
    # Register deterministic test coordinates
    register_test_location("Sydney CBD", (-33.8688, 151.2093))
    register_test_location("Bondi", (-33.8915, 151.2767))
    register_test_location("Parramatta", (-33.8150, 151.0011))
    register_test_location("Manly", (-33.7971, 151.2878))
    yield
    clear_test_locations()


@pytest.fixture
def p3_tenant(db_session) -> Tenant:
    """Create test tenant."""
    tenant = Tenant(
        name="Phase 3 Operational Tenant",
        subdomain="p3op",
        allow_in_call=True,
        allow_out_call=True,
        travel_charge_origin=TravelChargeOrigin.ALWAYS_FROM_BASE.value,
        address="Sydney CBD",
        latitude=-33.8688,
        longitude=151.2093,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def p3_provider(db_session, p3_tenant) -> Provider:
    """Create mobile provider with working hours 09:00 to 21:00 UTC every day."""
    provider = Provider(
        tenant_id=p3_tenant.id,
        name="Alex Operational Specialist",
        allow_in_call=True,
        allow_out_call=True,
        in_call_address="Sydney CBD",
        out_call_radius_km=50.0,
        base_outcall_surcharge=Decimal("20.00"),
        per_km_fee=Decimal("2.00"),
        turnaround_buffer_mins=15,
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)

    # Add ProviderWorkDay for all 7 days (09:00 - 21:00 UTC)
    for weekday in range(7):
        wd = ProviderWorkDay(
            tenant_id=p3_tenant.id,
            provider_id=provider.id,
            weekday=weekday,
            start_time="09:00",
            end_time="21:00",
            is_working=True,
        )
        db_session.add(wd)
    db_session.commit()

    return provider


@pytest.fixture
def p3_client(db_session, p3_tenant) -> Client:
    """Create test client."""
    client = Client(
        tenant_id=p3_tenant.id,
        name="Sarah Jenkins",
        email="sarah.jenkins@example.com",
        phone="+61400111222",
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


@pytest.fixture
def p3_outcall_service(db_session, p3_tenant) -> Service:
    """Create service with explicit out-call buffer settings."""
    service = Service(
        tenant_id=p3_tenant.id,
        name="Signature Mobile Massage",
        duration=60,
        price=Decimal("150.00"),
        outcall_price=Decimal("190.00"),
        buffer_before=15,
        buffer_after=15,
        outcall_buffer_before=20,
        outcall_buffer_after=20,
        allow_in_call=True,
        allow_out_call=True,
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


# ---------------------------------------------------------------------------
# 1. Backward-Chaining Availability Tests
# ---------------------------------------------------------------------------

def test_backward_chaining_rejects_slot_colliding_with_inbound_travel(
    db_session, p3_tenant, p3_provider, p3_client, p3_outcall_service
):
    """Backward-chain from requested start time: To offer a 17:00 slot, verify provider is free

    starting from 17:00 - outcall_buffer_before (20m) - inbound_travel (~30-35m) = ~16:05.
    If a prior booking at Parramatta ends at 16:00 (with post-buffer 20m = free at 16:20),
    17:00 MUST be rejected because provider is not free at 16:05.
    The next valid slot must shift forward to at least 17:15 or 17:30.
    """
    test_date = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)

    # Prior booking at Parramatta from 14:00 to 16:00
    b_start = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc)
    prior_booking = Booking(
        tenant_id=p3_tenant.id,
        client_id=p3_client.id,
        provider_id=p3_provider.id,
        service_id=p3_outcall_service.id,
        start_time=b_start,
        end_time=b_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Parramatta",
        client_suburb="Parramatta",
    )
    db_session.add(prior_booking)
    db_session.commit()

    # Query out-call availability at Bondi on this date
    slots = get_available_slots(
        db=db_session,
        service_duration=p3_outcall_service.duration,
        provider_id=p3_provider.id,
        date=test_date,
        service_id=p3_outcall_service.id,
        service_mode="out_call",
        client_suburb="Bondi",
        service_address="Bondi",
    )

    slot_starts = [s["start"] for s in slots]

    # Slot at 17:00 (5:00 PM) must be rejected because:
    # Free time: 16:00 + 20m post-buffer = 16:20
    # Inbound travel (Parramatta -> Bondi) >= 30m
    # Pre-buffer: 20m
    # 17:00 - 50m = 16:10 < 16:20 (Provider not free!)
    slot_1700 = datetime(2026, 10, 15, 17, 0, tzinfo=timezone.utc)
    assert slot_1700 not in slot_starts, "Slot at 17:00 must be rejected due to inbound travel collision"

    # Slot at 16:30 must also be rejected
    slot_1630 = datetime(2026, 10, 15, 16, 30, tzinfo=timezone.utc)
    assert slot_1630 not in slot_starts

    # Slots after sufficient turnaround (e.g. 17:30 or 18:00) must be available
    slot_1800 = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)
    assert slot_1800 in slot_starts, "Slot at 18:00 should be available"


# ---------------------------------------------------------------------------
# 2. Forward Availability Gap Between Two Consecutive Out-Call Bookings
# ---------------------------------------------------------------------------

def test_forward_availability_gap_rejects_insufficient_transit_gap(
    db_session, p3_tenant, p3_provider, p3_client, p3_outcall_service
):
    """Verify that forward gap between a candidate slot and a subsequent booking

    must accommodate: [outcall_buffer_after] + [transit(A -> B)] + [next_pre_buffer].
    If gap is too tight, candidate slot is rejected.
    """
    test_date = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)

    # Next booking at Manly starting at 17:00 (5:00 PM)
    b_start = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc)
    next_booking = Booking(
        tenant_id=p3_tenant.id,
        client_id=p3_client.id,
        provider_id=p3_provider.id,
        service_id=p3_outcall_service.id,
        start_time=b_start,
        end_time=b_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Manly",
        client_suburb="Manly",
    )
    db_session.add(next_booking)
    db_session.commit()

    # Query out-call availability at Bondi
    slots = get_available_slots(
        db=db_session,
        service_duration=p3_outcall_service.duration,
        provider_id=p3_provider.id,
        date=test_date,
        service_id=p3_outcall_service.id,
        service_mode="out_call",
        client_suburb="Bondi",
        service_address="Bondi",
    )

    slot_starts = [s["start"] for s in slots]

    # Candidate slot from 15:30 to 16:30 at Bondi:
    # Ends at 16:30.
    # Post-buffer: 20m -> 16:50.
    # Transit Bondi -> Manly >= 20m -> 17:10 > 17:00.
    # Therefore, 15:30 slot CANNOT fit before 17:00 Manly booking!
    slot_1530 = datetime(2026, 10, 16, 15, 30, tzinfo=timezone.utc)
    assert slot_1530 not in slot_starts, "Slot at 15:30 must be rejected: cannot reach Manly by 17:00"

    # Candidate slot ending much earlier (e.g. 13:00 to 14:00) should be available
    slot_1300 = datetime(2026, 10, 16, 13, 0, tzinfo=timezone.utc)
    assert slot_1300 in slot_starts, "Slot at 13:00 should easily fit before 17:00 booking"


# ---------------------------------------------------------------------------
# 3. Atomic Operational Slot Allocation (5:10 PM - 7:50 PM for 6:00 PM - 7:00 PM)
# ---------------------------------------------------------------------------

def test_atomic_slot_allocation_across_full_operational_window(
    db_session, p3_tenant, p3_provider, p3_client, p3_outcall_service
):
    """Test atomic slot allocation across the full 5-segment operational window:

    5:10 PM - 7:50 PM for a 6:00 PM - 7:00 PM appointment.
    Ensures uq_provider_slot_allocation atomically locks every 15-minute slice.
    Visible booking start_time and end_time remain 18:00 - 19:00.
    """
    app_start = datetime(2026, 10, 17, 18, 0, tzinfo=timezone.utc)  # 6:00 PM
    app_end = datetime(2026, 10, 17, 19, 0, tzinfo=timezone.utc)    # 7:00 PM

    op_start = datetime(2026, 10, 17, 17, 10, tzinfo=timezone.utc)  # 5:10 PM (50m before)
    op_end = datetime(2026, 10, 17, 19, 50, tzinfo=timezone.utc)    # 7:50 PM (50m after)

    booking = Booking(
        tenant_id=p3_tenant.id,
        client_id=p3_client.id,
        provider_id=p3_provider.id,
        service_id=p3_outcall_service.id,
        start_time=app_start,
        end_time=app_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Bondi",
        client_suburb="Bondi",
    )
    db_session.add(booking)
    db_session.commit()

    # Allocate across explicit operational window (5:10 PM to 7:50 PM)
    allocations = create_allocations_for_booking(
        db_session,
        booking=booking,
        operational_window_start=op_start,
        operational_window_end=op_end,
    )
    db_session.commit()

    # 1. Visible booking times are intact
    assert (booking.start_time.replace(tzinfo=timezone.utc) if booking.start_time.tzinfo is None else booking.start_time) == app_start
    assert (booking.end_time.replace(tzinfo=timezone.utc) if booking.end_time.tzinfo is None else booking.end_time) == app_end

    # 2. Check allocated slot slices
    # 5:10 PM aligns down to 5:00 PM (17:00)
    # 7:50 PM ends in 7:45 - 8:00 slice (19:45)
    # Total slices: 17:00, 17:15, 17:30, 17:45, 18:00, 18:15, 18:30, 18:45, 19:00, 19:15, 19:30, 19:45 (12 slices)
    assert len(allocations) == 12
    allocated_starts = {
        (a.slot_start.replace(tzinfo=timezone.utc) if a.slot_start.tzinfo is None else a.slot_start)
        for a in allocations
    }

    expected_starts = {
        datetime(2026, 10, 17, 17, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 17, 15, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 17, 30, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 17, 45, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 18, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 18, 15, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 18, 30, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 18, 45, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 19, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 19, 15, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 19, 30, tzinfo=timezone.utc),
        datetime(2026, 10, 17, 19, 45, tzinfo=timezone.utc),
    }
    assert allocated_starts == expected_starts

    # 3. Database unique constraint uq_provider_slot_allocation prevents collision on ANY of these slots
    # Attempting to allocate slot 17:30 for the same provider must fail atomically
    colliding_allocation = BookingSlotAllocation(
        tenant_id=p3_tenant.id,
        booking_id=booking.id,
        provider_id=p3_provider.id,
        slot_start=datetime(2026, 10, 17, 17, 30, tzinfo=timezone.utc),
    )
    db_session.add(colliding_allocation)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()

    assert is_slot_allocation_conflict(exc_info.value) is True
    db_session.rollback()


# ---------------------------------------------------------------------------
# 4. Canonical Travel Ownership Principle (B owns A -> B)
# ---------------------------------------------------------------------------

def test_canonical_travel_ownership_destination_owns_inbound_leg(
    db_session, p3_tenant, p3_provider, p3_client, p3_outcall_service
):
    """Verify Canonical Ownership Rule:

    When Booking A is followed by Booking B:
    - Booking B owns the transit leg A -> B as B's inbound travel.
    - Booking A does NOT double-count transit to B in its operational window.
    - Preceding booking A's return-to-base allocations are cleanly trimmed.
    """
    calc = get_operational_window_calculator()

    # Appointment A at Bondi: 14:00 - 15:00
    a_start = datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc)
    a_end = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)

    # Window for A alone (returning to base)
    window_a_alone = calc.calculate_window(
        provider=p3_provider,
        service=p3_outcall_service,
        client_start=a_start,
        client_end=a_end,
        service_mode="out_call",
        destination="Bondi",
    )
    assert window_a_alone.onward_travel_minutes > 0.0
    assert window_a_alone.onward_destination == p3_provider.in_call_address

    # Now Booking B is scheduled after A at Manly: 17:00 - 18:00
    b_start = datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 10, 18, 18, 0, tzinfo=timezone.utc)

    # Window for B: previous_location is Bondi (location of A)
    window_b = calc.calculate_window(
        provider=p3_provider,
        service=p3_outcall_service,
        client_start=b_start,
        client_end=b_end,
        service_mode="out_call",
        destination="Manly",
        previous_location="Bondi",
    )

    # B owns the transit from Bondi -> Manly as its inbound travel leg
    assert window_b.inbound_origin == "Bondi"
    assert window_b.destination == "Manly"
    assert window_b.inbound_travel_minutes > 0.0

    # Operational start for B includes transit Bondi -> Manly + pre_buffer
    expected_b_op_start = b_start - timedelta(minutes=(window_b.pre_buffer_minutes + window_b.inbound_travel_minutes))
    assert window_b.operational_window_start == expected_b_op_start

    # Window for A when B follows: A's onward travel is 0 (delegated to B)
    window_a_with_b = calc.calculate_window(
        provider=p3_provider,
        service=p3_outcall_service,
        client_start=a_start,
        client_end=a_end,
        service_mode="out_call",
        destination="Bondi",
        next_location="Manly",
    )
    assert window_a_with_b.onward_travel_minutes == 0.0
    assert window_a_with_b.operational_window_end == a_end + timedelta(minutes=window_a_with_b.post_buffer_minutes)


# ---------------------------------------------------------------------------
# 5. Backward Compatibility: In-Call Availability
# ---------------------------------------------------------------------------

def test_incall_availability_remains_100_percent_backward_compatible(
    db_session, p3_tenant, p3_provider, p3_client, p3_outcall_service
):
    """In-call availability requests must be completely unaffected by out-call buffers or travel."""
    test_date = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)

    # Request in-call availability
    slots = get_available_slots(
        db=db_session,
        service_duration=p3_outcall_service.duration,
        provider_id=p3_provider.id,
        date=test_date,
        service_id=p3_outcall_service.id,
        service_mode="in_call",
    )

    assert len(slots) > 0
    first_slot = slots[0]
    assert "start" in first_slot
    assert "end" in first_slot
    assert isinstance(first_slot["start"], datetime)
    assert isinstance(first_slot["end"], datetime)
    # Duration matches service duration exactly
    assert (first_slot["end"] - first_slot["start"]) == timedelta(minutes=p3_outcall_service.duration)


# ---------------------------------------------------------------------------
# 6. Public API Availability Endpoints
# ---------------------------------------------------------------------------

def test_api_get_availability_outcall(client: TestClient, p3_tenant, p3_provider, p3_outcall_service):
    """GET /api/public/availability with service_mode=out_call returns operational window data."""
    params = {
        "service_id": p3_outcall_service.id,
        "provider_id": p3_provider.id,
        "date": "2026-10-20T00:00:00Z",
        "service_mode": "out_call",
        "client_suburb": "Bondi",
    }
    response = client.get("/api/public/availability", params=params, headers={"X-Tenant": p3_tenant.subdomain})
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["ok"] is True
    assert isinstance(data["data"], list)
    if data["data"]:
        first = data["data"][0]
        assert "start" in first
        assert "end" in first
        assert "operational_window" in first
        op_win = first["operational_window"]
        assert op_win["service_mode"] == "out_call"
        assert op_win["inbound_travel_minutes"] >= 0.0
        assert op_win["pre_buffer_minutes"] == p3_outcall_service.outcall_buffer_before
        assert op_win["post_buffer_minutes"] == p3_outcall_service.outcall_buffer_after


def test_api_post_availability_structured_query(client: TestClient, p3_tenant, p3_provider, p3_outcall_service):
    """POST /api/public/availability supports structured AvailabilityQuery."""
    payload = {
        "service_id": p3_outcall_service.id,
        "provider_id": p3_provider.id,
        "date": "2026-10-21T00:00:00Z",
        "service_mode": "out_call",
        "client_suburb": "Bondi",
        "service_address": "123 Ocean Street, Bondi",
    }
    response = client.post("/api/public/availability", json=payload, headers={"X-Tenant": p3_tenant.subdomain})
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["ok"] is True
    assert isinstance(data["data"], list)


def test_api_get_availability_incall_backward_compatible(client: TestClient, p3_tenant, p3_provider, p3_outcall_service):
    """GET /api/public/availability without service_mode defaults to in_call and succeeds."""
    params = {
        "service_id": p3_outcall_service.id,
        "provider_id": p3_provider.id,
        "date": "2026-10-22T00:00:00Z",
    }
    response = client.get("/api/public/availability", params=params, headers={"X-Tenant": p3_tenant.subdomain})
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["ok"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0
    first = data["data"][0]
    assert "start" in first
    assert "end" in first
