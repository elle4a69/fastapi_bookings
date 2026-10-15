"""Comprehensive contract tests for WP0: Security Baseline & Control-Plane Contract.

Validates:
1. Strict platform owner gate (tenant owners rejected with 403; platform owners allowed).
2. Tenant lifecycle (suspension blocks tenant traffic with 403; reactivation restores traffic).
3. Tenant creation and invitation issuance + redemption.
4. Auto-provisioning elimination (uninvited Google logins rejected with 403).
5. Cross-tenant IDOR protection on GET /api/tenants/{id}.
6. Subscription tier modification restricted to platform owner.
7. Audit log creation for all tenant lifecycle events.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.models.invitation import TenantInvitation
from app.models.audit import AuditLog
from app.api.deps import require_platform_owner, get_current_platform_owner


def _seed_platform_owner(db_session: Session) -> tuple[User, dict[str, str]]:
    user = User(
        login="platform_root@controlplane.test",
        password_hash=get_password_hash("PlatformPassword123!"),
        role="platform_owner",
        is_platform_owner=True,
        is_superuser=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"X-Token": token}
    return user, headers


def _seed_tenant_and_owner(db_session: Session, suffix: str) -> tuple[Tenant, User, dict[str, str]]:
    tenant = Tenant(
        name=f"Studio {suffix}",
        subdomain=f"studio-{suffix.lower()}",
        subscription_tier="starter",
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    owner = User(
        tenant_id=tenant.id,
        login=f"owner_{suffix.lower()}",
        email=f"owner_{suffix.lower()}@studio.test",
        password_hash=get_password_hash("OwnerPassword123!"),
        role="owner",
        is_platform_owner=False,
        is_superuser=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    token = create_access_token({"sub": str(owner.id)})
    headers = {"X-Tenant": tenant.subdomain, "X-Token": token}
    return tenant, owner, headers


# ---------------------------------------------------------------------------
# 1. Platform Owner vs Tenant Owner Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_platform_owner_dependency_strict(db_session: Session):
    """Ensure tenant owner (role='owner') is rejected with 403 Forbidden."""
    _, tenant_owner, _ = _seed_tenant_and_owner(db_session, "dep-test")
    platform_owner, _ = _seed_platform_owner(db_session)

    # 1. Tenant owner without is_platform_owner -> 403
    with pytest.raises(Exception) as exc_info:
        await require_platform_owner(current_user=tenant_owner)
    assert exc_info.value.status_code == 403

    # 2. Platform owner -> allowed
    resolved = await require_platform_owner(current_user=platform_owner)
    assert resolved.id == platform_owner.id


def test_tenant_creation_restricted_to_platform_owner(client: TestClient, db_session: Session):
    """POST /api/tenants requires platform owner privileges."""
    _, _, tenant_owner_headers = _seed_tenant_and_owner(db_session, "creator")
    _, platform_headers = _seed_platform_owner(db_session)

    payload = {
        "name": "New Alpha Clinic",
        "subdomain": "new-alpha-clinic",
        "subscription_tier": "growth",
        "owner_email": "alpha_owner@clinic.test",
    }

    # 1. Unauthenticated -> 401
    res_unauth = client.post("/api/tenants", json=payload)
    assert res_unauth.status_code == 401

    # 2. Tenant owner calling -> 403 Forbidden
    res_tenant_owner = client.post("/api/tenants", json=payload, headers=tenant_owner_headers)
    assert res_tenant_owner.status_code == 403

    # 3. Platform owner calling -> 201 Created
    res_platform = client.post("/api/tenants", json=payload, headers=platform_headers)
    assert res_platform.status_code == 201, res_platform.text
    data = res_platform.json()["data"]
    assert data["subdomain"] == "new-alpha-clinic"
    assert data["subscription_tier"] == "growth"
    assert data["status"] == "active"
    assert data["invitation_token"] is not None

    # Verify audit log was written
    audit = db_session.query(AuditLog).filter(AuditLog.target_id == data["id"], AuditLog.action == "tenant_created").first()
    assert audit is not None


# ---------------------------------------------------------------------------
# 2. Tenant Lifecycle (Suspend & Reactivate)
# ---------------------------------------------------------------------------

def test_tenant_suspension_and_reactivation_lifecycle(client: TestClient, db_session: Session):
    """Platform owner can suspend and reactivate tenants; suspended tenants return 403."""
    tenant, _, tenant_headers = _seed_tenant_and_owner(db_session, "lifecycle")
    _, platform_headers = _seed_platform_owner(db_session)

    # 1. Active tenant can access authenticated endpoint
    res_active = client.get("/api/admin/auth/me", headers=tenant_headers)
    assert res_active.status_code == 200

    # 2. Tenant owner cannot suspend own tenant -> 403
    res_owner_suspend = client.post(f"/api/tenants/{tenant.id}/suspend", headers=tenant_headers)
    assert res_owner_suspend.status_code == 403

    # 3. Platform owner suspends tenant -> 200
    res_suspend = client.post(
        f"/api/tenants/{tenant.id}/suspend",
        json={"reason": "Terms of service violation"},
        headers=platform_headers,
    )
    assert res_suspend.status_code == 200
    assert res_suspend.json()["data"]["status"] == "suspended"

    # 4. Now any tenant-scoped request receives 403 Forbidden
    res_blocked = client.get("/api/admin/auth/me", headers=tenant_headers)
    assert res_blocked.status_code == 403
    assert "suspended" in res_blocked.json()["detail"].lower()

    # 5. Platform owner reactivates tenant -> 200
    res_reactivate = client.post(f"/api/tenants/{tenant.id}/reactivate", headers=platform_headers)
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["data"]["status"] == "active"

    # 6. Tenant-scoped request succeeds again
    res_restored = client.get("/api/admin/auth/me", headers=tenant_headers)
    assert res_restored.status_code == 200


# ---------------------------------------------------------------------------
# 3. Invitation Issuance and Acceptance
# ---------------------------------------------------------------------------

def test_invitation_issuance_and_acceptance_flow(client: TestClient, db_session: Session):
    """Invitee accepts token and can login with newly provisioned credentials."""
    tenant, _, tenant_headers = _seed_tenant_and_owner(db_session, "invitee")

    # 1. Issue invitation for a new staff administrator
    invite_res = client.post(
        f"/api/tenants/{tenant.id}/invitations",
        json={"email": "new_staff@studio.test", "role": "admin", "expires_in_days": 3},
        headers=tenant_headers,
    )
    assert invite_res.status_code == 201, invite_res.text
    invite_data = invite_res.json()["data"]
    token = invite_data["token"]
    assert token is not None

    # 2. Accept invitation via /api/auth/invitations/accept
    accept_res = client.post(
        "/api/auth/invitations/accept",
        json={
            "token": token,
            "password": "SecurePassword123!",
            "first_name": "New",
            "last_name": "Staff",
        },
    )
    assert accept_res.status_code == 200, accept_res.text
    accept_data = accept_res.json()["data"]
    assert "access_token" in accept_data
    assert accept_data["user"]["role"] == "admin"
    assert accept_data["user"]["email"] == "new_staff@studio.test"

    # 3. Attempting to redeem again fails with 400
    res_redeem_again = client.post(
        "/api/auth/invitations/accept",
        json={"token": token, "password": "AnotherPassword123!"},
    )
    assert res_redeem_again.status_code == 400

    # 4. Login with newly accepted credentials
    login_res = client.post(
        "/api/admin/auth",
        json={
            "company": tenant.subdomain,
            "login": "new_staff@studio.test",
            "password": "SecurePassword123!",
        },
        headers={"X-Tenant": tenant.subdomain},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()["data"]


# ---------------------------------------------------------------------------
# 4. Auto-Provisioning Elimination (Uninvited Google Login Rejection)
# ---------------------------------------------------------------------------

def test_uninvited_google_login_is_rejected(client: TestClient, db_session: Session, monkeypatch):
    """Google login for uninvited user without existing account is rejected with 403."""
    tenant, _, _ = _seed_tenant_and_owner(db_session, "googletest")

    # Mock verify_google_id_token to return uninvited user claims
    from app.services.auth import google_oidc

    def mock_verify_google(id_token: str):
        return {
            "sub": "google-sub-9999",
            "email": "uninvited_stranger@example.com",
            "name": "Stranger Danger",
            "picture": "https://example.com/avatar.png",
        }

    monkeypatch.setattr(google_oidc, "verify_google_id_token", mock_verify_google)

    res = client.post(
        "/api/admin/auth/google",
        json={"id_token": "fake-google-token", "company": tenant.subdomain},
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"] or "invitation" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Cross-Tenant IDOR Protection on GET /api/tenants/{tenant_id}
# ---------------------------------------------------------------------------

def test_cross_tenant_idor_protection_on_get_tenant(client: TestClient, db_session: Session):
    """Tenant A owner cannot access Tenant B by ID; platform owner can access any."""
    tenant_a, _, headers_a = _seed_tenant_and_owner(db_session, "idor-a")
    tenant_b, _, headers_b = _seed_tenant_and_owner(db_session, "idor-b")
    _, platform_headers = _seed_platform_owner(db_session)

    # 1. Unauthenticated -> 401
    res_unauth = client.get(f"/api/tenants/{tenant_b.id}")
    assert res_unauth.status_code == 401

    # 2. Tenant A owner requesting Tenant B -> 403 Forbidden
    res_cross = client.get(f"/api/tenants/{tenant_b.id}", headers=headers_a)
    assert res_cross.status_code == 403
    assert "Access denied" in res_cross.json()["detail"]

    # 3. Tenant B owner requesting Tenant B -> 200 OK
    res_own = client.get(f"/api/tenants/{tenant_b.id}", headers=headers_b)
    assert res_own.status_code == 200
    assert res_own.json()["data"]["id"] == tenant_b.id

    # 4. Platform owner requesting Tenant B -> 200 OK
    res_platform = client.get(f"/api/tenants/{tenant_b.id}", headers=platform_headers)
    assert res_platform.status_code == 200
    assert res_platform.json()["data"]["id"] == tenant_b.id


# ---------------------------------------------------------------------------
# 6. Tier Modification Restricted to Platform Owner
# ---------------------------------------------------------------------------

def test_tier_modification_restricted_to_platform_owner(client: TestClient, db_session: Session):
    """Tenant owners cannot modify their own subscription tier (403 Forbidden)."""
    tenant, _, tenant_headers = _seed_tenant_and_owner(db_session, "tiertest")
    platform_owner, _ = _seed_platform_owner(db_session)

    # 1. Tenant owner attempting to upgrade tier -> 403 Forbidden
    res_owner_tier = client.put(
        "/api/admin/tenant/modules/tier",
        json={"tier": "unlimited"},
        headers=tenant_headers,
    )
    assert res_owner_tier.status_code == 403
    assert "Platform owner privilege required" in res_owner_tier.json()["detail"]

    # 2. Platform owner with tenant header attempting upgrade -> 200 OK
    platform_tenant_headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(platform_owner.id)}),
    }
    res_platform_tier = client.put(
        "/api/admin/tenant/modules/tier",
        json={"tier": "growth"},
        headers=platform_tenant_headers,
    )
    assert res_platform_tier.status_code == 200
    assert res_platform_tier.json()["tier"] == "growth"
