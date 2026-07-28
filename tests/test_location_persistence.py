import pytest
from fastapi import status
from app.models import Tenant, User, Provider, Service, Category, Product, Location
from app.core.security import create_access_token

@pytest.fixture
def setup_data(db_session):
    # 1. Setup tenant and admin
    tenant = Tenant(name="Persistence Tenant", subdomain="persistence")
    db_session.add(tenant)
    db_session.flush()

    admin = User(tenant_id=tenant.id, login="admin@persistence.com", password_hash="hash", role="admin")
    db_session.add(admin)
    db_session.flush()

    # 2. Setup related entities
    provider = Provider(tenant_id=tenant.id, name="Test Provider", active=True)
    service = Service(tenant_id=tenant.id, name="Test Service", duration=30, active=True)
    category = Category(tenant_id=tenant.id, name="Test Category", active=True)
    product = Product(tenant_id=tenant.id, name="Test Product", price=15.50, active=True)
    
    db_session.add_all([provider, service, category, product])
    db_session.flush()

    token = create_access_token({"sub": str(admin.id)})

    return {
        "tenant": tenant,
        "admin": admin,
        "token": token,
        "provider": provider,
        "service": service,
        "category": category,
        "product": product,
    }

def test_location_image_and_relationships_persistence(client, setup_data, db_session):
    headers = {
        "X-Tenant": setup_data["tenant"].subdomain,
        "X-Token": setup_data["token"]
    }

    # 1. POST - Create location
    create_payload = {
        "name": "Persisted Location",
        "address": "456 Persistence Ave",
        "timezone": "America/Los_Angeles",
        "image": "http://example.com/location.png",
        "provider_ids": [setup_data["provider"].id],
        "service_ids": [setup_data["service"].id],
        "category_ids": [setup_data["category"].id],
        "product_ids": [setup_data["product"].id]
    }

    response = client.post("/api/admin/locations", json=create_payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    
    data = response.json()["data"]
    location_id = data["id"]
    
    # Assert properties in response
    assert data["name"] == "Persisted Location"
    assert data["image"] == "http://example.com/location.png"
    assert data["provider_ids"] == [setup_data["provider"].id]
    assert data["service_ids"] == [setup_data["service"].id]
    assert data["category_ids"] == [setup_data["category"].id]
    assert data["product_ids"] == [setup_data["product"].id]

    # 2. GET - Retrieve location
    get_response = client.get(f"/api/admin/locations/{location_id}", headers=headers)
    assert get_response.status_code == status.HTTP_200_OK
    get_data = get_response.json()["data"]
    assert get_data["image"] == "http://example.com/location.png"
    assert get_data["provider_ids"] == [setup_data["provider"].id]
    assert get_data["service_ids"] == [setup_data["service"].id]
    assert get_data["category_ids"] == [setup_data["category"].id]
    assert get_data["product_ids"] == [setup_data["product"].id]

    # 3. PUT - Update location (change image and modify some relationships)
    update_payload = {
        "name": "Updated Location Name",
        "image": "http://example.com/new-location.png",
        "provider_ids": [], # Clear providers
        "service_ids": [setup_data["service"].id], # Keep service
        "category_ids": [], # Clear categories
        "product_ids": [] # Clear products
    }

    put_response = client.put(f"/api/admin/locations/{location_id}", json=update_payload, headers=headers)
    assert put_response.status_code == status.HTTP_200_OK, put_response.text
    put_data = put_response.json()["data"]
    assert put_data["name"] == "Updated Location Name"
    assert put_data["image"] == "http://example.com/new-location.png"
    assert put_data["provider_ids"] == []
    assert put_data["service_ids"] == [setup_data["service"].id]
    assert put_data["category_ids"] == []
    assert put_data["product_ids"] == []

    # 4. GET - Retrieve location again to verify DB persistence
    get_response_2 = client.get(f"/api/admin/locations/{location_id}", headers=headers)
    assert get_response_2.status_code == status.HTTP_200_OK
    get_data_2 = get_response_2.json()["data"]
    assert get_data_2["image"] == "http://example.com/new-location.png"
    assert get_data_2["provider_ids"] == []
    assert get_data_2["service_ids"] == [setup_data["service"].id]
    assert get_data_2["category_ids"] == []
    assert get_data_2["product_ids"] == []
