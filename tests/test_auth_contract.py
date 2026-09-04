"""Regression contract tests for tenant-specific administrative access."""

from fastapi import status

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User


def _seed_auth_tenants(db_session):
    tenant_a = Tenant(name="Auth Tenant A", subdomain="auth-tenant-a")
    tenant_b = Tenant(name="Auth Tenant B", subdomain="auth-tenant-b")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin-a@example.test",
        password_hash="not-used-for-company-mismatch",
        role="admin",
    )
    staff_a = User(
        tenant_id=tenant_a.id,
        login="staff-a@example.test",
        password_hash="not-used-for-company-mismatch",
        role="staff",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin-b@example.test",
        password_hash="not-used-for-company-mismatch",
        role="admin",
    )
    db_session.add_all([admin_a, staff_a, admin_b])
    db_session.commit()
    return tenant_a, tenant_b, admin_a, staff_a, admin_b


def _headers(tenant, user):
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def test_mock_admin_token_is_rejected_for_admin_and_public_routes(client, db_session):
    tenant_a, *_ = _seed_auth_tenants(db_session)
    headers = {"X-Tenant": tenant_a.subdomain, "X-Token": "mock-admin-token"}

    admin_response = client.get("/api/admin/services", headers=headers)
    public_response = client.get("/api/public/services", headers=headers)

    assert admin_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert public_response.status_code == status.HTTP_401_UNAUTHORIZED


def test_missing_tenant_is_bad_request_even_when_tenants_exist(client, db_session):
    _, _, admin_a, _, _ = _seed_auth_tenants(db_session)

    response = client.get(
        "/api/admin/services",
        headers={"X-Token": create_access_token({"sub": str(admin_a.id)})},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Tenant subdomain is missing" in response.json()["error"]["message"]


def test_tenant_localhost_resolves_tenant_without_header_or_query(client, db_session):
    tenant_a, *_ = _seed_auth_tenants(db_session)

    response = client.get(
        "/api/public/services",
        headers={"Host": f"{tenant_a.subdomain}.localhost"},
    )

    assert response.status_code == status.HTTP_200_OK


def test_tenant_host_and_header_conflict_is_rejected(client, db_session):
    tenant_a, tenant_b, *_ = _seed_auth_tenants(db_session)

    response = client.get(
        "/api/public/services",
        headers={"Host": f"{tenant_a.subdomain}.localhost", "X-Tenant": tenant_b.subdomain},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "do not match" in response.json()["error"]["message"]


def test_root_two_label_host_cannot_impersonate_a_tenant(client, db_session):
    tenant_a, *_ = _seed_auth_tenants(db_session)

    response = client.get(
        "/api/public/services",
        headers={"Host": f"{tenant_a.subdomain}.example"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Tenant subdomain is missing" in response.json()["error"]["message"]


def test_valid_user_token_is_limited_to_its_resolved_tenant(client, db_session):
    tenant_a, tenant_b, admin_a, _, _ = _seed_auth_tenants(db_session)

    own_tenant_response = client.get("/api/admin/services", headers=_headers(tenant_a, admin_a))
    cross_tenant_response = client.get("/api/admin/services", headers=_headers(tenant_b, admin_a))

    assert own_tenant_response.status_code == status.HTTP_200_OK
    assert cross_tenant_response.status_code == status.HTTP_401_UNAUTHORIZED


def test_staff_token_is_forbidden_on_admin_route(client, db_session):
    tenant_a, _, _, staff_a, _ = _seed_auth_tenants(db_session)

    response = client.get("/api/admin/services", headers=_headers(tenant_a, staff_a))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_login_requires_company_to_match_resolved_tenant(client, db_session):
    tenant_a, tenant_b, admin_a, _, _ = _seed_auth_tenants(db_session)
    payload = {
        "company": tenant_b.subdomain,
        "login": admin_a.login,
        "password": "synthetic-admin-password",
    }

    response = client.post(
        "/api/admin/auth",
        json=payload,
        headers={"X-Tenant": tenant_a.subdomain},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "does not match the active tenant" in response.json()["error"]["message"]


def test_header_only_tenant_fallback_works_when_host_has_no_tenant(client, db_session):
    tenant_a, *_ = _seed_auth_tenants(db_session)

    response = client.get("/api/public/services", headers={"X-Tenant": tenant_a.subdomain})

    assert response.status_code == status.HTTP_200_OK
