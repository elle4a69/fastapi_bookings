"""Tests for Umbrella Directory and Geo-Radius Map Marketplace (/directory)."""

import pytest
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.location import Location
from app.models.service import Service
from app.models.category import Category, ServiceCategory


@pytest.fixture
def setup_directory_data(db_session: Session):
    """Seed distinct geo-located tenants for testing radius calculations and triage."""
    # Tenant 1: Sydney CBD (Origin)
    tenant_syd = Tenant(
        name="Sydney Wellness Clinic",
        subdomain="syd-wellness",
        address="100 George St, Sydney NSW 2000",
        latitude=-33.8688,
        longitude=151.2093,
    )
    # Tenant 2: North Sydney (~3.4 km from CBD)
    tenant_north = Tenant(
        name="North Sydney Specialist Center",
        subdomain="north-syd-spec",
        address="200 Pacific Hwy, North Sydney NSW 2060",
        latitude=-33.8390,
        longitude=151.2070,
    )
    # Tenant 3: Parramatta (~20 km from CBD)
    tenant_parra = Tenant(
        name="Parramatta Health Hub",
        subdomain="parra-health",
        address="50 Church St, Parramatta NSW 2150",
        latitude=-33.8150,
        longitude=151.0011,
    )
    # Tenant 4: Melbourne CBD (~713 km from Sydney CBD)
    tenant_melb = Tenant(
        name="Melbourne Elite Care",
        subdomain="melb-elite",
        address="150 Collins St, Melbourne VIC 3000",
        latitude=-37.8136,
        longitude=144.9631,
    )

    db_session.add_all([tenant_syd, tenant_north, tenant_parra, tenant_melb])
    db_session.commit()
    for t in [tenant_syd, tenant_north, tenant_parra, tenant_melb]:
        db_session.refresh(t)

    # Locations
    loc_syd = Location(tenant_id=tenant_syd.id, name="Sydney CBD Main Center", address=tenant_syd.address, active=True)
    loc_north = Location(tenant_id=tenant_north.id, name="North Sydney Suite", address=tenant_north.address, active=True)
    loc_parra = Location(tenant_id=tenant_parra.id, name="Parramatta Branch", address=tenant_parra.address, active=True)
    loc_melb = Location(tenant_id=tenant_melb.id, name="Melbourne Collins St Center", address=tenant_melb.address, active=True)

    db_session.add_all([loc_syd, loc_north, loc_parra, loc_melb])
    db_session.commit()

    # Category
    cat_consult = Category(tenant_id=tenant_syd.id, name="Consultations", active=True)
    cat_triage = Category(tenant_id=tenant_north.id, name="Triage", active=True)
    db_session.add_all([cat_consult, cat_triage])
    db_session.commit()

    # Services
    svc1 = Service(tenant_id=tenant_syd.id, name="Standard Consultation", duration=60, price=120.0, active=True)
    svc2 = Service(tenant_id=tenant_north.id, name="Rapid Triage Assessment", duration=15, price=50.0, active=True)
    svc3 = Service(tenant_id=tenant_parra.id, name="Holistic Wellness Review", duration=45, price=95.0, active=True)
    svc4 = Service(tenant_id=tenant_melb.id, name="Elite Executive Consultation", duration=60, price=200.0, active=True)

    db_session.add_all([svc1, svc2, svc3, svc4])
    db_session.commit()

    db_session.add(ServiceCategory(tenant_id=tenant_syd.id, service_id=svc1.id, category_id=cat_consult.id))
    db_session.add(ServiceCategory(tenant_id=tenant_north.id, service_id=svc2.id, category_id=cat_triage.id))
    db_session.commit()

    return {
        "tenant_syd": tenant_syd,
        "tenant_north": tenant_north,
        "tenant_parra": tenant_parra,
        "tenant_melb": tenant_melb,
        "cat_consult": cat_consult,
    }


def test_directory_search_with_lat_lng_and_radius_filtering(client, setup_directory_data):
    """Test searching directory with GPS coordinates and radius filtering."""
    # Center: Sydney CBD (-33.8688, 151.2093), Radius: 10 km
    # Expect: Sydney CBD (0 km) and North Sydney (~3.4 km). Parramatta (~20km) and Melb (~713km) excluded.
    response = client.get(
        "/api/public/directory/search",
        params={"lat": -33.8688, "lng": 151.2093, "radius_km": 10.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["radius_km"] == 10.0

    subdomains = [t["subdomain"] for t in data["tenants"]]
    assert "syd-wellness" in subdomains
    assert "north-syd-spec" in subdomains
    assert "parra-health" not in subdomains
    assert "melb-elite" not in subdomains


def test_directory_search_by_postcode(client, setup_directory_data):
    """Test searching directory by entering an Australian postcode."""
    # Search for Sydney CBD postcode 2000 with 30 km radius (accounting for 1.25 road winding factor)
    # Expect: Sydney CBD (~0km), North Sydney (~3.4km), and Parramatta (~25km)
    response = client.get(
        "/api/public/directory/search",
        params={"query": "2000", "radius_km": 30.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["search_center"] is not None
    assert "2000" in data["search_center"]["label"]

    subdomains = [t["subdomain"] for t in data["tenants"]]
    assert "syd-wellness" in subdomains
    assert "north-syd-spec" in subdomains
    assert "parra-health" in subdomains
    assert "melb-elite" not in subdomains


def test_directory_search_sorting_by_distance(client, setup_directory_data):
    """Test that search results are sorted ascending by distance."""
    response = client.get(
        "/api/public/directory/search",
        params={"lat": -33.8688, "lng": 151.2093, "radius_km": 50.0},
    )
    assert response.status_code == 200
    data = response.json()
    tenants = data["tenants"]
    assert len(tenants) >= 3

    # Distances must be non-decreasing
    distances = [t["distance_km"] for t in tenants]
    assert distances == sorted(distances)

    # First should be Sydney CBD (closest)
    assert tenants[0]["subdomain"] == "syd-wellness"
    assert tenants[0]["distance_km"] <= 1.0


def test_directory_featured(client, setup_directory_data):
    """Test /api/public/directory/featured endpoint."""
    response = client.get("/api/public/directory/featured")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["featured_tenants"]) >= 1
    assert "categories" in data


def test_directory_bot_triage_consultation_sydney(client, setup_directory_data):
    """Test AI bot concierge triage for 'Need standard consultation in Sydney under 15km'."""
    payload = {
        "query": "Need standard consultation in Sydney under 15km",
    }
    response = client.post("/api/public/directory/bot/triage", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["reply"]) > 20
    assert len(data["matched_tenants"]) >= 1

    top_tenant = data["matched_tenants"][0]
    assert top_tenant["subdomain"] == "syd-wellness"
    assert "booking_url" in top_tenant
    assert "/book?tenant=syd-wellness" in top_tenant["booking_url"]
