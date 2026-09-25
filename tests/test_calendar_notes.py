"""Tests for calendar notes tenant and provider isolation."""

from datetime import date
import pytest
from fastapi import status

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.models.provider import Provider
from app.models.calendar_note import CalendarNote


def _auth_headers(tenant: Tenant, user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


@pytest.fixture
def calendar_fixtures(db_session):
    """Seed synthetic tenants, providers, and users for calendar notes testing."""
    tenant_a = Tenant(name="Tenant Alpha", subdomain="tenant-alpha")
    tenant_b = Tenant(name="Tenant Beta", subdomain="tenant-beta")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    provider_a1 = Provider(tenant_id=tenant_a.id, name="Dr. Alpha 1", active=True)
    provider_a2 = Provider(tenant_id=tenant_a.id, name="Dr. Alpha 2", active=True)
    provider_b1 = Provider(tenant_id=tenant_b.id, name="Dr. Beta 1", active=True)
    db_session.add_all([provider_a1, provider_a2, provider_b1])
    db_session.flush()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin-alpha@example.com",
        password_hash="hash-alpha",
        role="admin",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin-beta@example.com",
        password_hash="hash-beta",
        role="admin",
    )
    staff_provider_a1 = User(
        tenant_id=tenant_a.id,
        login="provider-a1@example.com",
        password_hash="hash-p1",
        role="provider",
        provider_id=provider_a1.id,
    )
    staff_provider_a2 = User(
        tenant_id=tenant_a.id,
        login="provider-a2@example.com",
        password_hash="hash-p2",
        role="provider",
        provider_id=provider_a2.id,
    )

    db_session.add_all([admin_a, admin_b, staff_provider_a1, staff_provider_a2])
    db_session.flush()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "provider_a1": provider_a1,
        "provider_a2": provider_a2,
        "provider_b1": provider_b1,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "staff_provider_a1": staff_provider_a1,
        "staff_provider_a2": staff_provider_a2,
    }


def test_create_and_get_calendar_note(client, calendar_fixtures):
    f = calendar_fixtures
    headers_a = _auth_headers(f["tenant_a"], f["admin_a"])

    payload = {
        "provider_id": f["provider_a1"].id,
        "date": "2026-10-01",
        "start_time": "09:00",
        "end_time": "12:00",
        "text": "Alpha Clinic Holiday",
        "note_type": "holiday",
        "is_time_blocked": True,
    }

    create_resp = client.post("/api/admin/calendar-notes", json=payload, headers=headers_a)
    assert create_resp.status_code == status.HTTP_201_CREATED
    data = create_resp.json()
    assert data["ok"] is True
    note_id = data["data"]["id"]
    assert data["data"]["text"] == "Alpha Clinic Holiday"

    # Fetch via GET single note
    get_resp = client.get(f"/api/admin/calendar-notes/{note_id}", headers=headers_a)
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["data"]["id"] == note_id


def test_cross_tenant_cannot_see_or_access_notes(client, calendar_fixtures, db_session):
    f = calendar_fixtures
    headers_a = _auth_headers(f["tenant_a"], f["admin_a"])
    headers_b = _auth_headers(f["tenant_b"], f["admin_b"])

    # Create note in Tenant A
    note_a = CalendarNote(
        tenant_id=f["tenant_a"].id,
        provider_id=f["provider_a1"].id,
        date=date(2026, 10, 5),
        text="Tenant A Secret Conference",
        is_time_blocked=True,
    )
    db_session.add(note_a)
    db_session.commit()
    db_session.refresh(note_a)

    # 1. Tenant B listing notes: does not see Tenant A's note
    list_b = client.get("/api/admin/calendar-notes", headers=headers_b)
    assert list_b.status_code == status.HTTP_200_OK
    notes_b = list_b.json()["data"]
    assert all(n["id"] != note_a.id for n in notes_b)

    # 2. Tenant B GET note by ID: returns 404
    get_b = client.get(f"/api/admin/calendar-notes/{note_a.id}", headers=headers_b)
    assert get_b.status_code == status.HTTP_404_NOT_FOUND

    # 3. Tenant B PUT note by ID: returns 404
    put_b = client.put(
        f"/api/admin/calendar-notes/{note_a.id}",
        json={"text": "Hijacked by Tenant B"},
        headers=headers_b,
    )
    assert put_b.status_code == status.HTTP_404_NOT_FOUND

    # 4. Tenant B DELETE note by ID: returns 404
    del_b = client.delete(f"/api/admin/calendar-notes/{note_a.id}", headers=headers_b)
    assert del_b.status_code == status.HTTP_404_NOT_FOUND

    # Verify note in Tenant A is unchanged
    get_a = client.get(f"/api/admin/calendar-notes/{note_a.id}", headers=headers_a)
    assert get_a.status_code == status.HTTP_200_OK
    assert get_a.json()["data"]["text"] == "Tenant A Secret Conference"


def test_cannot_assign_cross_tenant_provider(client, calendar_fixtures):
    f = calendar_fixtures
    headers_a = _auth_headers(f["tenant_a"], f["admin_a"])

    # Tenant A tries to create note referencing Tenant B's provider
    bad_payload = {
        "provider_id": f["provider_b1"].id,
        "date": "2026-10-10",
        "text": "Cross tenant provider note",
    }
    resp = client.post("/api/admin/calendar-notes", json=bad_payload, headers=headers_a)
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # Create valid note in Tenant A
    good_payload = {
        "provider_id": f["provider_a1"].id,
        "date": "2026-10-10",
        "text": "Valid note",
    }
    create_resp = client.post("/api/admin/calendar-notes", json=good_payload, headers=headers_a)
    assert create_resp.status_code == status.HTTP_201_CREATED
    note_id = create_resp.json()["data"]["id"]

    # Tenant A tries to update note to reference Tenant B's provider
    bad_update = {"provider_id": f["provider_b1"].id}
    update_resp = client.put(f"/api/admin/calendar-notes/{note_id}", json=bad_update, headers=headers_a)
    assert update_resp.status_code == status.HTTP_404_NOT_FOUND


def test_provider_role_isolation_within_tenant(client, calendar_fixtures, db_session):
    f = calendar_fixtures
    headers_p1 = _auth_headers(f["tenant_a"], f["staff_provider_a1"])
    headers_p2 = _auth_headers(f["tenant_a"], f["staff_provider_a2"])

    note_p1 = CalendarNote(
        tenant_id=f["tenant_a"].id,
        provider_id=f["provider_a1"].id,
        date=date(2026, 10, 15),
        text="Doctor A1 Personal Note",
    )
    note_p2 = CalendarNote(
        tenant_id=f["tenant_a"].id,
        provider_id=f["provider_a2"].id,
        date=date(2026, 10, 16),
        text="Doctor A2 Personal Note",
    )
    db_session.add_all([note_p1, note_p2])
    db_session.commit()

    # Provider 1 lists notes: should see p1 note, not p2 note
    p1_list = client.get("/api/admin/calendar-notes", headers=headers_p1)
    assert p1_list.status_code == status.HTTP_200_OK
    p1_note_ids = [n["id"] for n in p1_list.json()["data"]]
    assert note_p1.id in p1_note_ids
    assert note_p2.id not in p1_note_ids

    # Provider 1 GET p2 note directly: 404
    p1_get_p2 = client.get(f"/api/admin/calendar-notes/{note_p2.id}", headers=headers_p1)
    assert p1_get_p2.status_code == status.HTTP_404_NOT_FOUND

    # Provider 2 GET p2 note directly: 200
    p2_get_p2 = client.get(f"/api/admin/calendar-notes/{note_p2.id}", headers=headers_p2)
    assert p2_get_p2.status_code == status.HTTP_200_OK


def test_update_and_delete_calendar_note(client, calendar_fixtures, db_session):
    f = calendar_fixtures
    headers_a = _auth_headers(f["tenant_a"], f["admin_a"])

    note = CalendarNote(
        tenant_id=f["tenant_a"].id,
        provider_id=f["provider_a1"].id,
        date=date(2026, 10, 20),
        text="Initial Note",
    )
    db_session.add(note)
    db_session.commit()

    # Update
    update_resp = client.put(
        f"/api/admin/calendar-notes/{note.id}",
        json={"text": "Updated Note Content", "is_time_blocked": True},
        headers=headers_a,
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["data"]["text"] == "Updated Note Content"
    assert update_resp.json()["data"]["is_time_blocked"] is True

    # Delete
    del_resp = client.delete(f"/api/admin/calendar-notes/{note.id}", headers=headers_a)
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    # Verify deleted
    get_resp = client.get(f"/api/admin/calendar-notes/{note.id}", headers=headers_a)
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND
