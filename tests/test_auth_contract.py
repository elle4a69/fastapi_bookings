"""Regression contract tests for tenant-specific administrative access."""

from fastapi import status
from pydantic import ValidationError
import pytest

from app.core.security import create_access_token, decode_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


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


@pytest.mark.parametrize("schema", [UserCreate, UserUpdate])
@pytest.mark.parametrize("privileged_key", ["is_platform_owner", "is_superuser"])
def test_public_user_schemas_forbid_privileged_extra_fields(schema, privileged_key):
    payload = {privileged_key: True}
    if schema is UserCreate:
        payload.update(company="synthetic", login="synthetic", password="synthetic-password")
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_admin_user_creation_persists_platform_authority_false(client, db_session):
    tenant_a, _, admin_a, _, _ = _seed_auth_tenants(db_session)
    response = client.post(
        "/api/admin/users",
        headers=_headers(tenant_a, admin_a),
        json={
            "company": tenant_a.subdomain,
            "login": "new-owner-synthetic",
            "password": "synthetic-password",
            "role": "owner",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    created = db_session.query(User).filter(User.login == "new-owner-synthetic").one()
    assert created.is_platform_owner is False
    assert "is_platform_owner" not in response.json()["data"]


def test_first_google_user_owner_role_does_not_imply_platform_authority(
    client,
    db_session,
    monkeypatch,
):
    tenant = Tenant(name="Google Synthetic", subdomain="google-synthetic")
    db_session.add(tenant)
    db_session.commit()
    monkeypatch.setattr(
        "app.services.auth.google_oidc.verify_google_id_token",
        lambda _token: {
            "sub": "synthetic-google-sub",
            "email": "first.user@example.test",
            "name": "Synthetic User",
        },
    )
    response = client.post(
        "/api/admin/auth/google",
        headers={"X-Tenant": tenant.subdomain},
        json={"id_token": "synthetic-id-token", "company": tenant.subdomain},
    )
    assert response.status_code == status.HTTP_200_OK
    created = db_session.query(User).filter(User.tenant_id == tenant.id).one()
    assert created.role == "owner"
    assert created.is_platform_owner is False
    token = response.json()["data"]["access_token"]
    assert "is_platform_owner" not in decode_access_token(token)
    assert "is_platform_owner" not in response.json()["data"]["user"]


def test_auth_me_and_tokens_do_not_expose_platform_capability(client, db_session):
    tenant_a, _, admin_a, _, _ = _seed_auth_tenants(db_session)
    admin_a.is_platform_owner = True
    db_session.commit()
    token = create_access_token(
        {"sub": str(admin_a.id), "tenant_id": tenant_a.id, "role": admin_a.role}
    )
    assert "is_platform_owner" not in decode_access_token(token)
    response = client.get(
        "/api/admin/auth/me",
        headers={"X-Tenant": tenant_a.subdomain, "X-Token": token},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "is_platform_owner" not in response.json()["data"]
