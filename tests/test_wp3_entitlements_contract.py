"""Comprehensive contract and integration tests for WP3: Entitlements, Quotas, and Usage Metering.

Validates:
1. Server-side entitlement enforcement (blocks unpurchased modules with 403 EntitlementRequiredError).
2. Quota enforcement before protected operations begin (QuotaExceededError).
3. Usage deduplication: metered consumption recorded once; retries with same idempotency key do not double-count.
4. Expiring platform grants take precedence over subscription snapshot and expire safely.
5. Multi-tenant boundary: Tenant A cannot consume or inspect Tenant B's quotas or grants.
6. Tenant owners cannot arbitrarily elevate tier or grant quotas without platform owner privileges.
7. Authoritative projection: GET /api/admin/tenant/modules reflects EntitlementSnapshot and active grants.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import uuid
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.location import Location
from app.models.platform_billing import (
    BillingAccount,
    SubscriptionProjection,
    EntitlementSnapshot,
    PlatformEntitlementGrant,
    UsageEventOutbox,
)
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.models.user import User
from app.services.platform_billing.entitlement_guard import (
    EntitlementGuardService,
    EntitlementRequiredError,
    QuotaExceededError,
    ENTITLEMENT_ASSISTANT_ENABLED,
    ENTITLEMENT_ASSISTANT_MONTHLY_RUNS,
    ENTITLEMENT_SMS_ENABLED,
    ENTITLEMENT_SMS_MONTHLY_MESSAGES,
    ENTITLEMENT_PROVIDERS_MAX,
    ENTITLEMENT_LOCATIONS_MAX,
    ENTITLEMENT_API_ENABLED,
)
from app.services.platform_billing.projection_service import projection_service


# ---------------------------------------------------------------------------
# Test Helpers
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


def _seed_user(db_session: Session, tenant_id: int, login: str, role: str = "owner", is_platform_owner: bool = False) -> User:
    user = User(
        tenant_id=tenant_id,
        login=login,
        email=f"{login}@example.com",
        password_hash=get_password_hash("Password123!"),
        role=role,
        is_active=True,
        is_platform_owner=is_platform_owner,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user: User, tenant: Optional[Tenant] = None) -> dict:
    token = create_access_token(data={"sub": str(user.id), "tenant_id": user.tenant_id, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}
    if tenant and hasattr(tenant, "subdomain") and tenant.subdomain:
        headers["X-Tenant"] = tenant.subdomain
    return headers


# ---------------------------------------------------------------------------
# 1. Server-Side Entitlement Enforcement
# ---------------------------------------------------------------------------

def test_server_side_entitlement_enforcement_blocks_unpurchased_modules(db_session: Session, client: TestClient):
    """Attempting to enable a module without prerequisite entitlement is blocked with 403."""
    tenant = _seed_tenant(db_session, "entitle-test", tier="starter")
    user = _seed_user(db_session, tenant.id, "owner-entitle", role="owner")
    headers = _auth_headers(user, tenant)

    # Set starter entitlement snapshots: locations.max = 1 (cannot enable locations module)
    db_session.add(EntitlementSnapshot(
        tenant_id=tenant.id,
        entitlement_key="locations.max",
        value_type="numeric",
        value="1",
        is_active=True,
    ))
    db_session.add(EntitlementSnapshot(
        tenant_id=tenant.id,
        entitlement_key="sms.enabled",
        value_type="boolean",
        value="false",
        is_active=True,
    ))
    db_session.commit()

    # Attempting to toggle locations module with locations.max <= 1 fails with 403
    resp_loc = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "locations", "enabled": True},
        headers=headers,
    )
    assert resp_loc.status_code == status.HTTP_403_FORBIDDEN
    assert "locations.max > 1" in resp_loc.json()["detail"]

    # Attempting to toggle sms_assistant with sms.enabled = false fails with 403
    resp_sms = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "sms_assistant", "enabled": True},
        headers=headers,
    )
    assert resp_sms.status_code == status.HTTP_403_FORBIDDEN
    assert "sms.enabled" in resp_sms.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Quota Enforcement Before Protected Operations
# ---------------------------------------------------------------------------

def test_quota_enforcement_stateful_providers_and_locations(db_session: Session, client: TestClient):
    """Enforcing providers.max and locations.max limits before creation."""
    tenant = _seed_tenant(db_session, "quota-state-test", tier="starter")
    user = _seed_user(db_session, tenant.id, "owner-quota", role="owner")
    headers = _auth_headers(user, tenant)

    # Explicit entitlement snapshot: providers.max = 2, locations.max = 1
    db_session.add(EntitlementSnapshot(
        tenant_id=tenant.id,
        entitlement_key="providers.max",
        value_type="numeric",
        value="2",
        is_active=True,
    ))
    db_session.add(EntitlementSnapshot(
        tenant_id=tenant.id,
        entitlement_key="locations.max",
        value_type="numeric",
        value="1",
        is_active=True,
    ))
    db_session.commit()

    # Create 1st provider -> succeeds
    p1 = Provider(tenant_id=tenant.id, name="Dr. First", active=True)
    db_session.add(p1)
    db_session.commit()

    # Create 2nd provider -> succeeds
    p2 = Provider(tenant_id=tenant.id, name="Dr. Second", active=True)
    db_session.add(p2)
    db_session.commit()

    # Verify check_quota reports limit reached (current=2, limit=2)
    assert EntitlementGuardService.check_quota(db_session, tenant.id, "providers.max", 1, raise_exception=False) is False
    with pytest.raises(QuotaExceededError) as exc_info:
        EntitlementGuardService.check_quota(db_session, tenant.id, "providers.max", 1, raise_exception=True)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    # Attempting to create location when limit is 1 and 1 already exists
    loc1 = Location(tenant_id=tenant.id, name="Main Clinic", active=True)
    db_session.add(loc1)
    db_session.commit()

    # API create location should be blocked by check_quota
    resp_loc = client.post(
        "/api/admin/locations",
        json={"name": "Second Branch", "address": "123 Test St"},
        headers=headers,
    )
    assert resp_loc.status_code == status.HTTP_403_FORBIDDEN


def test_quota_enforcement_metered_consumption(db_session: Session):
    """Enforcing metered consumption limit on outbound SMS and assistant runs."""
    tenant = _seed_tenant(db_session, "quota-meter-test", tier="starter")

    # Set quota snapshot: 100 SMS messages
    db_session.add(EntitlementSnapshot(
        tenant_id=tenant.id,
        entitlement_key="sms.monthly_outbound_messages",
        value_type="numeric",
        value="100",
        is_active=True,
    ))
    db_session.commit()

    # Record 99 SMS usage events
    now = datetime.now(timezone.utc)
    for i in range(99):
        EntitlementGuardService.record_usage_with_deduplication(
            db=db_session,
            tenant_id=tenant.id,
            meter_key="sms_outbound",
            quantity=1,
            idempotency_key=f"sms:{tenant.id}:batch_{i}",
            occurred_at=now,
        )

    # 100th SMS is allowed
    assert EntitlementGuardService.check_quota(db_session, tenant.id, "sms.monthly_outbound_messages", 1) is True

    # Record the 100th SMS
    EntitlementGuardService.record_usage_with_deduplication(
        db=db_session,
        tenant_id=tenant.id,
        meter_key="sms_outbound",
        quantity=1,
        idempotency_key=f"sms:{tenant.id}:batch_99",
        occurred_at=now,
    )

    # 101st SMS exceeds quota and raises QuotaExceededError
    with pytest.raises(QuotaExceededError) as exc_info:
        EntitlementGuardService.check_quota(db_session, tenant.id, "sms.monthly_outbound_messages", 1, raise_exception=True)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 3. Usage Deduplication Guarantee
# ---------------------------------------------------------------------------

def test_usage_deduplication_guarantee(db_session: Session):
    """Repeated calls with identical idempotency key return existing record and do not double-count."""
    tenant = _seed_tenant(db_session, "dedup-test")
    now = datetime.now(timezone.utc)
    idempotency_key = f"meter:{tenant.id}:unique_turn_12345"

    # Initial record
    rec1 = EntitlementGuardService.record_usage_with_deduplication(
        db=db_session,
        tenant_id=tenant.id,
        meter_key="assistant_runs",
        quantity=1,
        idempotency_key=idempotency_key,
        occurred_at=now,
    )
    assert rec1.id is not None
    assert rec1.quantity == 1

    # Duplicate submission with same idempotency key
    rec2 = EntitlementGuardService.record_usage_with_deduplication(
        db=db_session,
        tenant_id=tenant.id,
        meter_key="assistant_runs",
        quantity=1,
        idempotency_key=idempotency_key,
        occurred_at=now,
    )
    assert rec2.id == rec1.id

    # Total recorded quantity in database is exactly 1, not 2
    total_quantity = (
        db_session.query(UsageEventOutbox)
        .filter(UsageEventOutbox.idempotency_key == idempotency_key)
        .count()
    )
    assert total_quantity == 1


# ---------------------------------------------------------------------------
# 4. Platform Grants Precedence and Safe Expiration
# ---------------------------------------------------------------------------

def test_platform_grants_precedence_and_safe_expiration(db_session: Session):
    """PlatformEntitlementGrant overrides base subscription snapshot and safely expires."""
    tenant = _seed_tenant(db_session, "grant-test", tier="starter")
    now = datetime.now(timezone.utc)

    # Base snapshot: assistant.enabled = False
    db_session.add(EntitlementSnapshot(
        tenant_id=tenant.id,
        entitlement_key="assistant.enabled",
        value_type="boolean",
        value="false",
        is_active=True,
    ))
    db_session.commit()

    # Before grant: assistant.enabled is False
    assert EntitlementGuardService.has_entitlement(db_session, tenant.id, "assistant.enabled") is False

    # Platform operator issues temporary grant expiring in 1 hour
    grant = EntitlementGuardService.create_platform_grant(
        db=db_session,
        tenant_id=tenant.id,
        entitlement_key="assistant.enabled",
        granted_value="true",
        value_type="boolean",
        expires_at=now + timedelta(hours=1),
        reason="VIP customer trial grant",
    )
    assert grant.id is not None

    # Active grant overrides base snapshot -> True
    assert EntitlementGuardService.has_entitlement(db_session, tenant.id, "assistant.enabled") is True

    # Fast-forward / expire the grant
    grant.expires_at = now - timedelta(minutes=5)
    db_session.commit()

    # Expired grant is ignored; reverts to base snapshot -> False
    assert EntitlementGuardService.has_entitlement(db_session, tenant.id, "assistant.enabled") is False

    # Re-activate grant with future expiry, then manually revoke
    grant.expires_at = now + timedelta(hours=2)
    grant.is_revoked = True
    db_session.commit()

    # Revoked grant is ignored -> False
    assert EntitlementGuardService.has_entitlement(db_session, tenant.id, "assistant.enabled") is False


# ---------------------------------------------------------------------------
# 5. Multi-Tenant Boundary Isolation
# ---------------------------------------------------------------------------

def test_multi_tenant_quota_and_entitlement_isolation(db_session: Session):
    """Tenant A's consumption and grants cannot affect Tenant B's limits or usage."""
    tenant_a = _seed_tenant(db_session, "tenant-a", tier="starter")
    tenant_b = _seed_tenant(db_session, "tenant-b", tier="starter")

    # Set quota snapshots: 50 runs for each
    for t in (tenant_a, tenant_b):
        db_session.add(EntitlementSnapshot(
            tenant_id=t.id,
            entitlement_key="assistant.monthly_runs",
            value_type="numeric",
            value="50",
            is_active=True,
        ))
    db_session.commit()

    # Tenant A consumes all 50 runs
    now = datetime.now(timezone.utc)
    for i in range(50):
        EntitlementGuardService.record_usage_with_deduplication(
            db=db_session,
            tenant_id=tenant_a.id,
            meter_key="assistant_runs",
            quantity=1,
            idempotency_key=f"tenant_a_run_{i}",
            occurred_at=now,
        )

    # Tenant A has exhausted their quota
    assert EntitlementGuardService.check_quota(db_session, tenant_a.id, "assistant.monthly_runs", 1, raise_exception=False) is False

    # Tenant B has consumed 0 runs and has full quota available
    usage_b = EntitlementGuardService.get_current_usage(db_session, tenant_b.id, "assistant.monthly_runs")
    assert usage_b == 0
    assert EntitlementGuardService.check_quota(db_session, tenant_b.id, "assistant.monthly_runs", 1, raise_exception=True) is True

    # Platform grant given to Tenant A does not bleed to Tenant B
    EntitlementGuardService.create_platform_grant(
        db=db_session,
        tenant_id=tenant_a.id,
        entitlement_key="api.enabled",
        granted_value="true",
        value_type="boolean",
    )
    assert EntitlementGuardService.has_entitlement(db_session, tenant_a.id, "api.enabled") is True
    assert EntitlementGuardService.has_entitlement(db_session, tenant_b.id, "api.enabled") is False


# ---------------------------------------------------------------------------
# 6. Tenant Owner Cannot Arbitrarily Elevate Tiers or Quotas
# ---------------------------------------------------------------------------

def test_tenant_owner_cannot_arbitrarily_elevate_tiers(db_session: Session, client: TestClient):
    """Business owners cannot manipulate subscription tier or quota endpoints."""
    tenant = _seed_tenant(db_session, "tier-hack-test", tier="starter")
    user = _seed_user(db_session, tenant.id, "owner-tier", role="owner", is_platform_owner=False)
    headers = _auth_headers(user, tenant)

    # Owner attempts to change tier to unlimited via PUT /api/admin/tenant/modules/tier
    resp1 = client.put(
        "/api/admin/tenant/modules/tier",
        json={"tier": "unlimited", "addon_quota": 999},
        headers=headers,
    )
    assert resp1.status_code == status.HTTP_403_FORBIDDEN
    assert "Platform owner privilege required" in resp1.json()["detail"]

    # Owner attempts to pass tier override via PUT /api/admin/tenant/modules
    resp2 = client.put(
        "/api/admin/tenant/modules",
        json={"tier": "unlimited", "addon_quota": 999},
        headers=headers,
    )
    assert resp2.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# 7. Authoritative Projection & GET Harmonization
# ---------------------------------------------------------------------------

def test_get_tenant_modules_projection_harmonization(db_session: Session, client: TestClient):
    """GET /api/admin/tenant/modules accurately returns EntitlementSnapshot and active grants."""
    tenant = _seed_tenant(db_session, "projection-test", tier="starter")
    user = _seed_user(db_session, tenant.id, "owner-proj", role="owner")
    headers = _auth_headers(user, tenant)

    # Seed snapshot
    db_session.add(EntitlementSnapshot(
        tenant_id=tenant.id,
        entitlement_key="sms.enabled",
        value_type="boolean",
        value="true",
        is_active=True,
    ))
    db_session.add(EntitlementSnapshot(
        tenant_id=tenant.id,
        entitlement_key="sms.monthly_outbound_messages",
        value_type="numeric",
        value="500",
        is_active=True,
    ))
    # Seed active platform grant
    db_session.add(PlatformEntitlementGrant(
        tenant_id=tenant.id,
        entitlement_key="api.enabled",
        value_type="boolean",
        granted_value="true",
        reason="Partner integration test",
        is_revoked=False,
    ))
    db_session.commit()

    resp = client.get("/api/admin/tenant/modules", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert "entitlements" in data
    entitlements = data["entitlements"]
    assert "sms.enabled" in entitlements
    assert entitlements["sms.enabled"]["value"] == "true"
    assert entitlements["sms.enabled"]["is_active"] is True
    assert "api.enabled" in entitlements
    assert entitlements["api.enabled"]["value"] == "true"
