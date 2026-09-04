import pytest
from datetime import datetime, timezone, timedelta
from app.models.tenant import Tenant
from app.models.user import User
from app.models.provider import Provider
from app.models.client import Client
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.location import Location, LocationProvider, LocationService
from app.models.booking import Booking
from app.core.security import create_access_token

def test_bookings_performance_and_pagination(db_session, client):
    # 1. Seed Tenant
    tenant = Tenant(name="Test Tenant", subdomain="test-subdomain")
    db_session.add(tenant)
    db_session.commit()

    # 2. Seed Admin User
    admin = User(
        tenant_id=tenant.id,
        login="admin@test.com",
        role="admin",
        password_hash="mock-hash"
    )
    db_session.add(admin)
    db_session.commit()

    # 3. Seed Location
    location = Location(tenant_id=tenant.id, name="Main Clinic", active=True)
    db_session.add(location)
    db_session.commit()

    # 4. Seed Provider
    provider = Provider(tenant_id=tenant.id, name="Dr. John", active=True)
    db_session.add(provider)
    db_session.commit()

    # 5. Seed Service
    service = Service(
        tenant_id=tenant.id,
        name="Consultation",
        duration=30,
        price=100.0,
        active=True
    )
    db_session.add(service)
    db_session.commit()

    # 6. Seed Client
    test_client = Client(tenant_id=tenant.id, name="Jane Smith", email="jane@test.com", active=True)
    db_session.add(test_client)
    db_session.commit()

    # 7. Seed Relationships (LocationProvider, LocationService, ServiceProvider)
    # These will test whether selectin loading correctly isolates queries
    lp = LocationProvider(tenant_id=tenant.id, location_id=location.id, provider_id=provider.id)
    ls = LocationService(tenant_id=tenant.id, location_id=location.id, service_id=service.id)
    sp = ServiceProvider(tenant_id=tenant.id, service_id=service.id, provider_id=provider.id)
    db_session.add_all([lp, ls, sp])
    db_session.commit()

    # 8. Seed multiple bookings
    now = datetime.now(timezone.utc)
    bookings = []
    for i in range(15):
        b = Booking(
            tenant_id=tenant.id,
            client_id=test_client.id,
            provider_id=provider.id,
            service_id=service.id,
            location_id=location.id,
            start_time=now + timedelta(days=i),
            end_time=now + timedelta(days=i, minutes=30),
            status="PENDING"
        )
        bookings.append(b)
    db_session.add_all(bookings)
    db_session.commit()

    # 9. Request the bookings list via endpoint with pagination
    headers = {
        "X-Token": create_access_token({"sub": str(admin.id)}),
        "X-Tenant": "test-subdomain"
    }
    
    # Request first page of 5 items
    response = client.get("/api/admin/bookings?page=1&page_size=5", headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    
    # Assert correct pagination meta
    assert res_data["ok"] is True
    assert len(res_data["data"]) == 5
    assert res_data["meta"]["page"] == 1
    assert res_data["meta"]["page_size"] == 5
    assert res_data["meta"]["total"] == 15

    # Assert correct direct relationship data loaded
    first_booking = res_data["data"][0]
    assert first_booking["client"]["name"] == "Jane Smith"
    assert first_booking["provider"]["name"] == "Dr. John"
    assert first_booking["service"]["name"] == "Consultation"
    assert first_booking["location"]["name"] == "Main Clinic"

    # 10. Request second page
    response_p2 = client.get("/api/admin/bookings?page=2&page_size=5", headers=headers)
    assert response_p2.status_code == 200
    res_data_p2 = response_p2.json()
    assert len(res_data_p2["data"]) == 5
    assert res_data_p2["meta"]["page"] == 2
