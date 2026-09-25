"""Tests for Tenant Entitlements Engine, Module Store, and Dynamic Entitlements."""

from datetime import datetime, timezone
import pytest
from fastapi import status

from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import create_access_token


@pytest.fixture
def starter_tenant_and_owner(db_session):
    """Fixture providing a starter tier tenant and an owner user."""
    tenant = Tenant(
        name="Starter Studio",
        subdomain="starter-studio",
        subscription_tier="starter",
        addon_quota=0,
        enabled_modules=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    owner = User(
        tenant_id=tenant.id,
        login="starter_owner",
        password_hash="fake_hash",
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    token = create_access_token({"sub": str(owner.id)})
    headers = {"X-Tenant": tenant.subdomain, "X-Token": token}
    return tenant, owner, headers


@pytest.fixture
def growth_tenant_and_owner(db_session):
    """Fixture providing a growth tier tenant (quota 3) and an owner user."""
    tenant = Tenant(
        name="Growth Clinic",
        subdomain="growth-clinic",
        subscription_tier="growth",
        addon_quota=3,
        enabled_modules=["locations", "providers"],
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    owner = User(
        tenant_id=tenant.id,
        login="growth_owner",
        password_hash="fake_hash",
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    token = create_access_token({"sub": str(owner.id)})
    headers = {"X-Tenant": tenant.subdomain, "X-Token": token}
    return tenant, owner, headers


@pytest.fixture
def unlimited_tenant_and_owner(db_session):
    """Fixture providing an unlimited tier tenant and an owner user."""
    tenant = Tenant(
        name="Unlimited Enterprise",
        subdomain="unlimited-ent",
        subscription_tier="unlimited",
        addon_quota=999,
        enabled_modules=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    owner = User(
        tenant_id=tenant.id,
        login="unlimited_owner",
        password_hash="fake_hash",
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    token = create_access_token({"sub": str(owner.id)})
    headers = {"X-Tenant": tenant.subdomain, "X-Token": token}
    return tenant, owner, headers


def test_get_tenant_modules_starter(client, starter_tenant_and_owner):
    """Test retrieving modules for a starter tenant."""
    tenant, owner, headers = starter_tenant_and_owner
    response = client.get("/api/admin/tenant/modules", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    assert data["tier"] == "starter"
    assert data["addon_quota"] == 0
    assert data["used_addons"] == 0
    assert data["available_addons"] == 0
    assert len(data["modules"]) > 0

    # Core modules must be enabled
    modules_by_key = {m["key"]: m for m in data["modules"]}
    assert modules_by_key["dashboard"]["enabled"] is True
    assert modules_by_key["calendar"]["enabled"] is True
    assert modules_by_key["bookings"]["enabled"] is True
    assert modules_by_key["website"]["enabled"] is True
    assert modules_by_key["locations"]["enabled"] is False
    assert modules_by_key["sms_assistant"]["enabled"] is False


def test_get_tenant_modules_growth(client, growth_tenant_and_owner):
    """Test retrieving modules for a growth tenant with active add-ons."""
    tenant, owner, headers = growth_tenant_and_owner
    response = client.get("/api/admin/tenant/modules", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    assert data["tier"] == "growth"
    assert data["addon_quota"] == 3
    assert data["used_addons"] == 2  # locations, providers
    assert data["available_addons"] == 1

    modules_by_key = {m["key"]: m for m in data["modules"]}
    assert modules_by_key["locations"]["enabled"] is True
    assert modules_by_key["providers"]["enabled"] is True
    assert modules_by_key["sms_assistant"]["enabled"] is False


def test_get_tenant_modules_unlimited(client, unlimited_tenant_and_owner):
    """Test retrieving modules for an unlimited tier tenant."""
    tenant, owner, headers = unlimited_tenant_and_owner
    response = client.get("/api/admin/tenant/modules", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    assert data["tier"] == "unlimited"
    assert data["addon_quota"] == 999
    assert data["available_addons"] == 999


def test_toggle_addon_module_within_quota(client, growth_tenant_and_owner):
    """Test enabling a third add-on within quota, then disabling it."""
    tenant, owner, headers = growth_tenant_and_owner

    # Currently 2 add-ons active (locations, providers), quota is 3.
    # Enable 'sms_assistant'
    res_enable = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "sms_assistant", "enabled": True},
        headers=headers,
    )
    assert res_enable.status_code == status.HTTP_200_OK, res_enable.text
    data_enable = res_enable.json()
    assert data_enable["ok"] is True
    assert "sms_assistant" in data_enable["enabled_modules"]

    # Verify via GET
    res_get = client.get("/api/admin/tenant/modules", headers=headers)
    assert res_get.status_code == status.HTTP_200_OK
    data_get = res_get.json()
    assert data_get["used_addons"] == 3
    assert data_get["available_addons"] == 0

    # Now disable 'sms_assistant'
    res_disable = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "sms_assistant", "enabled": False},
        headers=headers,
    )
    assert res_disable.status_code == status.HTTP_200_OK, res_disable.text
    data_disable = res_disable.json()
    assert data_disable["ok"] is True
    assert "sms_assistant" not in data_disable["enabled_modules"]

    # Verify used_addons returned to 2
    res_get2 = client.get("/api/admin/tenant/modules", headers=headers)
    assert res_get2.json()["used_addons"] == 2


def test_quota_enforcement_prevents_exceeding_quota(client, starter_tenant_and_owner):
    """Test that attempting to enable an add-on on starter tier (quota 0) fails with 400."""
    tenant, owner, headers = starter_tenant_and_owner

    # Attempt to enable 'locations'
    response = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "locations", "enabled": True},
        headers=headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res_data = response.json()
    err_msg = res_data.get("detail") or res_data.get("error", {}).get("message", "")
    assert "Add-on quota reached" in err_msg
    assert "Starter" in err_msg or "starter" in err_msg


def test_core_module_cannot_be_disabled(client, growth_tenant_and_owner):
    """Test that core modules (dashboard, calendar, bookings, website) cannot be toggled off."""
    tenant, owner, headers = growth_tenant_and_owner

    for core_key in ["dashboard", "calendar", "bookings", "website"]:
        response = client.post(
            "/api/admin/tenant/modules/toggle",
            json={"module_key": core_key, "enabled": False},
            headers=headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        res_data = response.json()
        err_msg = res_data.get("detail") or res_data.get("error", {}).get("message", "")
        assert "cannot be disabled" in err_msg


def test_toggle_unknown_module_fails(client, growth_tenant_and_owner):
    """Test that attempting to toggle a non-existent module returns 400."""
    tenant, owner, headers = growth_tenant_and_owner

    response = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "space_travel", "enabled": True},
        headers=headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res_data = response.json()
    err_msg = res_data.get("detail") or res_data.get("error", {}).get("message", "")
    assert "Unknown module" in err_msg


def test_non_owner_forbidden_from_toggling(client, starter_tenant_and_owner, db_session):
    """Test that a staff/admin user without role=='owner' cannot toggle modules."""
    tenant, owner, _ = starter_tenant_and_owner

    staff_user = User(
        tenant_id=tenant.id,
        login="staff_admin",
        password_hash="fake_hash",
        role="admin",  # not owner
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(staff_user)
    db_session.commit()
    db_session.refresh(staff_user)

    token = create_access_token({"sub": str(staff_user.id)})
    headers = {"X-Tenant": tenant.subdomain, "X-Token": token}

    response = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "locations", "enabled": True},
        headers=headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_update_tenant_tier_and_quota(client, starter_tenant_and_owner):
    """Test updating tenant tier from starter to growth."""
    tenant, owner, headers = starter_tenant_and_owner

    # Upgrade to growth
    res_tier = client.put(
        "/api/admin/tenant/modules/tier",
        json={"tier": "growth"},
        headers=headers,
    )
    assert res_tier.status_code == status.HTTP_200_OK, res_tier.text
    data = res_tier.json()
    assert data["tier"] == "growth"
    assert data["addon_quota"] == 3

    # Now enabling locations succeeds
    res_enable = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "locations", "enabled": True},
        headers=headers,
    )
    assert res_enable.status_code == status.HTTP_200_OK
    assert "locations" in res_enable.json()["enabled_modules"]
