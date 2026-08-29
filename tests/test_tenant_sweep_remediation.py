"""Tenant Boundary Sweep Remediation Tests (Work Package G).

Verifies multi-tenant boundary enforcement across:
1. Calendar Notes (TEN-004)
2. GDPR Consents (TEN-005)
3. Public Timeline & Schedules (TEN-006)
4. System Diagnostics Counts (TEN-007)
5. Device Registration (TEN-008)
"""

from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.models.client import Client
from app.models.provider import Provider
from app.models.service import Service
from app.models.resource import Resource
from app.models.booking import Booking
from app.models.waitlist import WaitlistEntry, WaitlistStatus
from app.models.outbox import OutboxEvent
from app.models.calendar_note import CalendarNote
from app.models.general_systems import GdprConsent
from app.models.notification import DeviceToken
from app.models.service_provider import ServiceProvider
from app.models.schedule import ProviderWorkDay, ProviderSpecialDay


@pytest.fixture
def two_tenants(db_session: Session):
    """Seed two distinct tenants with administrators, providers, services, and clients."""
    # Tenant A
    tenant_a = Tenant(
        name="Alpha Tenant",
        subdomain="alpha",
        email="admin@alpha.test",
    )
    db_session.add(tenant_a)
    db_session.flush()

    user_a = User(
        tenant_id=tenant_a.id,
        login="admin_alpha",
        password_hash=get_password_hash("AlphaPass123!"),
        role="admin",
    )
    db_session.add(user_a)
    db_session.flush()

    client_a = Client(
        tenant_id=tenant_a.id,
        name="Alice Alpha",
        email="alice@alpha.test",
        phone="+61400000001",
    )
    db_session.add(client_a)

    provider_a = Provider(
        tenant_id=tenant_a.id,
        name="Provider Alpha 1",
        email="prov1@alpha.test",
        active=True,
    )
    db_session.add(provider_a)
    db_session.flush()

    service_a1 = Service(
        tenant_id=tenant_a.id,
        name="Alpha Service 1",
        duration=30,
        price=100.0,
        active=True,
    )
    service_a2 = Service(
        tenant_id=tenant_a.id,
        name="Alpha Service 2",
        duration=60,
        price=200.0,
        active=True,
    )
    db_session.add_all([service_a1, service_a2])
    db_session.flush()

    sp_a1 = ServiceProvider(
        tenant_id=tenant_a.id,
        service_id=service_a1.id,
        provider_id=provider_a.id,
    )
    sp_a2 = ServiceProvider(
        tenant_id=tenant_a.id,
        service_id=service_a2.id,
        provider_id=provider_a.id,
    )
    db_session.add_all([sp_a1, sp_a2])

    workday_a = ProviderWorkDay(
        tenant_id=tenant_a.id,
        provider_id=provider_a.id,
        weekday=date.today().weekday(),
        start_time="09:00",
        end_time="17:00",
        is_working=True,
    )
    db_session.add(workday_a)

    # Tenant B
    tenant_b = Tenant(
        name="Beta Tenant",
        subdomain="beta",
        email="admin@beta.test",
    )
    db_session.add(tenant_b)
    db_session.flush()

    user_b = User(
        tenant_id=tenant_b.id,
        login="admin_beta",
        password_hash=get_password_hash("BetaPass123!"),
        role="admin",
    )
    db_session.add(user_b)
    db_session.flush()

    client_b = Client(
        tenant_id=tenant_b.id,
        name="Bob Beta",
        email="bob@beta.test",
        phone="+61400000002",
    )
    db_session.add(client_b)

    provider_b = Provider(
        tenant_id=tenant_b.id,
        name="Provider Beta 1",
        email="prov1@beta.test",
        active=True,
    )
    db_session.add(provider_b)
    db_session.flush()

    service_b1 = Service(
        tenant_id=tenant_b.id,
        name="Beta Service 1",
        duration=45,
        price=150.0,
        active=True,
    )
    db_session.add(service_b1)
    db_session.flush()

    sp_b1 = ServiceProvider(
        tenant_id=tenant_b.id,
        service_id=service_b1.id,
        provider_id=provider_b.id,
    )
    db_session.add(sp_b1)

    workday_b = ProviderWorkDay(
        tenant_id=tenant_b.id,
        provider_id=provider_b.id,
        weekday=date.today().weekday(),
        start_time="10:00",
        end_time="18:00",
        is_working=True,
    )
    db_session.add(workday_b)

    db_session.commit()

    token_a = create_access_token({"sub": str(user_a.id), "role": "admin"})
    token_b = create_access_token({"sub": str(user_b.id), "role": "admin"})

    return {
        "tenant_a": tenant_a,
        "user_a": user_a,
        "client_a": client_a,
        "provider_a": provider_a,
        "service_a1": service_a1,
        "service_a2": service_a2,
        "headers_a": {"X-Tenant": "alpha", "X-Token": token_a},
        "tenant_b": tenant_b,
        "user_b": user_b,
        "client_b": client_b,
        "provider_b": provider_b,
        "service_b1": service_b1,
        "headers_b": {"X-Tenant": "beta", "X-Token": token_b},
    }


# ==============================================================================
# 1. Calendar Notes Tenant Scoping (TEN-004)
# ==============================================================================

def test_calendar_notes_crud_tenant_isolation(client: TestClient, db_session: Session, two_tenants):
    """Verify full CRUD operations on calendar notes are strictly isolated per tenant."""
    h_a = two_tenants["headers_a"]
    h_b = two_tenants["headers_b"]
    prov_a = two_tenants["provider_a"]
    prov_b = two_tenants["provider_b"]
    t_a = two_tenants["tenant_a"]
    t_b = two_tenants["tenant_b"]

    # 1. Tenant A creates calendar note
    note_payload = {
        "provider_id": prov_a.id,
        "date": "2026-09-01",
        "start_time": "09:00",
        "end_time": "11:00",
        "text": "Alpha Staff Briefing",
        "note_type": "meeting",
        "is_time_blocked": True,
    }
    resp_create = client.post("/api/admin/calendar-notes", json=note_payload, headers=h_a)
    assert resp_create.status_code == 201, resp_create.text
    note_a_id = resp_create.json()["data"]["id"]

    # Verify db record has tenant_id
    db_note = db_session.query(CalendarNote).filter(CalendarNote.id == note_a_id).first()
    assert db_note is not None
    assert db_note.tenant_id == t_a.id

    # 2. Tenant A lists notes -> sees note_a
    resp_list_a = client.get("/api/admin/calendar-notes", headers=h_a)
    assert resp_list_a.status_code == 200
    notes_a = resp_list_a.json()["data"]
    assert len(notes_a) == 1
    assert notes_a[0]["id"] == note_a_id

    # 3. Tenant B lists notes -> empty list (cannot see Tenant A notes)
    resp_list_b = client.get("/api/admin/calendar-notes", headers=h_b)
    assert resp_list_b.status_code == 200
    notes_b = resp_list_b.json()["data"]
    assert len(notes_b) == 0

    # 4. Tenant B attempts to update Tenant A's note -> 404 Not Found
    resp_up_b = client.put(
        f"/api/admin/calendar-notes/{note_a_id}",
        json={"text": "Hacked Note"},
        headers=h_b,
    )
    assert resp_up_b.status_code == 404

    # 5. Tenant B attempts to create note referencing Tenant A's provider -> 404 Not Found
    resp_cross_prov = client.post(
        "/api/admin/calendar-notes",
        json={
            "provider_id": prov_a.id,
            "date": "2026-09-02",
            "text": "Cross-tenant provider note",
        },
        headers=h_b,
    )
    assert resp_cross_prov.status_code == 404

    # 6. Tenant B attempts to delete Tenant A's note -> 404 Not Found
    resp_del_b = client.delete(f"/api/admin/calendar-notes/{note_a_id}", headers=h_b)
    assert resp_del_b.status_code == 404

    # Note still exists in DB
    db_session.refresh(db_note)
    assert db_note.text == "Alpha Staff Briefing"

    # 7. Tenant A updates and deletes their own note -> 200 & 204
    resp_up_a = client.put(
        f"/api/admin/calendar-notes/{note_a_id}",
        json={"text": "Alpha Staff Briefing - Updated"},
        headers=h_a,
    )
    assert resp_up_a.status_code == 200
    assert resp_up_a.json()["data"]["text"] == "Alpha Staff Briefing - Updated"

    resp_del_a = client.delete(f"/api/admin/calendar-notes/{note_a_id}", headers=h_a)
    assert resp_del_a.status_code == 204

    # Note is deleted
    assert db_session.query(CalendarNote).filter(CalendarNote.id == note_a_id).first() is None


# ==============================================================================
# 2. GDPR Consents Tenant Scoping (TEN-005)
# ==============================================================================

def test_gdpr_consents_tenant_scoping(client: TestClient, db_session: Session, two_tenants):
    """Verify GDPR consent creation and admin listing are strictly tenant-scoped."""
    h_a = two_tenants["headers_a"]
    h_b = two_tenants["headers_b"]
    c_a = two_tenants["client_a"]
    c_b = two_tenants["client_b"]
    t_a = two_tenants["tenant_a"]
    t_b = two_tenants["tenant_b"]

    # 1. Record consent for Client A under Tenant A public endpoint
    resp_consent_a = client.post(
        "/api/public/gdpr-consent",
        json={
            "client_id": c_a.id,
            "consent_type": "marketing",
            "is_approved": True,
            "ip_address": "198.51.100.1",
        },
        headers={"X-Tenant": "alpha"},
    )
    assert resp_consent_a.status_code == 201, resp_consent_a.text
    consent_a_id = resp_consent_a.json()["data"]["id"]

    db_consent_a = db_session.query(GdprConsent).filter(GdprConsent.id == consent_a_id).first()
    assert db_consent_a is not None
    assert db_consent_a.tenant_id == t_a.id

    # 2. Cross-tenant attempt: Record consent for Client B under Tenant A -> 404
    resp_cross = client.post(
        "/api/public/gdpr-consent",
        json={
            "client_id": c_b.id,
            "consent_type": "marketing",
            "is_approved": True,
            "ip_address": "198.51.100.2",
        },
        headers={"X-Tenant": "alpha"},
    )
    assert resp_cross.status_code == 404

    # 3. Record consent for Client B under Tenant B
    resp_consent_b = client.post(
        "/api/public/gdpr-consent",
        json={
            "client_id": c_b.id,
            "consent_type": "terms",
            "is_approved": True,
            "ip_address": "198.51.100.3",
        },
        headers={"X-Tenant": "beta"},
    )
    assert resp_consent_b.status_code == 201
    consent_b_id = resp_consent_b.json()["data"]["id"]

    # 4. Admin A lists consents -> only sees Tenant A consent
    resp_admin_list_a = client.get("/api/admin/gdpr-consents", headers=h_a)
    assert resp_admin_list_a.status_code == 200
    data_a = resp_admin_list_a.json()["data"]
    assert len(data_a) == 1
    assert data_a[0]["id"] == consent_a_id

    # 5. Admin A lists consents for Client A -> 200
    resp_client_a = client.get(f"/api/admin/gdpr-consents/{c_a.id}", headers=h_a)
    assert resp_client_a.status_code == 200
    assert len(resp_client_a.json()["data"]) == 1

    # 6. Admin A attempts to list consents for Client B -> 404 Not Found
    resp_cross_client = client.get(f"/api/admin/gdpr-consents/{c_b.id}", headers=h_a)
    assert resp_cross_client.status_code == 404

    # 7. Admin B lists consents -> only sees Tenant B consent
    resp_admin_list_b = client.get("/api/admin/gdpr-consents", headers=h_b)
    assert resp_admin_list_b.status_code == 200
    data_b = resp_admin_list_b.json()["data"]
    assert len(data_b) == 1
    assert data_b[0]["id"] == consent_b_id


# ==============================================================================
# 3. Public Timeline Tenant Scoping (TEN-006)
# ==============================================================================

def test_public_timeline_tenant_scoping(client: TestClient, db_session: Session, two_tenants):
    """Verify public timeline endpoints reject cross-tenant provider and service IDs."""
    prov_a = two_tenants["provider_a"]
    prov_b = two_tenants["provider_b"]
    svc_a1 = two_tenants["service_a1"]
    svc_b1 = two_tenants["service_b1"]

    # 1. Schedule endpoint for Provider A under Tenant A -> 200 OK
    resp_sched_a = client.get(
        f"/api/public/timeline/schedule/{prov_a.id}",
        headers={"X-Tenant": "alpha"},
    )
    assert resp_sched_a.status_code == 200
    assert resp_sched_a.json()["ok"] is True
    assert resp_sched_a.json()["data"]["providerId"] == prov_a.id

    # 2. Schedule endpoint for Provider A under Tenant B -> 404 Not Found
    resp_sched_cross = client.get(
        f"/api/public/timeline/schedule/{prov_a.id}",
        headers={"X-Tenant": "beta"},
    )
    assert resp_sched_cross.status_code == 404

    # 3. Available slots for Service A under Tenant A -> 200 OK
    resp_slots_a = client.get(
        f"/api/public/timeline/slots?service_id={svc_a1.id}&provider_id={prov_a.id}",
        headers={"X-Tenant": "alpha"},
    )
    assert resp_slots_a.status_code == 200
    assert resp_slots_a.json()["ok"] is True

    # 4. Available slots for Service A under Tenant B -> 404 Not Found
    resp_slots_cross_svc = client.get(
        f"/api/public/timeline/slots?service_id={svc_a1.id}",
        headers={"X-Tenant": "beta"},
    )
    assert resp_slots_cross_svc.status_code == 404

    # 5. Available slots with Service A + Provider B (cross-tenant) under Tenant A -> 404 Not Found
    resp_slots_cross_prov = client.get(
        f"/api/public/timeline/slots?service_id={svc_a1.id}&provider_id={prov_b.id}",
        headers={"X-Tenant": "alpha"},
    )
    assert resp_slots_cross_prov.status_code == 404

    # 6. First available day for Service A under Tenant A -> 200 OK
    resp_first_a = client.get(
        f"/api/public/timeline/first-available-day?service_id={svc_a1.id}",
        headers={"X-Tenant": "alpha"},
    )
    assert resp_first_a.status_code == 200
    assert resp_first_a.json()["ok"] is True

    # 7. First available day for Service A under Tenant B -> 404 Not Found
    resp_first_cross = client.get(
        f"/api/public/timeline/first-available-day?service_id={svc_a1.id}",
        headers={"X-Tenant": "beta"},
    )
    assert resp_first_cross.status_code == 404

    # 8. First available day for Service A with Provider B -> 404 Not Found
    resp_first_cross_prov = client.get(
        f"/api/public/timeline/first-available-day?service_id={svc_a1.id}&provider_id={prov_b.id}",
        headers={"X-Tenant": "alpha"},
    )
    assert resp_first_cross_prov.status_code == 404


# ==============================================================================
# 4. Tenant-Scoped Diagnostics (TEN-007)
# ==============================================================================

def test_diagnostics_counts_tenant_isolation(client: TestClient, db_session: Session, two_tenants):
    """Verify administrative diagnostics return entity and queue counts scoped exclusively to calling tenant."""
    h_a = two_tenants["headers_a"]
    h_b = two_tenants["headers_b"]
    t_a = two_tenants["tenant_a"]
    t_b = two_tenants["tenant_b"]
    c_a = two_tenants["client_a"]
    c_b = two_tenants["client_b"]
    s_a = two_tenants["service_a1"]
    s_b = two_tenants["service_b1"]
    p_a = two_tenants["provider_a"]
    p_b = two_tenants["provider_b"]

    # Seed extra records for Tenant A
    res_a = Resource(tenant_id=t_a.id, name="Alpha Room 1", type="room", capacity=1)
    db_session.add(res_a)

    booking_a = Booking(
        tenant_id=t_a.id,
        client_id=c_a.id,
        service_id=s_a.id,
        provider_id=p_a.id,
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
        status="confirmed",
    )
    db_session.add(booking_a)

    waitlist_a = WaitlistEntry(
        tenant_id=t_a.id,
        client_id=c_a.id,
        service_id=s_a.id,
        status=WaitlistStatus.REQUESTED,
    )
    db_session.add(waitlist_a)

    outbox_a1 = OutboxEvent(tenant_id=t_a.id, type="BOOKING_CONFIRMED", payload='{"id": 1}', processed=False)
    outbox_a2 = OutboxEvent(tenant_id=t_a.id, type="SEND_EMAIL", payload='{"id": 2}', processed=False)
    outbox_a_done = OutboxEvent(tenant_id=t_a.id, type="NOTIFICATION_SENT", payload='{"id": 3}', processed=True)
    db_session.add_all([outbox_a1, outbox_a2, outbox_a_done])

    # Seed extra records for Tenant B
    res_b1 = Resource(tenant_id=t_b.id, name="Beta Room 1", type="room", capacity=2)
    res_b2 = Resource(tenant_id=t_b.id, name="Beta Room 2", type="room", capacity=4)
    db_session.add_all([res_b1, res_b2])

    booking_b1 = Booking(
        tenant_id=t_b.id,
        client_id=c_b.id,
        service_id=s_b.id,
        provider_id=p_b.id,
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        end_time=datetime.now(timezone.utc) + timedelta(days=2, minutes=45),
        status="confirmed",
    )
    booking_b2 = Booking(
        tenant_id=t_b.id,
        client_id=c_b.id,
        service_id=s_b.id,
        provider_id=p_b.id,
        start_time=datetime.now(timezone.utc) + timedelta(days=3),
        end_time=datetime.now(timezone.utc) + timedelta(days=3, minutes=45),
        status="completed",
    )
    db_session.add_all([booking_b1, booking_b2])

    outbox_b = OutboxEvent(tenant_id=t_b.id, type="BOOKING_CONFIRMED", payload='{"id": 4}', processed=False)
    db_session.add(outbox_b)

    db_session.commit()

    # Query diagnostics as Admin A
    resp_diag_a = client.get("/api/admin/system/diagnostics", headers=h_a)
    assert resp_diag_a.status_code == 200
    counts_a = resp_diag_a.json()["counts"]
    assert counts_a["services"] == 2       # service_a1, service_a2
    assert counts_a["providers"] == 1      # provider_a
    assert counts_a["clients"] == 1        # client_a
    assert counts_a["bookings"] == 1       # booking_a
    assert counts_a["resources"] == 1      # res_a
    assert counts_a["waitlist_entries"] == 1  # waitlist_a
    assert counts_a["outbox_events"] == 2  # outbox_a1, outbox_a2 (unprocessed only)

    # Query diagnostics as Admin B
    resp_diag_b = client.get("/api/admin/system/diagnostics", headers=h_b)
    assert resp_diag_b.status_code == 200
    counts_b = resp_diag_b.json()["counts"]
    assert counts_b["services"] == 1       # service_b1
    assert counts_b["providers"] == 1      # provider_b
    assert counts_b["clients"] == 1        # client_b
    assert counts_b["bookings"] == 2       # booking_b1, booking_b2
    assert counts_b["resources"] == 2      # res_b1, res_b2
    assert counts_b["waitlist_entries"] == 0
    assert counts_b["outbox_events"] == 1  # outbox_b (unprocessed only)


# ==============================================================================
# 5. Device Registration Tenant & User Binding (TEN-008)
# ==============================================================================

def test_device_registration_tenant_binding(client: TestClient, db_session: Session, two_tenants):
    """Verify device token registration binds properly to the active tenant and validates user/client scope."""
    t_a = two_tenants["tenant_a"]
    t_b = two_tenants["tenant_b"]
    u_a = two_tenants["user_a"]
    u_b = two_tenants["user_b"]
    c_a = two_tenants["client_a"]
    c_b = two_tenants["client_b"]
    h_a = two_tenants["headers_a"]

    # 1. Register device for Tenant A user
    payload_a = {
        "token": "fcm_token_alpha_user_1",
        "platform": "ios",
        "device_id": "iphone_alpha",
        "user_id": u_a.id,
        "enabled": True,
    }
    resp_reg_a = client.post("/api/v1/devices/register", json=payload_a, headers={"X-Tenant": "alpha"})
    assert resp_reg_a.status_code == 200, resp_reg_a.text
    token_record_a = db_session.query(DeviceToken).filter_by(token="fcm_token_alpha_user_1").first()
    assert token_record_a is not None
    assert token_record_a.tenant_id == t_a.id
    assert token_record_a.user_id == u_a.id

    # 2. Register device with Tenant A header but User B (from Tenant B) -> 404
    payload_cross_user = {
        "token": "fcm_token_cross_user",
        "platform": "android",
        "device_id": "android_beta",
        "user_id": u_b.id,
        "enabled": True,
    }
    resp_cross_user = client.post("/api/v1/devices/register", json=payload_cross_user, headers={"X-Tenant": "alpha"})
    assert resp_cross_user.status_code == 404

    # 3. Register device with Tenant A header but Client B (from Tenant B) -> 404
    payload_cross_client = {
        "token": "fcm_token_cross_client",
        "platform": "android",
        "device_id": "android_beta",
        "client_id": c_b.id,
        "enabled": True,
    }
    resp_cross_client = client.post("/api/v1/devices/register", json=payload_cross_client, headers={"X-Tenant": "alpha"})
    assert resp_cross_client.status_code == 404

    # 4. Register device for Tenant A client -> succeeds and binds tenant_id
    payload_client_a = {
        "token": "fcm_token_alpha_client_1",
        "platform": "web",
        "device_id": "chrome_browser",
        "client_id": c_a.id,
        "enabled": True,
    }
    resp_client_a = client.post("/api/v1/devices/register", json=payload_client_a, headers={"X-Tenant": "alpha"})
    assert resp_client_a.status_code == 200
    token_client_a = db_session.query(DeviceToken).filter_by(token="fcm_token_alpha_client_1").first()
    assert token_client_a is not None
    assert token_client_a.tenant_id == t_a.id
    assert token_client_a.client_id == c_a.id

    # 5. Device token registration via authenticated user token (X-Token) auto-derives tenant
    payload_auth = {
        "token": "fcm_token_admin_auto_bind",
        "platform": "ios",
        "device_id": "ipad_admin",
        "enabled": True,
    }
    resp_auth = client.post("/api/v1/devices/register", json=payload_auth, headers=h_a)
    assert resp_auth.status_code == 200
    token_auth = db_session.query(DeviceToken).filter_by(token="fcm_token_admin_auto_bind").first()
    assert token_auth is not None
    assert token_auth.tenant_id == t_a.id
    assert token_auth.user_id == u_a.id

    # 6. Device registration without tenant header returns 400 Bad Request (fails closed)
    resp_no_tenant = client.post("/api/v1/devices/register", json=payload_a)
    assert resp_no_tenant.status_code == 400

    # 7. Device registration with unknown tenant returns 404 Not Found
    resp_unknown_tenant = client.post(
        "/api/v1/devices/register",
        json=payload_a,
        headers={"X-Tenant": "unknown-nonexistent-tenant"}
    )
    assert resp_unknown_tenant.status_code == 404

