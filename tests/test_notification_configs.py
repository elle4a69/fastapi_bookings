import pytest
from fastapi import status
from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import create_access_token

@pytest.fixture
def setup_configs_data(db_session):
    # Create tenant
    tenant = Tenant(name="Tenant Configs", subdomain="tenant-conf")
    db_session.add(tenant)
    db_session.commit()

    # Create admin user
    admin = User(tenant_id=tenant.id, login="admin@conf.com", password_hash="hash", role="admin")
    db_session.add(admin)
    db_session.commit()

    token = create_access_token({"sub": str(admin.id)})

    return {
        "tenant": tenant,
        "admin": admin,
        "token": token
    }

def test_notification_template_and_reminder_rule_crud(client, setup_configs_data, db_session):
    headers = {"X-Tenant": "tenant-conf", "X-Token": setup_configs_data["token"]}

    # 1. Create a notification template
    tmpl_payload = {
        "code": "welcome_email",
        "name": "Welcome Email Template",
        "channel": "email",
        "subject": "Welcome!",
        "body": "Welcome to our service.",
        "locale": "en",
        "active": True
    }
    resp_create_t = client.post("/api/admin/notification-templates", json=tmpl_payload, headers=headers)
    assert resp_create_t.status_code == status.HTTP_200_OK
    template_id = resp_create_t.json()["data"]["id"]
    assert resp_create_t.json()["data"]["code"] == "welcome_email"

    # 2. Get templates list
    resp_list_t = client.get("/api/admin/notification-templates", headers=headers)
    assert resp_list_t.status_code == status.HTTP_200_OK
    assert len(resp_list_t.json()["data"]) == 1

    # 3. Create a reminder rule linking to that template
    rule_payload = {
        "name": "24h Before Reminder",
        "event_type": "booking.start",
        "channel": "email",
        "audience": "client",
        "timing": "before",
        "offset_minutes": 1440,
        "template_id": template_id,
        "active": True
    }
    resp_create_r = client.post("/api/admin/reminder-rules", json=rule_payload, headers=headers)
    assert resp_create_r.status_code == status.HTTP_200_OK
    rule_id = resp_create_r.json()["data"]["id"]
    assert resp_create_r.json()["data"]["name"] == "24h Before Reminder"

    # 4. Get reminder rules list
    resp_list_r = client.get("/api/admin/reminder-rules", headers=headers)
    assert resp_list_r.status_code == status.HTTP_200_OK
    assert len(resp_list_r.json()["data"]) == 1

    # 5. Update the reminder rule
    update_payload = {"offset_minutes": 120}
    resp_update_r = client.put(f"/api/admin/reminder-rules/{rule_id}", json=update_payload, headers=headers)
    assert resp_update_r.status_code == status.HTTP_200_OK
    assert resp_update_r.json()["data"]["offset_minutes"] == 120

    # 6. Delete both
    resp_delete_r = client.delete(f"/api/admin/reminder-rules/{rule_id}", headers=headers)
    assert resp_delete_r.status_code == status.HTTP_200_OK
    
    resp_delete_t = client.delete(f"/api/admin/notification-templates/{template_id}", headers=headers)
    assert resp_delete_t.status_code == status.HTTP_200_OK

    # 7. Verify deletion
    assert len(client.get("/api/admin/reminder-rules", headers=headers).json()["data"]) == 0
    assert len(client.get("/api/admin/notification-templates", headers=headers).json()["data"]) == 0
