"""Comprehensive API contract tests for WP4: Tenant-Facing and Platform-Facing UX Endpoints.

Validates:
1. Tenant Subscription & Usage Overview:
   - GET /api/billing/subscription returns plan details, status, billing cycle, past_due flag,
     and computed usage quotas & capabilities.
   - Enforces strict tenant isolation: Tenant A cannot inspect Tenant B's subscription or quotas.
2. Tenant Hosted Portal Session:
   - POST /api/billing/portal-session requires tenant owner role; non-owners get 403.
3. Platform Operator Security Boundary:
   - All /api/admin/platform/billing/* endpoints reject regular tenant owners/admins (403 Forbidden).
   - Valid platform owner can access all operator endpoints.
4. Platform Operator Tenant Overview & Diagnostics:
   - GET /api/admin/platform/billing/tenants lists all tenants with plan, status, and health indicators.
   - GET /api/admin/platform/billing/tenants/{tenant_id}/diagnostics returns full diagnostics.
5. Platform Operator Event Inbox & Dead-Letter Queue:
   - GET /api/admin/platform/billing/inbox retrieves incoming events and failure filters.
   - POST /api/admin/platform/billing/inbox/{event_id}/retry retries failed events.
6. Platform Operator Grants Lifecycle:
   - POST /api/admin/platform/billing/grants creates explicit, expiring, audited grants with mandatory reason.
   - GET /api/admin/platform/billing/grants lists active/historical grants.
   - DELETE /api/admin/platform/billing/grants/{grant_id} revokes an active grant.
7. Platform Reconciliation:
   - POST /api/admin/platform/billing/reconcile triggers synchronization.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.location import Location
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.models.user import User
from app.models.platform_billing import (
    BillingAccount,
    SubscriptionProjection,
    EntitlementSnapshot,
    PlatformEntitlementGrant,
    ProviderEventInbox,
)


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------

def _seed_tenant(db_session: Session, slug: str, tier: str = "starter") -> Tenant:
    tenant = Tenant(
        name=f"Clinic {slug.upper()}",
        subdomain=f"clinic-{slug.lower()}",
        subscription_tier=tier,
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_user(db_session: Session, tenant_id: int, login: str, role: str = "owner") -> User:
    user = User(
        login=login,
        email=f"{login}@example.com",
        password_hash=get_password_hash("Password123!"),
        role=role,
        tenant_id=tenant_id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_platform_owner(db_session: Session) -> User:
    po = User(
        login="platform_super",
        email="platform_super@example.com",
        password_hash=get_password_hash("Password123!"),
        role="platform_owner",
        is_platform_owner=True,
        is_superuser=True,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(po)
    db_session.commit()
    db_session.refresh(po)
    return po


# ---------------------------------------------------------------------------
# 1. Tenant Subscription & Usage Overview
# ---------------------------------------------------------------------------

def test_tenant_subscription_overview_contract(client: TestClient, db_session: Session):
    """GET /api/billing/subscription returns plan, status, billing cycle, quotas, and capabilities."""
    tenant = _seed_tenant(db_session, "tenantux1", tier="starter")
    user = _seed_user(db_session, tenant.id, "ux_user1", role="owner")
    token = create_access_token(data={"sub": str(user.id), "tenant_id": tenant.id})

    # Add active locations and providers to test usage counting
    loc = Location(tenant_id=tenant.id, name="Main Office", active=True)
    db_session.add(loc)
    prov = Provider(tenant_id=tenant.id, name="Dr. Alice", active=True)
    db_session.add(prov)
    db_session.commit()

    resp = client.get(
        "/api/billing/subscription",
        headers={"Authorization": f"Bearer {token}", "X-Tenant": tenant.subdomain},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["plan_name"] == "Starter"
    assert data["status"] == "active"
    assert data["billing_cycle"] == "monthly"
    assert data["is_past_due"] is False

    # Check quotas
    quotas = data["usage_quotas"]
    assert "locations.max" in quotas
    assert quotas["locations.max"]["current_usage"] == 1
    assert quotas["locations.max"]["limit"] == 1

    assert "providers.max" in quotas
    assert quotas["providers.max"]["current_usage"] == 1
    assert quotas["providers.max"]["limit"] == 2

    assert "sms.monthly_outbound_messages" in quotas
    assert quotas["sms.monthly_outbound_messages"]["limit"] == 100

    # Check capabilities
    caps = data["capabilities"]
    assert caps["sms.enabled"] is True
    assert caps["assistant.enabled"] is False  # starter plan default


def test_tenant_subscription_isolation(client: TestClient, db_session: Session):
    """Tenant A cannot inspect or access Tenant B's subscription projection."""
    tenant_a = _seed_tenant(db_session, "isouxa", tier="starter")
    tenant_b = _seed_tenant(db_session, "isouxb", tier="pro")
    user_a = _seed_user(db_session, tenant_a.id, "user_iso_a", role="owner")
    token_a = create_access_token(data={"sub": str(user_a.id), "tenant_id": tenant_a.id})

    # Requesting as tenant A with tenant B header must fail
    resp = client.get(
        "/api/billing/subscription",
        headers={"Authorization": f"Bearer {token_a}", "X-Tenant": tenant_b.subdomain},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_tenant_past_due_status_and_banner(client: TestClient, db_session: Session):
    """When subscription projection is past_due, is_past_due is True."""
    tenant = _seed_tenant(db_session, "pastdue1", tier="pro")
    user = _seed_user(db_session, tenant.id, "past_user", role="owner")
    token = create_access_token(data={"sub": str(user.id), "tenant_id": tenant.id})

    # Seed past_due projection
    proj = SubscriptionProjection(
        tenant_id=tenant.id,
        external_subscription_id="sub_pastdue_test",
        plan_id="pro",
        plan_version=1,
        status="past_due",
        last_event_timestamp=datetime.now(timezone.utc),
        last_event_sequence=1,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    db_session.commit()

    resp = client.get(
        "/api/billing/subscription",
        headers={"Authorization": f"Bearer {token}", "X-Tenant": tenant.subdomain},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "past_due"
    assert data["is_past_due"] is True


# ---------------------------------------------------------------------------
# 2. Portal Session Role Authorization
# ---------------------------------------------------------------------------

def test_portal_session_requires_tenant_owner(client: TestClient, db_session: Session):
    """Non-owner (e.g. member/staff) cannot initiate billing portal sessions."""
    tenant = _seed_tenant(db_session, "portalauth", tier="starter")
    staff_user = _seed_user(db_session, tenant.id, "staff_user", role="member")
    token = create_access_token(data={"sub": str(staff_user.id), "tenant_id": tenant.id})

    resp = client.post(
        "/api/billing/portal-session",
        json={"return_url": "https://example.com/billing"},
        headers={"Authorization": f"Bearer {token}", "X-Tenant": tenant.subdomain},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 3. Platform Operator Security Boundary
# ---------------------------------------------------------------------------

def test_platform_operator_endpoints_reject_tenant_users(client: TestClient, db_session: Session):
    """Regular tenant owners cannot access any platform operator console endpoints."""
    tenant = _seed_tenant(db_session, "platsec1", tier="starter")
    tenant_owner = _seed_user(db_session, tenant.id, "regular_owner", role="owner")
    token = create_access_token(data={"sub": str(tenant_owner.id), "tenant_id": tenant.id})

    endpoints = [
        ("GET", "/api/admin/platform/billing/tenants"),
        ("GET", f"/api/admin/platform/billing/tenants/{tenant.id}/diagnostics"),
        ("GET", "/api/admin/platform/billing/inbox"),
        ("POST", "/api/admin/platform/billing/inbox/1/retry"),
        ("GET", "/api/admin/platform/billing/grants"),
        ("POST", "/api/admin/platform/billing/grants"),
        ("DELETE", "/api/admin/platform/billing/grants/1"),
        ("POST", "/api/admin/platform/billing/reconcile"),
    ]

    for method, path in endpoints:
        if method == "GET":
            resp = client.get(path, headers={"Authorization": f"Bearer {token}"})
        elif method == "POST":
            resp = client.post(path, json={}, headers={"Authorization": f"Bearer {token}"})
        elif method == "DELETE":
            resp = client.delete(path, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN), f"Failed for {method} {path}"


# ---------------------------------------------------------------------------
# 4. Platform Operator Tenant Overview & Diagnostics
# ---------------------------------------------------------------------------

def test_platform_operator_tenants_and_diagnostics(client: TestClient, db_session: Session):
    """Platform owner can list tenants and retrieve comprehensive billing diagnostics."""
    tenant = _seed_tenant(db_session, "diagtenant", tier="growth")
    po = _seed_platform_owner(db_session)
    po_token = create_access_token(data={"sub": str(po.id)})

    # List tenants
    resp = client.get(
        "/api/admin/platform/billing/tenants",
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    tenants_list = resp.json()
    assert any(t["tenant_id"] == tenant.id for t in tenants_list)

    # Get diagnostics
    diag_resp = client.get(
        f"/api/admin/platform/billing/tenants/{tenant.id}/diagnostics",
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert diag_resp.status_code == status.HTTP_200_OK
    diag = diag_resp.json()
    assert diag["tenant_id"] == tenant.id
    assert diag["tenant_name"] == tenant.name
    assert "usage_summary" in diag
    assert "active_grants" in diag


# ---------------------------------------------------------------------------
# 5. Platform Operator Event Inbox & Dead-Letter Retry
# ---------------------------------------------------------------------------

def test_platform_operator_inbox_and_retry(client: TestClient, db_session: Session):
    """Platform owner can view inbox events and retry failed ones."""
    po = _seed_platform_owner(db_session)
    po_token = create_access_token(data={"sub": str(po.id)})

    # Create failed event
    inbox_item = ProviderEventInbox(
        provider="flexprice",
        external_event_id="evt_failed_test_123",
        event_type="subscription.updated",
        payload_digest="abc123digest",
        processing_status="failed",
        retry_count=0,
        error_message="Simulated parsing error",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(inbox_item)
    db_session.commit()
    db_session.refresh(inbox_item)

    # List failed inbox events
    resp = client.get(
        "/api/admin/platform/billing/inbox?status_filter=failed",
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    events = resp.json()
    assert any(e["external_event_id"] == "evt_failed_test_123" for e in events)

    # Retry failed event
    retry_resp = client.post(
        f"/api/admin/platform/billing/inbox/{inbox_item.id}/retry",
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert retry_resp.status_code == status.HTTP_200_OK
    retried = retry_resp.json()
    assert retried["processing_status"] == "pending"
    assert retried["retry_count"] == 1
    assert retried["error_message"] is None


# ---------------------------------------------------------------------------
# 6. Platform Operator Grants Lifecycle
# ---------------------------------------------------------------------------

def test_platform_operator_grants_lifecycle(client: TestClient, db_session: Session):
    """Platform owner can create, list, and revoke audited entitlement grants."""
    tenant = _seed_tenant(db_session, "grantflow", tier="starter")
    po = _seed_platform_owner(db_session)
    po_token = create_access_token(data={"sub": str(po.id)})

    # 1. Create grant with valid reason
    expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    grant_payload = {
        "tenant_id": tenant.id,
        "entitlement_key": "assistant.enabled",
        "value_type": "boolean",
        "granted_value": "true",
        "expires_at": expiry,
        "reason": "VIP beta customer trial requested by executive team",
    }
    create_resp = client.post(
        "/api/admin/platform/billing/grants",
        json=grant_payload,
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    grant = create_resp.json()
    grant_id = grant["id"]
    assert grant["entitlement_key"] == "assistant.enabled"
    assert grant["is_active"] is True
    assert grant["reason"] == "VIP beta customer trial requested by executive team"

    # 2. List grants filtered by tenant
    list_resp = client.get(
        f"/api/admin/platform/billing/grants?tenant_id={tenant.id}",
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert list_resp.status_code == status.HTTP_200_OK
    grants = list_resp.json()
    assert any(g["id"] == grant_id for g in grants)

    # 3. Create grant without reason must fail (422)
    bad_grant = {
        "tenant_id": tenant.id,
        "entitlement_key": "locations.max",
        "value_type": "numeric",
        "granted_value": "10",
        "reason": "",
    }
    bad_resp = client.post(
        "/api/admin/platform/billing/grants",
        json=bad_grant,
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert bad_resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 4. Revoke grant
    del_resp = client.delete(
        f"/api/admin/platform/billing/grants/{grant_id}",
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert del_resp.status_code == status.HTTP_200_OK
    assert del_resp.json()["status"] == "revoked"

    # Verify grant is now revoked in list
    list_after = client.get(
        f"/api/admin/platform/billing/grants?tenant_id={tenant.id}",
        headers={"Authorization": f"Bearer {po_token}"},
    ).json()
    revoked_grant = next(g for g in list_after if g["id"] == grant_id)
    assert revoked_grant["is_revoked"] is True
    assert revoked_grant["is_active"] is False


# ---------------------------------------------------------------------------
# 7. Platform Operator Reconciliation
# ---------------------------------------------------------------------------

def test_platform_operator_reconcile_post(client: TestClient, db_session: Session):
    """POST /api/admin/platform/billing/reconcile triggers reconciliation."""
    tenant = _seed_tenant(db_session, "postreconcile", tier="starter")
    po = _seed_platform_owner(db_session)
    po_token = create_access_token(data={"sub": str(po.id)})

    resp = client.post(
        "/api/admin/platform/billing/reconcile",
        json={"tenant_id": tenant.id},
        headers={"Authorization": f"Bearer {po_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    reports = resp.json()
    assert isinstance(reports, list)
    assert len(reports) == 1
    assert reports[0]["tenant_id"] == tenant.id
