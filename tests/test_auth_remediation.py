"""Comprehensive test suite for authentication and multi-tenant security remediation.

Validates:
- AUTH-001: Deletion of mock-admin-token bypass from production backend
- AUTH-002: Rejection of forged/missing frontend tokens
- AUTH-003: Strict multi-tenant isolation, fail-closed tenant resolution, and admin auth rate limiting
- FE-001: Strict unauthenticated state handling
"""

from datetime import datetime, timedelta, timezone
from jose import jwt
import pytest
from fastapi import status

from app.models.tenant import Tenant
from app.models.user import User
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash


@pytest.fixture
def auth_test_data(db_session):
    """Seed two distinct tenants and users with distinct roles."""
    tenant_a = Tenant(name="Tenant Alpha", subdomain="tenant-alpha", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant Beta", subdomain="tenant-beta", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()
    db_session.refresh(tenant_a)
    db_session.refresh(tenant_b)

    p_hash = get_password_hash("SecretPassword123!")

    owner_a = User(tenant_id=tenant_a.id, login="owner_a@alpha.com", password_hash=p_hash, role="owner")
    admin_a = User(tenant_id=tenant_a.id, login="admin_a@alpha.com", password_hash=p_hash, role="admin")
    staff_a = User(tenant_id=tenant_a.id, login="staff_a@alpha.com", password_hash=p_hash, role="staff")

    owner_b = User(tenant_id=tenant_b.id, login="owner_b@beta.com", password_hash=p_hash, role="owner")
    admin_b = User(tenant_id=tenant_b.id, login="admin_b@beta.com", password_hash=p_hash, role="admin")

    db_session.add_all([owner_a, admin_a, staff_a, owner_b, admin_b])
    db_session.commit()
    db_session.refresh(owner_a)
    db_session.refresh(admin_a)
    db_session.refresh(staff_a)
    db_session.refresh(owner_b)
    db_session.refresh(admin_b)

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "owner_a": owner_a,
        "admin_a": admin_a,
        "staff_a": staff_a,
        "owner_b": owner_b,
        "admin_b": admin_b,
    }


def test_mock_admin_token_rejected_across_admin_routes(client, auth_test_data):
    """Ensure mock-admin-token is strictly rejected across all administrative route families."""
    tenant_sub = auth_test_data["tenant_a"].subdomain
    headers = {
        "X-Tenant": tenant_sub,
        "X-Token": "mock-admin-token",
    }

    endpoints = [
        ("GET", "/api/admin/bookings"),
        ("GET", "/api/admin/services"),
        ("GET", "/api/admin/providers"),
        ("GET", "/api/admin/clients"),
        ("GET", "/api/admin/locations"),
        ("POST", "/api/admin/users"),
    ]

    for method, path in endpoints:
        if method == "GET":
            res = client.get(path, headers=headers)
        else:
            res = client.post(path, json={"company": tenant_sub, "login": "new@alpha.com", "password": "pw", "role": "admin"}, headers=headers)
        
        assert res.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"Endpoint {method} {path} accepted mock-admin-token with status {res.status_code}: {res.text}"
        )
        data = res.json()
        assert data.get("ok") is False
        assert data.get("error", {}).get("code") == "UNAUTHORIZED"


def test_missing_token_rejected(client, auth_test_data):
    """Ensure missing X-Token receives 401 Unauthorized."""
    tenant_sub = auth_test_data["tenant_a"].subdomain
    headers = {"X-Tenant": tenant_sub}

    res = client.get("/api/admin/bookings", headers=headers)
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Missing access token"


def test_malformed_token_rejected(client, auth_test_data):
    """Ensure malformed or garbage tokens receive 401 Unauthorized."""
    tenant_sub = auth_test_data["tenant_a"].subdomain
    for bad_token in ["not-a-token", "a.b.c", "Bearer fake", "null", "undefined"]:
        res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": bad_token})
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert res.json()["error"]["message"] == "Invalid token"


def test_expired_token_rejected(client, auth_test_data):
    """Ensure expired JWT tokens are rejected with 401 Unauthorized."""
    tenant_sub = auth_test_data["tenant_a"].subdomain
    user = auth_test_data["admin_a"]

    # Create expired token
    expired_token = create_access_token(
        {"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(seconds=-60)
    )

    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": expired_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Invalid token"


def test_wrong_signature_token_rejected(client, auth_test_data):
    """Ensure tokens signed with a different key are rejected with 401 Unauthorized."""
    tenant_sub = auth_test_data["tenant_a"].subdomain
    user = auth_test_data["admin_a"]

    wrong_key_token = jwt.encode(
        {"sub": str(user.id), "role": user.role, "exp": datetime.utcnow() + timedelta(hours=1)},
        "completely-different-signing-secret-key-1234567890",
        algorithm="HS256"
    )

    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": wrong_key_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Invalid token"


def test_invalid_payload_sub_rejected(client, auth_test_data):
    """Ensure tokens with non-integer subject or missing subject receive 401."""
    tenant_sub = auth_test_data["tenant_a"].subdomain

    # Missing sub
    no_sub_token = create_access_token({"role": "admin"})
    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": no_sub_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Non-integer sub
    bad_sub_token = create_access_token({"sub": "not-an-integer", "role": "admin"})
    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": bad_sub_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Invalid token payload"


def test_jwt_standard_claims_verification(client, auth_test_data):
    """Ensure standard claims (iss, aud, exp, iat) are verified strictly (AUTH-004)."""
    tenant_sub = auth_test_data["tenant_a"].subdomain
    user = auth_test_data["admin_a"]
    now = datetime.now(timezone.utc)

    # 1. Invalid / mismatched issuer
    wrong_iss_token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iss": "untrusted-issuer",
            "aud": settings.JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": wrong_iss_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Invalid token"

    # 2. Invalid / mismatched audience
    wrong_aud_token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iss": settings.JWT_ISSUER,
            "aud": "wrong-audience-api",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": wrong_aud_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Invalid token"

    # 3. Missing issuer claim
    missing_iss_token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "aud": settings.JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": missing_iss_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Invalid token"

    # 4. Missing audience claim
    missing_aud_token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iss": settings.JWT_ISSUER,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": missing_aud_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Invalid token"

    # 5. Expired token (exp in past)
    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": expired_token})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "Invalid token"

    # 6. Valid standard claims token succeeds
    valid_token = create_access_token({"sub": str(user.id), "role": user.role})
    res_valid = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": valid_token})
    assert res_valid.status_code == status.HTTP_200_OK


def test_cross_tenant_token_rejected(client, auth_test_data):
    """Ensure a valid token for Tenant A fails authentication when presented against Tenant B."""
    tenant_b_sub = auth_test_data["tenant_b"].subdomain
    user_a = auth_test_data["owner_a"]

    # Valid token for User A (who belongs only to Tenant A)
    token_a = create_access_token({"sub": str(user_a.id), "role": user_a.role})

    # Present User A's token against Tenant B
    res = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_b_sub, "X-Token": token_a})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error"]["message"] == "User not found in this tenant"


def test_missing_tenant_fails_closed(client, auth_test_data):
    """Ensure missing tenant context rejects with 400 Bad Request instead of falling back to first tenant."""
    user_a = auth_test_data["owner_a"]
    token_a = create_access_token({"sub": str(user_a.id), "role": user_a.role})

    # Request without X-Tenant header or subdomain
    res = client.get("/api/admin/bookings", headers={"X-Token": token_a})
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Tenant subdomain is missing or invalid" in res.json()["error"]["message"]


def test_unknown_tenant_fails_closed(client, auth_test_data):
    """Ensure non-existent tenant subdomains reject with 404 Not Found."""
    user_a = auth_test_data["owner_a"]
    token_a = create_access_token({"sub": str(user_a.id), "role": user_a.role})

    res = client.get("/api/admin/bookings", headers={"X-Tenant": "non-existent-tenant-xyz", "X-Token": token_a})
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in res.json()["error"]["message"]


def test_staff_vs_admin_vs_owner_roles(client, auth_test_data, db_session):
    """Verify role boundaries: staff role receives 403 on admin-only endpoints while admin and owner succeed."""
    import asyncio
    from app.api.deps import get_current_user, get_current_admin
    from fastapi import HTTPException

    tenant = auth_test_data["tenant_a"]
    tenant_sub = tenant.subdomain
    staff_user = auth_test_data["staff_a"]
    admin_user = auth_test_data["admin_a"]
    owner_user = auth_test_data["owner_a"]

    staff_token = create_access_token({"sub": str(staff_user.id), "role": staff_user.role})
    admin_token = create_access_token({"sub": str(admin_user.id), "role": admin_user.role})
    owner_token = create_access_token({"sub": str(owner_user.id), "role": owner_user.role})

    # 1. Direct unit test of get_current_user vs get_current_admin dependencies
    user_resolved = asyncio.run(get_current_user(x_token=staff_token, tenant=tenant, db=db_session))
    assert user_resolved.id == staff_user.id
    assert user_resolved.role == "staff"

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_admin(current_user=user_resolved))
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Insufficient privileges"

    # Admin passes get_current_admin
    admin_resolved = asyncio.run(get_current_user(x_token=admin_token, tenant=tenant, db=db_session))
    admin_checked = asyncio.run(get_current_admin(current_user=admin_resolved))
    assert admin_checked.id == admin_user.id

    # Owner passes get_current_admin
    owner_resolved = asyncio.run(get_current_user(x_token=owner_token, tenant=tenant, db=db_session))
    owner_checked = asyncio.run(get_current_admin(current_user=owner_resolved))
    assert owner_checked.id == owner_user.id

    # 2. Staff is forbidden (403) from get_current_admin HTTP routes
    res_staff_read = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": staff_token})
    assert res_staff_read.status_code == status.HTTP_403_FORBIDDEN
    assert res_staff_read.json()["error"]["message"] == "Insufficient privileges"

    res_staff_create = client.post(
        "/api/admin/users",
        json={"company": tenant_sub, "login": "newstaff@alpha.com", "password": "password123", "role": "staff"},
        headers={"X-Tenant": tenant_sub, "X-Token": staff_token}
    )
    assert res_staff_create.status_code == status.HTTP_403_FORBIDDEN
    assert res_staff_create.json()["error"]["message"] == "Insufficient privileges"

    # 3. Admin can access get_current_admin routes (200)
    res_admin_read = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": admin_token})
    assert res_admin_read.status_code == status.HTTP_200_OK

    res_admin_create = client.post(
        "/api/admin/users",
        json={"company": tenant_sub, "login": "created_by_admin@alpha.com", "password": "password123", "role": "staff"},
        headers={"X-Tenant": tenant_sub, "X-Token": admin_token}
    )
    assert res_admin_create.status_code == status.HTTP_200_OK
    assert res_admin_create.json()["ok"] is True

    # 4. Owner can access get_current_admin routes (200)
    res_owner_read = client.get("/api/admin/bookings", headers={"X-Tenant": tenant_sub, "X-Token": owner_token})
    assert res_owner_read.status_code == status.HTTP_200_OK

    res_owner_create = client.post(
        "/api/admin/users",
        json={"company": tenant_sub, "login": "created_by_owner@alpha.com", "password": "password123", "role": "admin"},
        headers={"X-Tenant": tenant_sub, "X-Token": owner_token}
    )
    assert res_owner_create.status_code == status.HTTP_200_OK
    assert res_owner_create.json()["ok"] is True


def test_admin_auth_rate_limiting(client, auth_test_data):
    """Verify rate limiter triggers on rapid authentication attempts to /api/admin/auth."""
    tenant_sub = auth_test_data["tenant_a"].subdomain
    payload = {"company": tenant_sub, "login": "admin_a@alpha.com", "password": "wrong-password"}

    # Slowapi limit is 10/minute. Firing 15 requests in rapid succession should trigger 429 Too Many Requests.
    statuses = []
    for _ in range(15):
        res = client.post("/api/admin/auth", json=payload, headers={"X-Tenant": tenant_sub, "X-Forwarded-For": "198.51.100.42"})
        statuses.append(res.status_code)

    assert status.HTTP_429_TOO_MANY_REQUESTS in statuses, (
        f"Expected 429 Too Many Requests in rate limit test, got statuses: {statuses}"
    )


def test_public_tenant_resolution_and_validation(auth_test_data, db_session):
    """Test get_public_tenant validation behavior across public tokens, user tokens, and invalid tokens."""
    import asyncio
    from app.api.deps import get_public_tenant

    tenant_a = auth_test_data["tenant_a"]
    user_a = auth_test_data["owner_a"]
    user_b = auth_test_data["owner_b"]

    # 1. No token -> returns tenant
    res = asyncio.run(get_public_tenant(x_token=None, db=db_session, tenant=tenant_a))
    assert res.id == tenant_a.id

    # 2. Public token with matching subdomain
    public_token = create_access_token({"sub": tenant_a.subdomain})
    res = asyncio.run(get_public_tenant(x_token=public_token, db=db_session, tenant=tenant_a))
    assert res.id == tenant_a.id

    # 3. User token belonging to tenant
    user_token = create_access_token({"sub": str(user_a.id)})
    res = asyncio.run(get_public_tenant(x_token=user_token, db=db_session, tenant=tenant_a))
    assert res.id == tenant_a.id

    # 4. User token belonging to different tenant (User B does not belong to Tenant A)
    user_b_token = create_access_token({"sub": str(user_b.id)})
    res = asyncio.run(get_public_tenant(x_token=user_b_token, db=db_session, tenant=tenant_a))
    assert res.id == tenant_a.id


def test_admin_auth_success_and_failure(client, auth_test_data):
    """Test administrative login endpoint with correct vs incorrect credentials."""
    tenant_sub = auth_test_data["tenant_a"].subdomain

    # Correct credentials
    res_valid = client.post(
        "/api/admin/auth",
        json={"company": tenant_sub, "login": "admin_a@alpha.com", "password": "SecretPassword123!"},
        headers={"X-Tenant": tenant_sub}
    )
    assert res_valid.status_code == status.HTTP_200_OK
    valid_data = res_valid.json()
    assert valid_data["ok"] is True
    assert "access_token" in valid_data["data"]

    # Incorrect password
    res_invalid_pw = client.post(
        "/api/admin/auth",
        json={"company": tenant_sub, "login": "admin_a@alpha.com", "password": "WrongPassword!"},
        headers={"X-Tenant": tenant_sub}
    )
    assert res_invalid_pw.status_code == status.HTTP_401_UNAUTHORIZED

    # Mismatched company in request body
    res_bad_company = client.post(
        "/api/admin/auth",
        json={"company": "wrong-company", "login": "admin_a@alpha.com", "password": "SecretPassword123!"},
        headers={"X-Tenant": tenant_sub}
    )
    assert res_bad_company.status_code == status.HTTP_400_BAD_REQUEST

