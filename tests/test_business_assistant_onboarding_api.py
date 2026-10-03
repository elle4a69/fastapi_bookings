"""Authenticated onboarding API tests backed by native tenant setup records."""

from app.core.security import create_access_token
from app.models.location import Location
from app.models.provider import Provider
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.user import User


def _owner(db_session, suffix: str, *, tenant: Tenant | None = None) -> tuple[Tenant, User]:
    tenant = tenant or Tenant(
        name=f"Onboarding Tenant {suffix}",
        subdomain=f"onboarding-{suffix}",
        enabled_modules=["locations", "categories", "untrusted_context_key"],
    )
    if tenant.id is None:
        db_session.add(tenant)
        db_session.flush()
    user = User(tenant_id=tenant.id, login=f"onboarding-owner-{suffix}", password_hash="test", role="owner")
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def test_onboarding_requires_an_authenticated_owner(client, db_session):
    tenant, _user = _owner(db_session, "auth")
    response = client.get("/api/admin/business-assistant/onboarding", headers={"X-Tenant": tenant.subdomain})
    assert response.status_code == 401


def test_onboarding_returns_live_allowlisted_setup_context_and_persists_personal_progress(client, db_session):
    tenant, user = _owner(db_session, "setup")
    db_session.add_all(
        [
            Service(tenant_id=tenant.id, name="Synthetic service", duration=30, active=True),
            Service(tenant_id=tenant.id, name="Inactive synthetic service", duration=30, active=False),
            Provider(tenant_id=tenant.id, name="Synthetic provider", active=True),
            Provider(tenant_id=tenant.id, name="Inactive synthetic provider", active=False),
            Location(tenant_id=tenant.id, name="Synthetic location", active=True),
            Location(tenant_id=tenant.id, name="Inactive synthetic location", active=False),
        ]
    )
    db_session.commit()
    headers = _headers(tenant, user)
    original_enabled_modules = list(tenant.enabled_modules)

    initial = client.get("/api/admin/business-assistant/onboarding", headers=headers)
    assert initial.status_code == 200
    initial_body = initial.json()
    assert initial_body["progress"] == {
        "status": "not_started",
        "completed_steps": [],
        "updated_at": None,
    }
    assert initial_body["product_context"]["availability"] == "available"
    assert set(("dashboard", "calendar", "bookings", "website", "locations", "categories")) <= set(
        initial_body["product_context"]["enabled_modules"]
    )
    assert "untrusted_context_key" not in initial_body["product_context"]["enabled_modules"]
    assert initial_body["product_context"]["setup_counts"] == {
        "active_services": 1,
        "active_providers": 1,
        "active_locations": 1,
    }
    assert "name" not in initial_body["product_context"]

    updated = client.put(
        "/api/admin/business-assistant/onboarding/progress",
        headers=headers,
        json={"step": "review_product_context"},
    )
    assert updated.status_code == 200
    assert updated.json()["progress"]["status"] == "in_progress"
    assert updated.json()["progress"]["completed_steps"] == ["review_product_context"]

    for step in ("review_catalog_readiness", "prepare_product_question"):
        completed = client.put(
            "/api/admin/business-assistant/onboarding/progress",
            headers=headers,
            json={"step": step},
        )
        assert completed.status_code == 200
    assert completed.json()["progress"]["status"] == "completed"
    db_session.refresh(tenant)
    assert tenant.enabled_modules == original_enabled_modules


def test_onboarding_progress_is_not_shared_between_users_or_tenants(client, db_session):
    tenant_a, user_a = _owner(db_session, "scope-a")
    _same_tenant, user_same_tenant = _owner(db_session, "scope-user", tenant=tenant_a)
    tenant_b, user_b = _owner(db_session, "scope-b")
    owner_headers = _headers(tenant_a, user_a)

    updated = client.put(
        "/api/admin/business-assistant/onboarding/progress",
        headers=owner_headers,
        json={"step": "review_product_context"},
    )
    assert updated.status_code == 200

    same_tenant = client.get("/api/admin/business-assistant/onboarding", headers=_headers(tenant_a, user_same_tenant))
    other_tenant = client.get("/api/admin/business-assistant/onboarding", headers=_headers(tenant_b, user_b))
    assert same_tenant.status_code == 200
    assert other_tenant.status_code == 200
    assert same_tenant.json()["progress"]["status"] == "not_started"
    assert other_tenant.json()["progress"]["status"] == "not_started"
    assert other_tenant.json()["product_context"]["setup_counts"] == {
        "active_services": 0,
        "active_providers": 0,
        "active_locations": 0,
    }


def test_onboarding_rejects_unknown_progress_steps(client, db_session):
    tenant, user = _owner(db_session, "validation")
    response = client.put(
        "/api/admin/business-assistant/onboarding/progress",
        headers=_headers(tenant, user),
        json={"step": "change_tenant_settings"},
    )
    assert response.status_code == 422
