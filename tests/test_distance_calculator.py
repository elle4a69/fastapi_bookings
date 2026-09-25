"""Tests for DistanceCalculator service and out-call fee calculation."""

import pytest
import httpx

from app.services.routing.distance_calculator import DistanceCalculator


def test_haversine_distance_calculation():
    """Test Haversine distance formula with known coordinates."""
    # Sydney CBD to Bondi Beach (~7 km straight line, ~8.7 km with 1.25 road winding factor)
    origin_lat, origin_lng = -33.8688, 151.2093
    dest_lat, dest_lng = -33.8915, 151.2767

    res = DistanceCalculator.haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)

    assert isinstance(res["distance_km"], float)
    assert isinstance(res["duration_minutes"], float)
    assert 6.0 < res["distance_km"] < 12.0
    assert res["duration_minutes"] > 0


@pytest.mark.asyncio
async def test_calculate_distance_osrm_success():
    """Test OSRM routing success."""
    origin_lat, origin_lng = 40.7128, -74.0060
    dest_lat, dest_lng = 40.7589, -73.9851

    def handler(request: httpx.Request) -> httpx.Response:
        # Check coordinate order: longitude,latitude;longitude,latitude
        expected_coord_str = f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        assert expected_coord_str in request.url.path
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "distance": 6250.5,  # meters -> 6.25 km
                        "duration": 750.0,   # seconds -> 12.5 minutes
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        calc = DistanceCalculator(base_url="https://router.project-osrm.org", client=client)
        result = await calc.calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng)

        assert result["distance_km"] == 6.25
        assert result["duration_minutes"] == 12.5


@pytest.mark.asyncio
async def test_calculate_distance_osrm_failure_fallback():
    """Test fallback to Haversine when OSRM returns 500."""
    origin_lat, origin_lng = 40.7128, -74.0060
    dest_lat, dest_lng = 40.7589, -73.9851

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="OSRM service unavailable")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        calc = DistanceCalculator(client=client)
        result = await calc.calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng)

        # Should seamlessly fall back to Haversine
        assert isinstance(result["distance_km"], float)
        assert isinstance(result["duration_minutes"], float)
        assert result["distance_km"] > 0
        assert result["duration_minutes"] > 0


@pytest.mark.asyncio
async def test_calculate_distance_osrm_timeout_fallback():
    """Test fallback to Haversine when OSRM request times out."""
    origin_lat, origin_lng = 40.7128, -74.0060
    dest_lat, dest_lng = 40.7589, -73.9851

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("OSRM timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        calc = DistanceCalculator(client=client)
        result = await calc.calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng)

        assert isinstance(result["distance_km"], float)
        assert result["distance_km"] > 0


def test_calculate_outcall_fee_within_radius():
    """Test out-call fee calculation within allowed radius."""
    res = DistanceCalculator.calculate_outcall_fee(
        distance_km=12.5,
        base_surcharge=20.0,
        per_km_fee=1.5,
        max_radius_km=25.0,
    )

    assert res["allowed"] is True
    # 20.0 + (12.5 * 1.5) = 20.0 + 18.75 = 38.75
    assert res["fee"] == 38.75


def test_calculate_outcall_fee_exceeds_radius():
    """Test out-call fee calculation when distance exceeds maximum radius."""
    res = DistanceCalculator.calculate_outcall_fee(
        distance_km=30.0,
        base_surcharge=20.0,
        per_km_fee=1.5,
        max_radius_km=25.0,
    )

    assert res["allowed"] is False
    assert res["reason"] == "Location exceeds maximum out-call radius"
    assert res["fee"] == 0.0


def test_calculate_outcall_fee_exact_boundary():
    """Test boundary where distance exactly equals max_radius_km."""
    res = DistanceCalculator.calculate_outcall_fee(
        distance_km=25.0,
        base_surcharge=15.0,
        per_km_fee=2.0,
        max_radius_km=25.0,
    )

    assert res["allowed"] is True
    # 15.0 + (25.0 * 2.0) = 65.0
    assert res["fee"] == 65.0


def test_distance_calculator_zero_distance():
    """Test distance calculation when origin equals destination (zero distance)."""
    lat, lng = -37.8136, 144.9631  # Melbourne
    res = DistanceCalculator.haversine_distance(lat, lng, lat, lng)
    assert res["distance_km"] == 0.0
    assert res["duration_minutes"] == 0.0

    fee = DistanceCalculator.calculate_outcall_fee(
        distance_km=0.0,
        base_surcharge=25.0,
        per_km_fee=2.0,
        max_radius_km=30.0,
    )
    assert fee["allowed"] is True
    assert fee["fee"] == 25.0


def test_distance_calculator_negative_coordinates():
    """Test Haversine distance with all-negative coordinates (Southern & Western hemisphere)."""
    # Santiago (-33.4489, -70.6693) to Buenos Aires (-34.6037, -58.3816)
    res = DistanceCalculator.haversine_distance(-33.4489, -70.6693, -34.6037, -58.3816)
    assert isinstance(res["distance_km"], float)
    assert 1200.0 < res["distance_km"] < 1600.0
    assert res["duration_minutes"] > 0


@pytest.mark.asyncio
async def test_calculate_distance_osrm_noroute_fallback():
    """Test fallback to Haversine when OSRM returns non-Ok code (e.g. NoRoute across oceans)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "NoRoute", "routes": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        calc = DistanceCalculator(client=client)
        res = await calc.calculate_distance(-33.8688, 151.2093, 35.6762, 139.6503)
        assert res["distance_km"] > 0
        assert res["duration_minutes"] > 0


@pytest.mark.asyncio
async def test_distance_calculator_context_manager():
    """Test DistanceCalculator async context manager entry and exit."""
    async with DistanceCalculator() as calc:
        assert calc is not None


def test_calculate_outcall_fee_boundary_epsilon():
    """Test radius boundary with tiny delta above and below."""
    # Just slightly above max_radius
    res_above = DistanceCalculator.calculate_outcall_fee(
        distance_km=25.01,
        base_surcharge=10.0,
        per_km_fee=1.0,
        max_radius_km=25.0,
    )
    assert res_above["allowed"] is False
    assert res_above["fee"] == 0.0

    # Just slightly below max_radius
    res_below = DistanceCalculator.calculate_outcall_fee(
        distance_km=24.99,
        base_surcharge=10.0,
        per_km_fee=1.0,
        max_radius_km=25.0,
    )
    assert res_below["allowed"] is True
    assert res_below["fee"] == 34.99

