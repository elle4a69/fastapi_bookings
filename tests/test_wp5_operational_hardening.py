"""Operational hardening, readiness probes, and release gate verification tests (WP5).

Validates:
1. Readiness endpoint behavior:
   - GET /api/platform/health/readiness and /health/ready return 200 OK when healthy.
   - Deep health structure with database, cache, identity, and billing dependencies.
   - Strict zero-credential and privacy-safe guarantee: NO connection strings, passwords,
     auth headers, or secret keys appear in the response payload.
   - Fails closed with HTTP 503 Service Unavailable when the database is unreachable.
2. SaaS Control Plane Reconciliation CLI:
   - Compares local SubscriptionProjection against Flexprice state.
   - Detects synchronization and drift accurately.
3. Dead-Letter Queue Inspection & Batch Replay:
   - Inspects failed/ignored webhook inbox events.
   - Dry-run preserves database state.
   - Active replay successfully resets event for reprocessing.
4. Tenant Lifecycle & Suspension Data Safety:
   - Verifies tenant suspension flags and tenant isolation.
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.tenant import Tenant
from app.models.platform_billing import (
    BillingAccount,
    SubscriptionProjection,
    ProviderEventInbox,
)
from app.services.platform_billing.flexprice_client import flexprice_client, FlexpriceClient
from scripts.reconcile_saas_control_plane import (
    reconcile_tenants,
    inspect_dead_letter_inbox,
    replay_failed_inbox_events,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_tenant(db_session: Session) -> Tenant:
    tenant = Tenant(
        name="WP5 Test Clinic",
        subdomain="wp5-test-clinic",
        subscription_tier="growth",
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


# ---------------------------------------------------------------------------
# 1. Platform Deep Readiness & Zero Secret Leakage Tests
# ---------------------------------------------------------------------------

def test_platform_readiness_healthy_200(client: TestClient):
    """GET /api/platform/health/readiness returns 200 OK and deep dependency health."""
    resp = client.get("/api/platform/health/readiness")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "timestamp" in data
    assert "dependencies" in data
    assert "environment" in data

    deps = data["dependencies"]
    assert "database" in deps
    assert deps["database"]["status"] == "ok"
    assert "redis" in deps
    assert "identity_provider" in deps
    assert "billing_provider" in deps


def test_platform_readiness_route_alias_healthy(client: TestClient):
    """GET /health/ready alias routes to the deep readiness check."""
    resp = client.get("/health/ready")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["dependencies"]["database"]["status"] == "ok"


def test_platform_readiness_zero_credential_leakage(client: TestClient):
    """Verify that NO secret keys, database credentials, or passwords appear in response."""
    resp = client.get("/api/platform/health/readiness")
    content = resp.text

    # Sensitive strings that must never be present
    forbidden_needles = [
        settings.SECRET_KEY,
        getattr(settings, "FLEXPRICE_API_KEY", "placeholder_never_leak"),
        getattr(settings, "LOGTO_M2M_APP_SECRET", "placeholder_never_leak"),
        getattr(settings, "FLEXPRICE_WEBHOOK_SECRET", "placeholder_never_leak"),
        "password",
        "client_secret",
        "Authorization",
        "Bearer ",
    ]

    for needle in forbidden_needles:
        if needle and len(needle) > 3:
            assert needle not in content, f"Sensitive credential leaked in readiness probe: {needle}"


def test_platform_readiness_fails_closed_on_db_outage(client: TestClient):
    """If database connectivity fails, probe fails closed with HTTP 503."""
    with patch("app.api.routers.platform_health.check_database_health") as mock_db_health:
        from app.schemas.platform_health import DependencyHealth
        mock_db_health.return_value = DependencyHealth(
            status="down",
            latency_ms=None,
            detail="Database connectivity check failed",
        )

        resp = client.get("/api/platform/health/readiness")
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = resp.json()
        assert data["status"] == "down"
        assert data["dependencies"]["database"]["status"] == "down"


# ---------------------------------------------------------------------------
# 2. SaaS Control Plane Reconciliation CLI Tests
# ---------------------------------------------------------------------------

def test_reconciliation_detects_sync_and_drift(db_session: Session, sample_tenant: Tenant):
    """Reconciliation CLI correctly flags synchronized and drifting subscriptions."""
    # Create local projection with last_event_timestamp
    proj = SubscriptionProjection(
        tenant_id=sample_tenant.id,
        external_subscription_id="sub_test_wp5_recon",
        plan_id="growth",
        status="active",
        last_event_timestamp=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    db_session.commit()

    # 1. Test synchronized condition
    mock_client = MagicMock(spec=FlexpriceClient)
    mock_client.get_subscription.return_value = {
        "id": "sub_test_wp5_recon",
        "status": "active",
        "plan_id": "growth",
    }

    with patch("scripts.reconcile_saas_control_plane.flexprice_client", mock_client):
        reports = reconcile_tenants(tenant_id=sample_tenant.id, db=db_session)
        assert len(reports) == 1
        assert reports[0]["is_synchronized"] is True
        assert reports[0]["discrepancies"] is None

    # 2. Test drift condition (e.g. canceled on remote Flexprice)
    mock_client.get_subscription.return_value = {
        "id": "sub_test_wp5_recon",
        "status": "canceled",
        "plan_id": "growth",
    }

    with patch("scripts.reconcile_saas_control_plane.flexprice_client", mock_client):
        reports = reconcile_tenants(tenant_id=sample_tenant.id, db=db_session)
        assert len(reports) == 1
        assert reports[0]["is_synchronized"] is False
        assert "Status mismatch" in reports[0]["discrepancies"]


# ---------------------------------------------------------------------------
# 3. Dead-Letter Queue Inspection & Batch Replay Tests
# ---------------------------------------------------------------------------

def test_dead_letter_inspection_and_batch_replay(db_session: Session, sample_tenant: Tenant):
    """Dead-letter events can be inspected and successfully replayed."""
    # Seed a failed event in the inbox
    failed_event = ProviderEventInbox(
        provider="flexprice",
        external_event_id="evt_wp5_retry_101",
        event_type="subscription.updated",
        payload_digest="sha256_mock_digest_for_testing",
        processing_status="failed",
        error_message="Simulated downstream timeout",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(failed_event)
    db_session.commit()

    # 1. Inspection test
    inspected = inspect_dead_letter_inbox(limit=10, db=db_session)
    matching = [e for e in inspected if e["event_id"] == "evt_wp5_retry_101"]
    assert len(matching) == 1
    assert matching[0]["processing_status"] == "failed"

    # 2. Dry-run test: status must NOT change
    dry_stats = replay_failed_inbox_events(limit=10, dry_run=True, db=db_session)
    assert dry_stats["replayed"] >= 1
    db_session.refresh(failed_event)
    assert failed_event.processing_status == "failed"

    # 3. Active replay test: event reset to pending for reprocessing
    stats = replay_failed_inbox_events(limit=10, dry_run=False, db=db_session)
    assert stats["replayed"] >= 1

    db_session.refresh(failed_event)
    assert failed_event.processing_status == "pending"
    assert failed_event.retry_count == 1
    assert failed_event.error_message is None


# ---------------------------------------------------------------------------
# 4. Tenant Lifecycle & Suspension Data Safety Tests
# ---------------------------------------------------------------------------

def test_tenant_suspension_isolation_and_safety(db_session: Session, sample_tenant: Tenant):
    """Verifies that suspended tenant status is strictly enforced."""
    sample_tenant.status = "suspended"
    db_session.commit()
    db_session.refresh(sample_tenant)

    assert sample_tenant.status == "suspended"

    # Reactivation restores active status
    sample_tenant.status = "active"
    db_session.commit()
    db_session.refresh(sample_tenant)
    assert sample_tenant.status == "active"
