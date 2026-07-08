import pytest
from datetime import datetime, timezone, date
from fastapi import status
from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import create_access_token

def test_predecessor_record_keeping_fields(client, db_session):
    """Verify that the new record-keeping fields for Provider, Service, and CalendarNote function correctly."""
    # 1. Setup tenant and admin user
    tenant = Tenant(name="Test Tenant", subdomain="test-tenant", created_at=datetime.now(timezone.utc))
    db_session.add(tenant)
    db_session.commit()

    p_hash = "fake_password_hash_value"
    admin_user = User(tenant_id=tenant.id, login="admin_user", password_hash=p_hash, role="owner", created_at=datetime.now(timezone.utc))
    db_session.add(admin_user)
    db_session.commit()

    token = create_access_token({"sub": str(admin_user.id)})
    headers = {
        "X-Tenant": "test-tenant",
        "X-Token": token
    }

    # 2. Test Provider creation with new fields
    provider_payload = {
        "name": "Dr. John Doe",
        "email": "john.doe@example.com",
        "phone": "555-0199",
        "active": True,
        "is_visible": False,       # New field
        "capacity": 3,            # New field
        "color": "#ff0000",       # New field
        "description": "Expert physician"  # New field
    }
    resp_prov = client.post("/api/admin/providers", json=provider_payload, headers=headers)
    assert resp_prov.status_code == status.HTTP_200_OK, resp_prov.text
    prov_data = resp_prov.json()["data"]
    assert prov_data["is_visible"] is False
    assert prov_data["capacity"] == 3
    assert prov_data["color"] == "#ff0000"
    assert prov_data["description"] == "Expert physician"

    # Test updating provider new fields
    prov_update = {
        "capacity": 5,
        "color": "#00ff00"
    }
    resp_prov_up = client.put(f"/api/admin/providers/{prov_data['id']}", json=prov_update, headers=headers)
    assert resp_prov_up.status_code == status.HTTP_200_OK
    assert resp_prov_up.json()["data"]["capacity"] == 5
    assert resp_prov_up.json()["data"]["color"] == "#00ff00"

    # 3. Test Service creation with new fields
    service_payload = {
        "name": "General Checkup",
        "description": "Routine checkup",
        "duration": 30,
        "price": 120.0,
        "active": True,
        "is_visible": True,           # New field
        "deposit_amount": 25.0,       # New field
        "tax_rate_id": None,          # New field
        "min_group_size": 2,          # New field
        "max_group_size": 4           # New field
    }
    resp_serv = client.post("/api/admin/services", json=service_payload, headers=headers)
    assert resp_serv.status_code == status.HTTP_200_OK, resp_serv.text
    serv_data = resp_serv.json()["data"]
    assert serv_data["is_visible"] is True
    assert serv_data["deposit_amount"] == 25.0
    assert serv_data["min_group_size"] == 2
    assert serv_data["max_group_size"] == 4

    # Test updating service new fields
    serv_update = {
        "deposit_amount": 50.0,
        "max_group_size": 10
    }
    resp_serv_up = client.put(f"/api/admin/services/{serv_data['id']}", json=serv_update, headers=headers)
    assert resp_serv_up.status_code == status.HTTP_200_OK
    assert resp_serv_up.json()["data"]["deposit_amount"] == 50.0
    assert resp_serv_up.json()["data"]["max_group_size"] == 10

    # 4. Test Calendar Note creation with new fields
    note_payload = {
        "provider_id": prov_data["id"],
        "date": "2026-07-15",
        "start_time": "09:00",
        "end_time": "12:00",
        "text": "Out of office - Dentist appointment",
        "note_type": "leave",          # New field
        "is_time_blocked": True        # New field
    }
    resp_note = client.post("/api/admin/calendar-notes", json=note_payload, headers=headers)
    assert resp_note.status_code == status.HTTP_201_CREATED, resp_note.text
    note_data = resp_note.json()["data"]
    assert note_data["note_type"] == "leave"
    assert note_data["is_time_blocked"] is True

    # Test updating calendar note new fields
    note_update = {
        "note_type": "personal",
        "is_time_blocked": False
    }
    resp_note_up = client.put(f"/api/admin/calendar-notes/{note_data['id']}", json=note_update, headers=headers)
    assert resp_note_up.status_code == status.HTTP_200_OK
    assert resp_note_up.json()["data"]["note_type"] == "personal"
    assert resp_note_up.json()["data"]["is_time_blocked"] is False
