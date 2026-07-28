import pytest
from datetime import datetime, timezone
from fastapi import status
from app.models.tenant import Tenant
from app.models.location import Location
from app.models.provider import Provider
from app.models.service import Service
from app.models.category import Category
from app.models.user import User
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.core.security import create_access_token

@pytest.fixture
def setup_tenants(db_session):
    # Create two tenants
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a")
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    # Create admin user for Tenant A
    admin_a = User(tenant_id=tenant_a.id, login="admin@a.com", password_hash="hash", role="admin")
    db_session.add(admin_a)
    db_session.commit()

    # Create tokens
    token_admin_a = create_access_token({"sub": str(admin_a.id)})
    
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "token_a": token_admin_a
    }

def test_partitioning_audit_and_notification(client, setup_tenants, db_session):
    headers = {"X-Tenant": "tenant-a", "X-Token": setup_tenants["token_a"]}

    # Create Audit logs and notifications for both tenants
    audit_a = AuditLog(tenant_id=setup_tenants["tenant_a"].id, action="CREATE", target_type="service", details="created service")
    audit_b = AuditLog(tenant_id=setup_tenants["tenant_b"].id, action="CREATE", target_type="service", details="created service b")
    
    notification_a = Notification(tenant_id=setup_tenants["tenant_a"].id, type="email", status="pending", recipient_email="a@example.com")
    notification_b = Notification(tenant_id=setup_tenants["tenant_b"].id, type="email", status="pending", recipient_email="b@example.com")

    db_session.add_all([audit_a, audit_b, notification_a, notification_b])
    db_session.commit()

    # Query Tenant A audit logs -> should only see audit_a
    response_audit = client.get("/api/admin/audit-log", headers=headers)
    assert response_audit.status_code == status.HTTP_200_OK, response_audit.text
    audits = response_audit.json()["data"]
    assert len(audits) == 1
    assert audits[0]["id"] == audit_a.id

    # Query Tenant A notifications -> should only see notification_a
    response_noti = client.get("/api/admin/notifications", headers=headers)
    assert response_noti.status_code == status.HTTP_200_OK, response_noti.text
    notis = response_noti.json()["data"]
    assert len(notis) == 1
    assert notis[0]["id"] == notification_a.id

def test_location_relationships_crud(client, setup_tenants, db_session):
    headers = {"X-Tenant": "tenant-a", "X-Token": setup_tenants["token_a"]}

    # Create location, provider, service, category for Tenant A
    loc = Location(tenant_id=setup_tenants["tenant_a"].id, name="Downtown Office")
    prov = Provider(tenant_id=setup_tenants["tenant_a"].id, name="Dr. A")
    srv = Service(tenant_id=setup_tenants["tenant_a"].id, name="Therapy", duration=60)
    cat = Category(tenant_id=setup_tenants["tenant_a"].id, name="Wellness")
    db_session.add_all([loc, prov, srv, cat])
    db_session.commit()

    # 1. Link provider to location
    resp_link_p = client.post(f"/api/admin/locations/{loc.id}/providers/{prov.id}", headers=headers)
    assert resp_link_p.status_code == status.HTTP_201_CREATED

    # 2. Link service to location
    resp_link_s = client.post(f"/api/admin/locations/{loc.id}/services/{srv.id}", headers=headers)
    assert resp_link_s.status_code == status.HTTP_201_CREATED

    # 3. Link category to location
    resp_link_c = client.post(f"/api/admin/locations/{loc.id}/categories/{cat.id}", headers=headers)
    assert resp_link_c.status_code == status.HTTP_201_CREATED

    # 4. List and check links
    resp_list_p = client.get(f"/api/admin/locations/{loc.id}/providers", headers=headers)
    assert resp_list_p.status_code == 200
    assert len(resp_list_p.json()) == 1
    assert resp_list_p.json()[0]["name"] == "Dr. A"

    resp_list_s = client.get(f"/api/admin/locations/{loc.id}/services", headers=headers)
    assert len(resp_list_s.json()) == 1

    resp_list_c = client.get(f"/api/admin/locations/{loc.id}/categories", headers=headers)
    assert len(resp_list_c.json()) == 1

    # 5. Delete links
    client.delete(f"/api/admin/locations/{loc.id}/providers/{prov.id}", headers=headers)
    client.delete(f"/api/admin/locations/{loc.id}/services/{srv.id}", headers=headers)
    client.delete(f"/api/admin/locations/{loc.id}/categories/{cat.id}", headers=headers)

    # 6. Verify empty lists
    assert len(client.get(f"/api/admin/locations/{loc.id}/providers", headers=headers).json()) == 0
