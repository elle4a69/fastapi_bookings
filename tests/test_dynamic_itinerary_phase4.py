"""Comprehensive Test Suite for Phase 4: Dynamic Itinerary Recalculation & Conflict Sentinel.

Tests:
1. Backward expansion: Booking A (Suburb A) cancelled -> Booking B (Suburb B) inbound travel
   automatically expands backwards from 1 hr (A->B) to 2 hrs (Base->B); slot allocations expand from 5:00 PM to 4:00 PM.
2. Billing snapshot invariant: Booking B's chargeable_travel_fee ($65.00) remains completely unchanged after Booking A is cancelled.
3. Conflict detection: If required departure time is earlier than provider shift start (4:00 PM vs 4:30 PM),
   conflict is cleanly detected and flagged on the booking and in the recalculation result.
4. Intermediate insertion: Booking C inserted between A and B -> recalculates legs A->C and C->B.
5. Administrative Conflict Sentinel Endpoints: GET /api/admin/itinerary/conflicts and POST /api/admin/itinerary/recalculate.
6. Conflict resolution: Extending provider shift hours or rescheduling clears the conflict flag and synchronizes slots.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.core.state_machine import BookingStatus
from app.models.booking import Booking, ServiceMode
from app.models.booking_slot_allocation import BookingSlotAllocation
from app.models.client import Client
from app.models.provider import Provider
from app.models.schedule import ProviderWorkDay
from app.models.service import Service
from app.models.tenant import Tenant, TravelChargeOrigin
from app.models.user import User
from app.schemas.itinerary import ItineraryRecalculationResult
from app.services.booking.itinerary_service import (
    get_provider_itinerary_conflicts,
    recalculate_provider_itinerary,
)
from app.services.booking.slot_allocation_service import (
    create_allocations_for_booking,
)
from app.services.routing.geocoding import clear_test_locations, register_test_location


# Coordinates calibrated for Haversine speed (50 km/h) & winding factor (1.25):
# straight_km * 1.5 = duration_minutes.
# Suburb A: 40 km from Base -> 60.0 mins (1.0 hr)
# Suburb B: 80 km from Base -> 120.0 mins (2.0 hrs); 40 km from Suburb A -> 60.0 mins (1.0 hr)
# Suburb C: 60 km from Base -> 90.0 mins; 20 km from Suburb A -> 30.0 mins; 20 km to Suburb B -> 30.0 mins
LAT_A = 0.359728
LAT_B = 0.719456
LAT_C = 0.539592


@pytest.fixture(autouse=True)
def clean_test_locations_registry():
    """Register deterministic test coordinates before each test."""
    clear_test_locations()
    register_test_location("Base", (0.0, 0.0))
    register_test_location("Suburb A", (LAT_A, 0.0))
    register_test_location("Suburb B", (LAT_B, 0.0))
    register_test_location("Suburb C", (LAT_C, 0.0))
    yield
    clear_test_locations()


@pytest.fixture
def p4_tenant(db_session) -> Tenant:
    """Create test tenant."""
    tenant = Tenant(
        name="Phase 4 Itinerary Tenant",
        subdomain="p4itin",
        allow_in_call=True,
        allow_out_call=True,
        travel_charge_origin=TravelChargeOrigin.ALWAYS_FROM_BASE.value,
        address="Base",
        latitude=0.0,
        longitude=0.0,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def p4_owner(db_session, p4_tenant) -> User:
    """Create admin/owner user for tenant."""
    owner = User(
        tenant_id=p4_tenant.id,
        login="p4_owner",
        password_hash="fake_hash",
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)
    return owner


@pytest.fixture
def p4_admin_headers(p4_tenant, p4_owner) -> dict:
    """Admin request headers with auth token and tenant subdomain."""
    token = create_access_token({"sub": str(p4_owner.id)})
    return {
        "X-Tenant": p4_tenant.subdomain,
        "X-Token": token,
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture
def p4_provider(db_session, p4_tenant) -> Provider:
    """Create mobile provider with default base location."""
    provider = Provider(
        tenant_id=p4_tenant.id,
        name="Morgan Itinerary Specialist",
        allow_in_call=True,
        allow_out_call=True,
        in_call_address="Base",
        out_call_radius_km=150.0,
        base_outcall_surcharge=Decimal("25.00"),
        per_km_fee=Decimal("1.50"),
        turnaround_buffer_mins=15,
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


@pytest.fixture
def p4_client(db_session, p4_tenant) -> Client:
    """Create test client."""
    client = Client(
        tenant_id=p4_tenant.id,
        name="David Miller",
        email="david.miller@example.com",
        phone="+61400333444",
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


@pytest.fixture
def p4_service(db_session, p4_tenant) -> Service:
    """Create 60-min out-call service without additional manual buffers (buffer_before=0, buffer_after=0)."""
    service = Service(
        tenant_id=p4_tenant.id,
        name="Executive On-Site Service",
        duration=60,
        price=Decimal("100.00"),
        outcall_price=Decimal("150.00"),
        buffer_before=0,
        buffer_after=0,
        outcall_buffer_before=0,
        outcall_buffer_after=0,
        allow_in_call=True,
        allow_out_call=True,
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def set_provider_shift(db_session, tenant_id: int, provider_id: int, weekday: int, start_time: str, end_time: str):
    """Helper to set or update provider workday shift hours."""
    wd = (
        db_session.query(ProviderWorkDay)
        .filter(
            ProviderWorkDay.tenant_id == tenant_id,
            ProviderWorkDay.provider_id == provider_id,
            ProviderWorkDay.weekday == weekday,
        )
        .first()
    )
    if not wd:
        wd = ProviderWorkDay(
            tenant_id=tenant_id,
            provider_id=provider_id,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            is_working=True,
        )
        db_session.add(wd)
    else:
        wd.start_time = start_time
        wd.end_time = end_time
        wd.is_working = True
    db_session.commit()
    return wd


# ---------------------------------------------------------------------------
# 1. Test Backward Expansion & 2. Billing Snapshot Invariant
# ---------------------------------------------------------------------------

def test_backward_expansion_and_billing_snapshot_invariant(
    client: TestClient,
    db_session,
    p4_tenant,
    p4_provider,
    p4_client,
    p4_service,
    p4_admin_headers,
):
    """Test Requirement 1 & 2:

    - Booking A at Suburb A (14:00 - 15:00) precedes Booking B at Suburb B (18:00 - 19:00).
    - When A exists, inbound transit (A -> B) is 60 minutes (1 hr).
      Operational window starts at 17:00 (5:00 PM). Slots start at 17:00.
    - Booking A is cancelled -> Booking B inbound transit expands to Base -> B (120 mins = 2 hrs).
      Operational window expands backwards to 16:00 (4:00 PM). Slot allocations expand backwards to 16:00.
    - Billing Snapshot Invariant: Booking B's chargeable_travel_fee ($65.00) remains completely unchanged.
    """
    target_date = date(2026, 11, 10)  # Tuesday, weekday = 1
    # Provider shift covers 09:00 to 21:00 UTC
    set_provider_shift(db_session, p4_tenant.id, p4_provider.id, target_date.weekday(), "09:00", "21:00")

    # Booking A: 14:00 to 15:00 at Suburb A
    a_start = datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)
    a_end = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
    booking_a = Booking(
        tenant_id=p4_tenant.id,
        client_id=p4_client.id,
        provider_id=p4_provider.id,
        service_id=p4_service.id,
        start_time=a_start,
        end_time=a_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Suburb A",
        client_suburb="Suburb A",
        chargeable_travel_distance_km=50.0,
        chargeable_travel_fee=Decimal("40.00"),
    )
    db_session.add(booking_a)

    # Booking B: 18:00 to 19:00 at Suburb B, with fixed snapshot fee of $65.00
    b_start = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 11, 10, 19, 0, tzinfo=timezone.utc)
    booking_b = Booking(
        tenant_id=p4_tenant.id,
        client_id=p4_client.id,
        provider_id=p4_provider.id,
        service_id=p4_service.id,
        start_time=b_start,
        end_time=b_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Suburb B",
        client_suburb="Suburb B",
        chargeable_travel_distance_km=100.0,
        chargeable_travel_fee=Decimal("65.00"),
    )
    db_session.add(booking_b)
    db_session.commit()

    # Initial recalculation with both bookings active
    res_initial = recalculate_provider_itinerary(db_session, p4_provider.id, target_date)
    assert res_initial.success is True
    assert res_initial.has_conflicts is False
    assert res_initial.bookings_evaluated == 2

    # Verify Booking B initial slot allocations start at 17:00 (5:00 PM)
    db_session.refresh(booking_b)
    allocs_b_initial = (
        db_session.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == booking_b.id)
        .order_by(BookingSlotAllocation.slot_start.asc())
        .all()
    )
    initial_starts = [a.slot_start.replace(tzinfo=timezone.utc) if a.slot_start.tzinfo is None else a.slot_start for a in allocs_b_initial]
    assert initial_starts[0] == datetime(2026, 11, 10, 17, 0, tzinfo=timezone.utc), "B initially starts at 17:00 (1 hr travel from A)"

    # CANCEL Booking A via the router endpoint (PATCH /bookings/{id}/cancel)
    resp = client.patch(
        f"/api/admin/bookings/{booking_a.id}/cancel",
        headers=p4_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()

    # Verify Booking A allocations are released
    allocs_a = (
        db_session.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == booking_a.id)
        .all()
    )
    assert len(allocs_a) == 0, "Booking A slot allocations should be released"

    # Refresh Booking B from DB
    db_session.refresh(booking_b)

    # 1. Verify Backward Expansion: Slot allocations for B expanded from 17:00 backwards to 16:00 (4:00 PM)
    allocs_b_expanded = (
        db_session.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == booking_b.id)
        .order_by(BookingSlotAllocation.slot_start.asc())
        .all()
    )
    expanded_starts = [
        a.slot_start.replace(tzinfo=timezone.utc) if a.slot_start.tzinfo is None else a.slot_start
        for a in allocs_b_expanded
    ]

    earliest_slot = expanded_starts[0]
    expected_expansion_start = datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc)  # 4:00 PM
    assert earliest_slot == expected_expansion_start, (
        f"Operational slots must expand backwards from 17:00 to 16:00! Got {earliest_slot}"
    )

    # Slices between 16:00 and 17:00 must now be present
    assert datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc) in expanded_starts
    assert datetime(2026, 11, 10, 16, 15, tzinfo=timezone.utc) in expanded_starts
    assert datetime(2026, 11, 10, 16, 30, tzinfo=timezone.utc) in expanded_starts
    assert datetime(2026, 11, 10, 16, 45, tzinfo=timezone.utc) in expanded_starts
    assert datetime(2026, 11, 10, 17, 0, tzinfo=timezone.utc) in expanded_starts

    # 2. Verify BILLING SNAPSHOT INVARIANT:
    # Client travel fee ($65.00) remains completely unchanged!
    assert booking_b.chargeable_travel_fee == Decimal("65.00"), "Billing Snapshot Invariant violated! Fee changed."
    assert booking_b.chargeable_travel_distance_km == 100.0, "Chargeable distance snapshot modified!"


# ---------------------------------------------------------------------------
# 3. Test Conflict Detection (Departure Earlier than Shift Start)
# ---------------------------------------------------------------------------

def test_conflict_detection_when_departure_precedes_shift_start(
    db_session,
    p4_tenant,
    p4_provider,
    p4_client,
    p4_service,
):
    """Test Requirement 3:

    - Provider shift starts at 16:30 (4:30 PM).
    - Booking at Suburb B requires departure at 16:00 (4:00 PM) to travel 2 hrs to reach B by 18:00.
    - Feasibility fails: 16:00 < 16:30.
    - Conflict is cleanly detected and flagged on the booking and returned in ItineraryRecalculationResult.
    """
    target_date = date(2026, 11, 11)  # Wednesday, weekday = 2

    # Provider shift starts late at 16:30 UTC
    set_provider_shift(db_session, p4_tenant.id, p4_provider.id, target_date.weekday(), "16:30", "22:00")

    # Booking at Suburb B at 18:00 (requires 2 hrs transit from Base -> 16:00 departure)
    b_start = datetime(2026, 11, 11, 18, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 11, 11, 19, 0, tzinfo=timezone.utc)
    booking = Booking(
        tenant_id=p4_tenant.id,
        client_id=p4_client.id,
        provider_id=p4_provider.id,
        service_id=p4_service.id,
        start_time=b_start,
        end_time=b_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Suburb B",
        client_suburb="Suburb B",
        chargeable_travel_fee=Decimal("65.00"),
    )
    db_session.add(booking)
    db_session.commit()

    # Recalculate
    result: ItineraryRecalculationResult = recalculate_provider_itinerary(
        db_session, p4_provider.id, target_date
    )

    # Verify conflict detected in result
    assert result.has_conflicts is True
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.booking_id == booking.id
    assert "requires departure at 16:00" in conflict.reason
    assert "shift starts at 16:30" in conflict.reason

    # Verify conflict flagged directly on Booking model
    db_session.refresh(booking)
    assert booking.has_itinerary_conflict is True
    assert booking.itinerary_conflict is not None
    assert "requires departure at 16:00" in booking.itinerary_conflict
    assert "shift starts at 16:30" in booking.itinerary_conflict
    assert booking.itinerary_conflict_reason == booking.itinerary_conflict


# ---------------------------------------------------------------------------
# 4. Test Intermediate Insertion (Booking C inserted between A and B)
# ---------------------------------------------------------------------------

def test_intermediate_insertion_recalculates_waypoint_legs(
    db_session,
    p4_tenant,
    p4_provider,
    p4_client,
    p4_service,
):
    """Test Requirement 4:

    - Booking A at Suburb A (10:00 - 11:00)
    - Booking B at Suburb B (18:00 - 19:00)
    - Initially B's inbound leg is from Suburb A.
    - Insert Booking C at Suburb C (13:00 - 14:00).
    - Recalculate: Legs are A -> C and C -> B.
    """
    target_date = date(2026, 11, 12)  # Thursday
    set_provider_shift(db_session, p4_tenant.id, p4_provider.id, target_date.weekday(), "08:00", "22:00")

    # Booking A: 10:00 - 11:00 at Suburb A
    a_start = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
    a_end = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)
    booking_a = Booking(
        tenant_id=p4_tenant.id,
        client_id=p4_client.id,
        provider_id=p4_provider.id,
        service_id=p4_service.id,
        start_time=a_start,
        end_time=a_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Suburb A",
        client_suburb="Suburb A",
        chargeable_travel_fee=Decimal("40.00"),
    )
    db_session.add(booking_a)

    # Booking B: 18:00 - 19:00 at Suburb B
    b_start = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 11, 12, 19, 0, tzinfo=timezone.utc)
    booking_b = Booking(
        tenant_id=p4_tenant.id,
        client_id=p4_client.id,
        provider_id=p4_provider.id,
        service_id=p4_service.id,
        start_time=b_start,
        end_time=b_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Suburb B",
        client_suburb="Suburb B",
        chargeable_travel_fee=Decimal("65.00"),
    )
    db_session.add(booking_b)
    db_session.commit()

    # Recalculate A and B
    res_ab = recalculate_provider_itinerary(db_session, p4_provider.id, target_date)
    assert res_ab.bookings_evaluated == 2
    b_inbound_initial = next(
        leg for leg in res_ab.itinerary_legs if leg.booking_id == booking_b.id and leg.leg_type == "inbound_travel"
    )
    assert b_inbound_initial.origin == "Suburb A"
    assert b_inbound_initial.duration_minutes == 60.0

    # Insert Booking C between A and B at Suburb C: 13:00 - 14:00
    c_start = datetime(2026, 11, 12, 13, 0, tzinfo=timezone.utc)
    c_end = datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc)
    booking_c = Booking(
        tenant_id=p4_tenant.id,
        client_id=p4_client.id,
        provider_id=p4_provider.id,
        service_id=p4_service.id,
        start_time=c_start,
        end_time=c_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Suburb C",
        client_suburb="Suburb C",
        chargeable_travel_fee=Decimal("50.00"),
    )
    db_session.add(booking_c)
    db_session.commit()

    # Recalculate after intermediate insertion
    res_acb = recalculate_provider_itinerary(db_session, p4_provider.id, target_date)
    assert res_acb.bookings_evaluated == 3
    assert res_acb.has_conflicts is False

    # Check legs:
    # C's inbound leg must originate at Suburb A (A -> C, 30 mins)
    c_inbound = next(
        leg for leg in res_acb.itinerary_legs if leg.booking_id == booking_c.id and leg.leg_type == "inbound_travel"
    )
    assert c_inbound.origin == "Suburb A"
    assert c_inbound.destination == "Suburb C"
    assert c_inbound.duration_minutes == 30.0

    # B's inbound leg must now originate at Suburb C (C -> B, 30 mins)!
    b_inbound_updated = next(
        leg for leg in res_acb.itinerary_legs if leg.booking_id == booking_b.id and leg.leg_type == "inbound_travel"
    )
    assert b_inbound_updated.origin == "Suburb C"
    assert b_inbound_updated.destination == "Suburb B"
    assert b_inbound_updated.duration_minutes == 30.0


# ---------------------------------------------------------------------------
# 5. Test Conflict Sentinel API & Conflict Resolution
# ---------------------------------------------------------------------------

def test_conflict_sentinel_api_and_resolution_flow(
    client: TestClient,
    db_session,
    p4_tenant,
    p4_provider,
    p4_client,
    p4_service,
    p4_admin_headers,
):
    """Test Conflict Sentinel Admin API endpoints:

    - GET /api/admin/itinerary/conflicts returns flagged conflicts.
    - POST /api/admin/itinerary/recalculate re-runs recalculation.
    - Adjusting shift clears the conflict flag atomically.
    """
    target_date = date(2026, 11, 13)
    # Shift starts at 17:00 (too late for 16:00 departure)
    set_provider_shift(db_session, p4_tenant.id, p4_provider.id, target_date.weekday(), "17:00", "22:00")

    b_start = datetime(2026, 11, 13, 18, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 11, 13, 19, 0, tzinfo=timezone.utc)
    booking = Booking(
        tenant_id=p4_tenant.id,
        client_id=p4_client.id,
        provider_id=p4_provider.id,
        service_id=p4_service.id,
        start_time=b_start,
        end_time=b_end,
        status=BookingStatus.CONFIRMED,
        service_mode=ServiceMode.OUT_CALL.value,
        service_address="Suburb B",
        client_suburb="Suburb B",
        chargeable_travel_fee=Decimal("65.00"),
    )
    db_session.add(booking)
    db_session.commit()

    # Recalculate to generate initial conflict
    recalculate_provider_itinerary(db_session, p4_provider.id, target_date)

    # 1. Query GET /api/admin/itinerary/conflicts
    resp_conflicts = client.get(
        "/api/admin/itinerary/conflicts",
        params={"provider_id": p4_provider.id},
        headers=p4_admin_headers,
    )
    assert resp_conflicts.status_code == 200, resp_conflicts.text
    data = resp_conflicts.json()
    assert data["ok"] is True
    assert data["total"] >= 1
    found = any(c["booking_id"] == booking.id for c in data["conflicts"])
    assert found is True

    # 2. Resolve conflict by extending provider shift to start earlier (15:00)
    set_provider_shift(db_session, p4_tenant.id, p4_provider.id, target_date.weekday(), "15:00", "22:00")

    # 3. Call POST /api/admin/itinerary/recalculate
    recalc_payload = {
        "provider_id": p4_provider.id,
        "target_date": "2026-11-13",
    }
    resp_recalc = client.post(
        "/api/admin/itinerary/recalculate",
        json=recalc_payload,
        headers=p4_admin_headers,
    )
    assert resp_recalc.status_code == 200, resp_recalc.text
    recalc_data = resp_recalc.json()
    assert recalc_data["success"] is True
    assert recalc_data["has_conflicts"] is False

    # 4. Verify booking has conflict cleared in DB
    db_session.refresh(booking)
    assert booking.has_itinerary_conflict is False
    assert booking.itinerary_conflict is None

    # 5. Query GET conflicts again - total should now be 0
    resp_conflicts_cleared = client.get(
        "/api/admin/itinerary/conflicts",
        params={"provider_id": p4_provider.id, "date_from": "2026-11-13", "date_to": "2026-11-13"},
        headers=p4_admin_headers,
    )
    assert resp_conflicts_cleared.status_code == 200
    cleared_data = resp_conflicts_cleared.json()
    assert cleared_data["total"] == 0
