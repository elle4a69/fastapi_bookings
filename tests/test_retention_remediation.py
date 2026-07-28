import pytest
from datetime import datetime, timedelta, timezone
from fastapi import status

from app.models.tenant import Tenant
from app.models.client import Client
from app.models.user import User
from app.models.audit import AuditLog
from app.models.notification import Notification, NotificationLog
from app.models.booking import Booking
from app.core.security import create_access_token
from app.core.state_machine import BookingStatus

@pytest.fixture
def setup_retention_data(db_session):
    tenant = Tenant(name="Tenant Retention", subdomain="tenant-ret")
    db_session.add(tenant)
    db_session.commit()

    admin = User(tenant_id=tenant.id, login="admin@ret.com", password_hash="pwd", role="admin")
    client_obj = Client(
        tenant_id=tenant.id,
        name="John Doe",
        email="john@doe.com",
        phone="1234567890",
        address_line1="123 Main St",
        active=True
    )
    db_session.add_all([admin, client_obj])
    db_session.commit()

    token = create_access_token({"sub": str(admin.id)})

    return {
        "tenant": tenant,
        "admin": admin,
        "client": client_obj,
        "token": token
    }

def test_client_anonymization(client, setup_retention_data, db_session):
    headers = {"X-Tenant": "tenant-ret", "X-Token": setup_retention_data["token"]}
    client_id = setup_retention_data["client"].id

    # Execute anonymization
    response = client.post(f"/api/admin/system/clients/{client_id}/anonymize", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    # Refresh from database and verify anonymized fields
    db_session.expire_all()
    updated_client = db_session.query(Client).filter(Client.id == client_id).first()
    assert updated_client.name == "Anonymized Client"
    assert "anonymized-" in updated_client.email
    assert updated_client.phone == "0000000000"
    assert updated_client.address_line1 is None
    assert updated_client.active is False
    assert updated_client.deleted_at is not None

def test_historic_cleanup(client, setup_retention_data, db_session):
    headers = {"X-Tenant": "tenant-ret", "X-Token": setup_retention_data["token"]}
    tenant_id = setup_retention_data["tenant"].id

    # Create one provider and one service to hook a historic booking
    from app.models.provider import Provider
    from app.models.service import Service
    prov = Provider(tenant_id=tenant_id, name="Dr. A")
    srv = Service(tenant_id=tenant_id, name="Therapy", duration=60)
    db_session.add_all([prov, srv])
    db_session.commit()

    # Create old records (older than 30 days)
    old_date = datetime.now(timezone.utc) - timedelta(days=40)
    
    old_audit = AuditLog(tenant_id=tenant_id, action="DELETE", timestamp=old_date)
    old_noti = Notification(tenant_id=tenant_id, type="email", status="sent", created_at=old_date)
    
    # We must add these first to get IDs
    db_session.add_all([old_audit, old_noti])
    db_session.commit()

    old_log = NotificationLog(
        notification_id=old_noti.id,
        status="sent",
        channel="email",
        created_at=old_date
    )
    
    old_booking = Booking(
        tenant_id=tenant_id,
        client_id=setup_retention_data["client"].id,
        provider_id=prov.id,
        service_id=srv.id,
        start_time=old_date,
        end_time=old_date + timedelta(hours=1),
        status=BookingStatus.CANCELLED
    )
    db_session.add_all([old_log, old_booking])
    db_session.commit()

    # Create recent records (e.g. 5 days old)
    recent_date = datetime.now(timezone.utc) - timedelta(days=5)
    recent_audit = AuditLog(tenant_id=tenant_id, action="DELETE", timestamp=recent_date)
    db_session.add(recent_audit)
    db_session.commit()

    old_audit_id = old_audit.id
    recent_audit_id = recent_audit.id

    # Run cleanup for records older than 15 days
    response = client.post("/api/admin/system/cleanup?days=15", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["deleted_audit_logs"] == 1
    assert data["deleted_cancelled_bookings"] == 1

    # Verify recent audit log still exists
    assert db_session.query(AuditLog).filter(AuditLog.id == recent_audit_id).first() is not None
    # Verify old audit log is deleted
    assert db_session.query(AuditLog).filter(AuditLog.id == old_audit_id).first() is None
