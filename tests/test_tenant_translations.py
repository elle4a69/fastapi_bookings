"""Tenant Translations & Dynamic Wording Engine Verification Suite.

Tests cover:
1. Public endpoint returns tenant-specific terminology with safe fallbacks.
2. Admin endpoint returns current wording, presets catalog, and resolved terminology.
3. Admin update endpoint allows updating custom terms and applying industry presets.
4. Layering precedence: Default fallbacks -> Industry Presets -> Custom Tenant Overrides.
5. Strict cross-tenant isolation (Tenant B cannot read or overwrite Tenant A's terminology).
6. Cascade delete integrity when a tenant is removed.
"""

import pytest
from app.models.tenant import Tenant
from app.models.tenant_translation import TenantTranslation
from app.models.user import User
from app.core.security import create_access_token, get_password_hash
from app.services.localization.presets import DEFAULT_TERMINOLOGY, INDUSTRY_PRESETS


def _create_tenant_with_admin(db_session, subdomain: str, name: str):
    """Helper to provision a tenant and associated owner/admin user."""
    tenant = Tenant(
        name=name,
        subdomain=subdomain,
        subscription_tier="growth",
    )
    db_session.add(tenant)
    db_session.flush()

    admin = User(
        tenant_id=tenant.id,
        login=f"admin@{subdomain}.test",
        password_hash=get_password_hash("StrongSecret123!"),
        role="admin",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(tenant)
    db_session.refresh(admin)

    token = create_access_token(data={"sub": str(admin.id), "tenant_id": tenant.id})
    return tenant, admin, token


def test_public_translations_defaults(client, db_session):
    """Public endpoint returns default terminology when no custom translation is stored."""
    tenant, _, _ = _create_tenant_with_admin(db_session, "default-clinic", "Default Clinic")

    resp = client.get("/api/public/translations", headers={"X-Tenant": "default-clinic"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["locale"] == "en"
    assert "terminology" in data
    # Standard defaults check
    assert data["terminology"]["client"] == "Client"
    assert data["terminology"]["provider"] == "Provider"
    assert data["terminology"]["booking"] == "Booking"
    assert data["terminology"]["service"] == "Service"
    assert data["terminology"]["location"] == "Location"


def test_admin_get_translations_and_presets(client, db_session):
    """Admin endpoint returns current translation, resolved terms, and available presets."""
    tenant, admin, token = _create_tenant_with_admin(db_session, "med-center", "Med Center")

    resp = client.get(
        "/api/admin/translations",
        headers={"X-Tenant": "med-center", "X-Token": token},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "translation" in data
    assert data["translation"]["tenant_id"] == tenant.id
    assert "presets" in data
    assert len(data["presets"]) >= 4

    preset_ids = [p["id"] for p in data["presets"]]
    assert "allied_health" in preset_ids
    assert "automotive" in preset_ids
    assert "wellness_salon" in preset_ids
    assert "professional_services" in preset_ids

    assert "resolved_terminology" in data
    assert data["resolved_terminology"]["client"] == "Client"


def test_admin_update_custom_terms(client, db_session):
    """Admin can update custom terms directly."""
    tenant, admin, token = _create_tenant_with_admin(db_session, "custom-studio", "Custom Studio")

    payload = {
        "locale": "en",
        "terminology": {
            "client": "Guest",
            "clients": "Guests",
            "booking": "Reservation",
            "bookings": "Reservations",
        },
    }

    put_resp = client.put(
        "/api/admin/translations",
        json=payload,
        headers={"X-Tenant": "custom-studio", "X-Token": token},
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["terminology"]["client"] == "Guest"
    assert updated["terminology"]["booking"] == "Reservation"

    # Verify public endpoint reflects custom terms
    pub_resp = client.get("/api/public/translations", headers={"X-Tenant": "custom-studio"})
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()
    assert pub_data["terminology"]["client"] == "Guest"
    assert pub_data["terminology"]["booking"] == "Reservation"
    # Unoverridden keys fall back to defaults
    assert pub_data["terminology"]["provider"] == "Provider"


def test_admin_apply_industry_preset_allied_health(client, db_session):
    """Applying allied_health preset updates vocabulary across all core entities."""
    tenant, admin, token = _create_tenant_with_admin(db_session, "health-hub", "Health Hub")

    put_resp = client.put(
        "/api/admin/translations",
        json={"preset": "allied_health"},
        headers={"X-Tenant": "health-hub", "X-Token": token},
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()

    assert updated["terminology"]["client"] == "Patient"
    assert updated["terminology"]["clients"] == "Patients"
    assert updated["terminology"]["provider"] == "Practitioner"
    assert updated["terminology"]["providers"] == "Practitioners"
    assert updated["terminology"]["booking"] == "Appointment"
    assert updated["terminology"]["service"] == "Consultation"
    assert updated["terminology"]["location"] == "Clinic"

    # Public endpoint reflects allied health preset
    pub_resp = client.get("/api/public/translations", headers={"X-Tenant": "health-hub"})
    assert pub_resp.status_code == 200
    pub_terms = pub_resp.json()["terminology"]
    assert pub_terms["client"] == "Patient"
    assert pub_terms["provider"] == "Practitioner"


def test_admin_apply_preset_with_custom_overrides(client, db_session):
    """Tenant overrides take precedence over preset terms."""
    tenant, admin, token = _create_tenant_with_admin(db_session, "auto-care", "Auto Care Shop")

    # Apply automotive preset but override 'booking' with 'Work Order'
    payload = {
        "preset": "automotive",
        "terminology": {
            "booking": "Work Order",
            "bookings": "Work Orders",
        },
    }

    put_resp = client.put(
        "/api/admin/translations",
        json=payload,
        headers={"X-Tenant": "auto-care", "X-Token": token},
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()

    # Preset values
    assert updated["terminology"]["client"] == "Customer"
    assert updated["terminology"]["provider"] == "Technician"
    assert updated["terminology"]["location"] == "Workshop"
    # Custom override
    assert updated["terminology"]["booking"] == "Work Order"
    assert updated["terminology"]["bookings"] == "Work Orders"


def test_admin_apply_invalid_preset_rejected(client, db_session):
    """Providing a non-existent preset returns 400 Bad Request."""
    tenant, admin, token = _create_tenant_with_admin(db_session, "fail-preset", "Fail Preset")

    put_resp = client.put(
        "/api/admin/translations",
        json={"preset": "non_existent_preset_xyz"},
        headers={"X-Tenant": "fail-preset", "X-Token": token},
    )
    assert put_resp.status_code == 400
    body = put_resp.json()
    assert "Unknown industry preset" in body["error"]["message"]


def test_strict_cross_tenant_isolation(client, db_session):
    """Tenant B cannot read or overwrite Tenant A translations."""
    tenant_a, admin_a, token_a = _create_tenant_with_admin(db_session, "clinic-a", "Clinic A")
    tenant_b, admin_b, token_b = _create_tenant_with_admin(db_session, "garage-b", "Garage B")

    # Tenant A configures allied_health preset
    client.put(
        "/api/admin/translations",
        json={"preset": "allied_health"},
        headers={"X-Tenant": "clinic-a", "X-Token": token_a},
    )

    # Tenant B configures automotive preset
    client.put(
        "/api/admin/translations",
        json={"preset": "automotive"},
        headers={"X-Tenant": "garage-b", "X-Token": token_b},
    )

    # 1. Tenant A public endpoint returns Patient
    resp_a = client.get("/api/public/translations", headers={"X-Tenant": "clinic-a"})
    assert resp_a.status_code == 200
    assert resp_a.json()["terminology"]["client"] == "Patient"
    assert resp_a.json()["terminology"]["provider"] == "Practitioner"

    # 2. Tenant B public endpoint returns Customer
    resp_b = client.get("/api/public/translations", headers={"X-Tenant": "garage-b"})
    assert resp_b.status_code == 200
    assert resp_b.json()["terminology"]["client"] == "Customer"
    assert resp_b.json()["terminology"]["provider"] == "Technician"

    # 3. Tenant B admin token cannot write to Tenant A scope
    # Header X-Tenant is clinic-a, but token belongs to garage-b admin
    cross_write = client.put(
        "/api/admin/translations",
        json={"terminology": {"client": "Compromised"}},
        headers={"X-Tenant": "clinic-a", "X-Token": token_b},
    )
    # Fastapi auth dependency fails user lookup in clinic-a scope
    assert cross_write.status_code in {401, 403}

    # Verify Tenant A terms remained untouched
    verify_a = client.get("/api/public/translations", headers={"X-Tenant": "clinic-a"})
    assert verify_a.json()["terminology"]["client"] == "Patient"


def test_tenant_translation_cascade_delete(client, db_session):
    """Deleting a tenant removes its associated translation row via cascade."""
    tenant, admin, token = _create_tenant_with_admin(db_session, "cascade-test", "Cascade Test")

    # Set up translation record
    client.put(
        "/api/admin/translations",
        json={"preset": "wellness_salon"},
        headers={"X-Tenant": "cascade-test", "X-Token": token},
    )

    # Ensure record exists in DB
    record = db_session.query(TenantTranslation).filter_by(tenant_id=tenant.id).first()
    assert record is not None
    assert record.terminology["provider"] == "Stylist"

    # Delete the tenant
    db_session.delete(tenant)
    db_session.commit()

    # Verify translation record was deleted as well
    orphaned = db_session.query(TenantTranslation).filter_by(tenant_id=tenant.id).first()
    assert orphaned is None
