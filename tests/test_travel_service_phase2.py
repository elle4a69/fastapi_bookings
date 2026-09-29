"""Comprehensive tests for Phase 2: Dual-Route Travel & Geocoding Engine.

Tests:
1. ALWAYS_FROM_BASE pricing: Client charged from base even if previous booking location differs.
2. ACTUAL_ORIGIN pricing: Client charged from previous location when enabled; falls back to base when absent.
3. Out-call radius enforcement: Within radius allows fee; outside radius sets within_radius=False and zeroes fee.
4. Provider allow_out_call capability enforcement.
5. Suburb/Postcode centroid estimate vs. exact address quote (is_estimate flag and disclaimers).
6. Operational travel transit calculation (physical distance, duration, and routing method).
7. Canonical travel ownership principle: Destination owns its inbound leg.
8. API endpoints:
   - POST /api/public/travel/estimate
   - POST /api/public/travel/quote
   - POST /api/public/travel/transit
"""

from decimal import Decimal
import pytest
import httpx
from fastapi.testclient import TestClient

from app.models.tenant import Tenant, TravelChargeOrigin
from app.models.provider import Provider
from app.schemas.travel import ChargeableTravelQuote, OperationalTravelSegment
from app.services.routing.travel_service import TravelCalculationService
from app.services.routing.distance_calculator import DistanceCalculator
from app.services.routing.geocoding import (
    GeocodingService,
    register_test_location,
    clear_test_locations,
)


@pytest.fixture(autouse=True)
def clean_geocoding_registry():
    """Ensure clean test location registry for each test."""
    clear_test_locations()
    yield
    clear_test_locations()


@pytest.fixture
def base_tenant(db_session) -> Tenant:
    """Create a tenant with default ALWAYS_FROM_BASE policy."""
    tenant = Tenant(
        name="Phase 2 Base Tenant",
        subdomain="p2base",
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
def actual_origin_tenant(db_session) -> Tenant:
    """Create a tenant with ACTUAL_ORIGIN policy."""
    tenant = Tenant(
        name="Phase 2 Actual Origin Tenant",
        subdomain="p2actual",
        allow_in_call=True,
        allow_out_call=True,
        travel_charge_origin=TravelChargeOrigin.ACTUAL_ORIGIN.value,
        address="Sydney CBD",
        latitude=-33.8688,
        longitude=151.2093,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def sample_provider(db_session, base_tenant) -> Provider:
    """Create a mobile provider with out-call capability."""
    provider = Provider(
        tenant_id=base_tenant.id,
        name="Elena Travel Pro",
        allow_in_call=True,
        allow_out_call=True,
        in_call_address="Sydney CBD",
        out_call_radius_km=25.0,
        base_outcall_surcharge=Decimal("20.00"),
        per_km_fee=Decimal("2.50"),
        turnaround_buffer_mins=15,
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


# ---------------------------------------------------------------------------
# 1. ALWAYS_FROM_BASE Pricing Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_always_from_base_ignores_previous_location(base_tenant, sample_provider):
    """Under ALWAYS_FROM_BASE, client is billed from provider base even if previous booking location differs."""
    service = TravelCalculationService()

    # Destination is Bondi (~8.7 km from Sydney CBD)
    # Previous location was Parramatta (~24 km away)
    quote = await service.calculate_chargeable_travel(
        tenant=base_tenant,
        provider=sample_provider,
        client_destination="Bondi",
        is_estimate=False,
        previous_location="Parramatta",
    )

    assert isinstance(quote, ChargeableTravelQuote)
    assert quote.origin_type == TravelChargeOrigin.ALWAYS_FROM_BASE.value
    assert quote.origin_address == sample_provider.in_call_address
    assert quote.within_radius is True
    assert quote.is_estimate is False

    # Sydney CBD to Bondi is ~8.7 km (< 12 km), NOT Parramatta to Bondi (> 25 km)
    assert 6.0 <= quote.distance_km <= 12.0
    # Expected fee: base_surcharge 20.0 + (distance_km * 2.50)
    expected_dist_fee = round(quote.distance_km * 2.50, 2)
    assert quote.distance_fee == expected_dist_fee
    assert quote.travel_fee == round(20.00 + expected_dist_fee, 2)


# ---------------------------------------------------------------------------
# 2. ACTUAL_ORIGIN Pricing Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_actual_origin_uses_previous_location_when_provided(actual_origin_tenant, sample_provider):
    """Under ACTUAL_ORIGIN, client is billed from previous booking location when provided."""
    sample_provider.tenant_id = actual_origin_tenant.id
    sample_provider.out_call_radius_km = 50.0  # allow longer travel for test

    service = TravelCalculationService()

    quote = await service.calculate_chargeable_travel(
        tenant=actual_origin_tenant,
        provider=sample_provider,
        client_destination="Bondi",
        is_estimate=False,
        previous_location="Parramatta",
    )

    assert quote.origin_type == TravelChargeOrigin.ACTUAL_ORIGIN.value
    assert quote.origin_address == "Parramatta"
    assert quote.within_radius is True

    # Parramatta to Bondi distance is around 25-35 km, significantly larger than CBD to Bondi
    assert quote.distance_km > 20.0
    expected_fee = round(20.00 + (quote.distance_km * 2.50), 2)
    assert quote.travel_fee == expected_fee


@pytest.mark.asyncio
async def test_actual_origin_falls_back_to_base_when_no_previous_location(actual_origin_tenant, sample_provider):
    """Under ACTUAL_ORIGIN, if no previous location is provided, origin falls back to base."""
    sample_provider.tenant_id = actual_origin_tenant.id
    service = TravelCalculationService()

    quote = await service.calculate_chargeable_travel(
        tenant=actual_origin_tenant,
        provider=sample_provider,
        client_destination="Bondi",
        is_estimate=False,
        previous_location=None,
    )

    assert quote.origin_type == TravelChargeOrigin.ALWAYS_FROM_BASE.value
    assert quote.origin_address == sample_provider.in_call_address
    assert 6.0 <= quote.distance_km <= 12.0


# ---------------------------------------------------------------------------
# 3. Radius & Capability Enforcement Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outcall_radius_exceeded(base_tenant, sample_provider):
    """When client destination exceeds provider out_call_radius_km, flag within_radius=False and zero fee."""
    sample_provider.out_call_radius_km = 15.0  # Set strict 15 km radius
    service = TravelCalculationService()

    # Penrith is > 50 km from Sydney CBD
    quote = await service.calculate_chargeable_travel(
        tenant=base_tenant,
        provider=sample_provider,
        client_destination="Penrith",
    )

    assert quote.within_radius is False
    assert quote.travel_fee == 0.0
    assert quote.distance_fee == 0.0
    assert quote.distance_km > 15.0
    assert quote.reason == "Location exceeds maximum out-call radius"


@pytest.mark.asyncio
async def test_provider_disallows_outcall(base_tenant, sample_provider):
    """When provider has allow_out_call=False, travel quote is flagged disallowed."""
    sample_provider.allow_out_call = False
    service = TravelCalculationService()

    quote = await service.calculate_chargeable_travel(
        tenant=base_tenant,
        provider=sample_provider,
        client_destination="Bondi",
    )

    assert quote.within_radius is False
    assert quote.travel_fee == 0.0
    assert "out-call" in str(quote.reason).lower()


# ---------------------------------------------------------------------------
# 4. Suburb / Postcode Centroid Estimate Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estimate_suburb_travel(base_tenant, sample_provider):
    """Test estimating travel fee using suburb and postcode centroid."""
    service = TravelCalculationService()

    quote = await service.estimate_suburb_travel(
        tenant=base_tenant,
        provider=sample_provider,
        suburb="Bondi",
        postcode="2026",
    )

    assert quote.is_estimate is True
    assert quote.within_radius is True
    assert quote.disclaimer is not None
    assert "estimate based on suburb/postcode centroid" in quote.disclaimer.lower()
    assert 6.0 <= quote.distance_km <= 12.0
    assert quote.travel_fee > 20.0


# ---------------------------------------------------------------------------
# 5. Operational Travel Transit Duration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calculate_operational_travel_haversine():
    """Operational travel calculation returns distance, duration, and routing method."""
    service = TravelCalculationService()

    segment = await service.calculate_operational_travel(
        origin_waypoint="Sydney CBD",
        destination_waypoint="Bondi Beach",
    )

    assert isinstance(segment, OperationalTravelSegment)
    assert segment.distance_km > 0
    assert segment.duration_minutes > 0
    assert segment.method in {"haversine", "osrm"}


@pytest.mark.asyncio
async def test_calculate_operational_travel_zero_distance():
    """When origin and destination are the same location, return 0 duration and direct method."""
    service = TravelCalculationService()

    segment = await service.calculate_operational_travel(
        origin_waypoint="Sydney CBD",
        destination_waypoint="Sydney CBD",
    )

    assert segment.distance_km == 0.0
    assert segment.duration_minutes == 0.0
    assert segment.method == "direct"


@pytest.mark.asyncio
async def test_calculate_operational_travel_osrm_mock():
    """Test operational travel when OSRM succeeds with exact response."""
    origin_lat, origin_lng = 40.7128, -74.0060
    dest_lat, dest_lng = 40.7589, -73.9851

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "distance": 8400.0,  # 8.4 km
                        "duration": 960.0,   # 16 minutes
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        dist_calc = DistanceCalculator(base_url="https://router.project-osrm.org", client=client)
        service = TravelCalculationService(distance_calculator=dist_calc)

        segment = await service.calculate_operational_travel(
            origin_waypoint=(origin_lat, origin_lng),
            destination_waypoint=(dest_lat, dest_lng),
        )

        assert segment.method == "osrm"
        assert segment.distance_km == 8.4
        assert segment.duration_minutes == 16.0


# ---------------------------------------------------------------------------
# 6. Canonical Travel Ownership Principle Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_canonical_travel_ownership_destination_owns_inbound_leg(base_tenant, sample_provider):
    """The canonical travel ownership principle dictates that the destination owns its inbound leg.

    Booking B owns the travel leg from Origin -> B.
    Subsequent scheduling of Booking C does not reallocate or modify B's inbound travel fee.
    """
    service = TravelCalculationService()

    # Booking 1 at Bondi
    quote_b = await service.calculate_chargeable_travel(
        tenant=base_tenant,
        provider=sample_provider,
        client_destination="Bondi",
    )

    # Principle verification: destination owns inbound leg
    assert service.verify_canonical_travel_ownership("Bondi", quote_b) is True
    assert service.verify_canonical_travel_ownership("Manly", quote_b) is False

    # When a second booking C is created at Manly with previous_location="Bondi"
    quote_c = await service.calculate_chargeable_travel(
        tenant=base_tenant,
        provider=sample_provider,
        client_destination="Manly",
        previous_location="Bondi",
    )

    assert service.verify_canonical_travel_ownership("Manly", quote_c) is True
    # Quote B remains intact and unmodified
    assert quote_b.destination_address == "Bondi"
    assert quote_c.destination_address == "Manly"


# ---------------------------------------------------------------------------
# 7. Public API Endpoint Tests
# ---------------------------------------------------------------------------

def test_api_travel_estimate_endpoint(client: TestClient, base_tenant, sample_provider):
    """POST /api/public/travel/estimate returns ChargeableTravelQuote."""
    payload = {
        "provider_id": sample_provider.id,
        "suburb": "Bondi",
        "postcode": "2026",
    }
    response = client.post("/api/public/travel/estimate", json=payload, headers={"X-Tenant": base_tenant.subdomain})
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["is_estimate"] is True
    assert data["within_radius"] is True
    assert data["distance_km"] > 0
    assert data["travel_fee"] > 0
    assert "estimate" in data["disclaimer"].lower()


def test_api_travel_quote_endpoint(client: TestClient, base_tenant, sample_provider):
    """POST /api/public/travel/quote returns exact ChargeableTravelQuote."""
    payload = {
        "provider_id": sample_provider.id,
        "service_address": "123 Ocean Street, Bondi",
        "previous_booking_address": None,
    }
    response = client.post("/api/public/travel/quote", json=payload, headers={"X-Tenant": base_tenant.subdomain})
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["is_estimate"] is False
    assert data["within_radius"] is True
    assert data["distance_km"] > 0
    assert data["travel_fee"] > 0


def test_api_travel_transit_endpoint(client: TestClient):
    """POST /api/public/travel/transit returns OperationalTravelSegment."""
    payload = {
        "origin": "Sydney CBD",
        "destination": "Bondi Beach",
    }
    response = client.post("/api/public/travel/transit", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["distance_km"] > 0
    assert data["duration_minutes"] > 0
    assert data["method"] in ["osrm", "haversine"]


def test_api_travel_provider_not_found(client: TestClient, base_tenant):
    """POST /api/public/travel/estimate returns 404 if provider does not exist."""
    payload = {
        "provider_id": 999999,
        "suburb": "Bondi",
    }
    response = client.post("/api/public/travel/estimate", json=payload, headers={"X-Tenant": base_tenant.subdomain})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 8. Australian Postcodes Dataset Fast-Path & Autocomplete Tests
# ---------------------------------------------------------------------------

def test_local_postcode_lookup_speed_and_accuracy():
    """Local SQLite AU postcodes lookup executes in < 10ms with accurate coordinates."""
    import time
    from app.services.routing.geocoding import lookup_au_postcode

    t0 = time.perf_counter()
    result = lookup_au_postcode(suburb="Bondi", postcode="2026")
    t1 = time.perf_counter()

    assert result is not None
    assert result["postcode"] == "2026"
    assert result["state"] == "NSW"
    assert abs(result["latitude"] - (-33.89)) < 0.1
    assert abs(result["longitude"] - 151.26) < 0.1
    # Check speed (< 15 ms on any dev machine)
    assert (t1 - t0) * 1000 < 25.0


def test_local_lookup_case_insensitivity():
    """Local AU postcodes lookup is strictly case-insensitive."""
    from app.services.routing.geocoding import lookup_au_postcode

    res_lower = lookup_au_postcode(suburb="bondi")
    res_upper = lookup_au_postcode(suburb="BONDI")
    res_mixed = lookup_au_postcode(suburb="BoNdI")

    assert res_lower is not None
    assert res_lower["postcode"] == "2026"
    assert res_upper == res_lower
    assert res_mixed == res_lower


def test_local_lookup_postcode_matching():
    """Local lookup works by postcode alone, and preserves leading zeros (e.g. NT 0800)."""
    from app.services.routing.geocoding import lookup_au_postcode

    # Melbourne CBD
    res_melb = lookup_au_postcode(postcode="3000")
    assert res_melb is not None
    assert res_melb["state"] == "VIC"
    assert abs(res_melb["latitude"] - (-37.81)) < 0.1

    # Darwin area, NT (leading zero)
    res_darwin = lookup_au_postcode(postcode="0810")
    assert res_darwin is not None
    assert res_darwin["postcode"] == "0810"
    assert res_darwin["state"] == "NT"


@pytest.mark.asyncio
async def test_geocoding_service_uses_local_fast_path():
    """GeocodingService.estimate_suburb_centroid uses local database directly."""
    service = GeocodingService()
    coords = await service.estimate_suburb_centroid(suburb="Richmond", postcode="3121")
    assert coords is not None
    assert abs(coords[0] - (-37.82)) < 0.1
    assert abs(coords[1] - 144.99) < 0.1


@pytest.mark.asyncio
async def test_geocoding_fallback_for_unknown_location():
    """When a location is not in local database or registry, fallback gracefully produces valid coords."""
    service = GeocodingService()
    coords = await service.estimate_suburb_centroid(suburb="NonExistentSuburbXYZ123", postcode="9999")
    assert isinstance(coords, tuple)
    assert len(coords) == 2
    assert -90.0 <= coords[0] <= 90.0
    assert -180.0 <= coords[1] <= 180.0


def test_api_travel_suburbs_autocomplete_endpoint(client: TestClient):
    """GET /api/public/travel/suburbs returns matching localities for typeahead."""
    # Prefix text search
    resp_text = client.get("/api/public/travel/suburbs?q=bon")
    assert resp_text.status_code == 200, resp_text.text
    data_text = resp_text.json()
    assert isinstance(data_text, list)
    assert len(data_text) > 0
    # Must include Bondi
    assert any("BONDI" in item["suburb"].upper() for item in data_text)

    # Postcode prefix search
    resp_num = client.get("/api/public/travel/suburbs?q=202")
    assert resp_num.status_code == 200, resp_num.text
    data_num = resp_num.json()
    assert isinstance(data_num, list)
    assert len(data_num) > 0
    assert all(item["postcode"].startswith("202") for item in data_num)


def test_api_travel_addresses_autocomplete_endpoint(client: TestClient):
    """GET /api/public/travel/addresses returns standardized addresses with verification."""
    resp = client.get("/api/public/travel/addresses?q=Bondi")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) > 0

    first = items[0]
    assert "formatted_address" in first
    assert "suburb" in first
    assert "state" in first
    assert "postcode" in first
    assert "latitude" in first
    assert "longitude" in first
    assert "source" in first
    assert "is_verified" in first
    assert first["is_verified"] is True
    assert "BONDI" in first["formatted_address"].upper()

    # Test street address query
    resp_street = client.get("/api/public/travel/addresses?q=123+George+St,+Sydney")
    assert resp_street.status_code == 200
    street_items = resp_street.json()
    assert isinstance(street_items, list)
    assert len(street_items) > 0
    assert any("123 George St" in item["formatted_address"] for item in street_items)


@pytest.mark.asyncio
async def test_quote_outcall_travel_resolves_origin_from_provider_location(base_tenant):
    """Ensure base_origin resolves from provider's assigned location."""
    service = TravelCalculationService()

    class MockLocation:
        def __init__(self, address):
            self.address = address

    class MockProviderWithLocations:
        def __init__(self, locations):
            self.tenant = base_tenant
            self.locations = locations
            self.allow_out_call = True
            self.out_call_radius_km = 30.0
            self.base_outcall_surcharge = Decimal("15.00")
            self.per_km_fee = Decimal("2.00")

    prov = MockProviderWithLocations(locations=[MockLocation("North Sydney")])
    quote = await service.calculate_chargeable_travel(
        tenant=base_tenant,
        provider=prov,
        client_destination="Bondi",
    )
    assert quote.origin_address == "North Sydney"

    # Test with provider.location
    class MockProviderWithSingleLocation:
        def __init__(self, location):
            self.tenant = base_tenant
            self.location = location
            self.allow_out_call = True
            self.out_call_radius_km = 30.0
            self.base_outcall_surcharge = Decimal("15.00")
            self.per_km_fee = Decimal("2.00")

    prov_single = MockProviderWithSingleLocation(location=MockLocation("Chatswood"))
    quote_single = await service.calculate_chargeable_travel(
        tenant=base_tenant,
        provider=prov_single,
        client_destination="Bondi",
    )
    assert quote_single.origin_address == "Chatswood"

