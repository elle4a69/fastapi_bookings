"""End-to-End QA Suite: Manual Takeover Priority, Epoch Invalidation & Concurrency Leasing.

Verifies:
1. Manual Takeover Priority:
   - User takeover ("I'll do this part") immediately increments plan control_epoch.
   - Audited reason and actor recorded in OnboardingAuditLog.
2. Control Epoch Invalidation:
   - Stale control epoch validation fails with StaleControlEpochError.
   - Late agent writes carrying older control epochs are rejected.
   - API endpoints reject stale epoch payloads.
3. Single-Tab Active Executor Leasing:
   - Active executor lease token registration and validation.
   - Secondary tab attempting to execute with mismatched lease raises LeaseExpiredError.
   - Empty/blank lease token rejected.
   - API lease endpoint raises HTTP 409 Conflict when a second tab attempts to hijack active lease.
4. Concurrency & Monotonic State Protection:
   - Multiple sequential takeovers strictly increment control_epoch monotonically.
   - In-flight writes with past epochs cannot overwrite subsequent user edits.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.main import app as fastapi_app
from app.models.tenant import Tenant
from app.models.user import User
from app.models.onboarding import OnboardingAuditLog, OnboardingPlan, OnboardingStep
from app.services.business_assistant.onboarding import (
    LeaseExpiredError,
    OnboardingPlanService,
    StaleControlEpochError,
)
from app.services.business_assistant.onboarding.tools import OnboardingToolPack


@pytest.fixture
def db_session():
    """In-memory SQLite session with full models registered."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    tenant = Tenant(
        id=1,
        name="Canine Couture Grooming",
        subdomain="couture",
        email="info@couturegrooming.com.au",
        phone="0395551234",
    )
    session.add(tenant)
    session.flush()

    user = User(
        id=1,
        tenant_id=1,
        login="couture_owner",
        password_hash="fakehash",
        email="owner@couturegrooming.com.au",
        role="owner",
    )
    session.add(user)
    session.commit()

    yield session
    session.close()


@pytest.fixture
def test_client(db_session):
    """FastAPI TestClient with overridden get_db fixture."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(fastapi_app)
    yield client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(db_session):
    """Generate headers with valid X-Tenant and JWT access token."""
    tenant = db_session.query(Tenant).filter(Tenant.id == 1).first()
    user = db_session.query(User).filter(User.id == 1).first()
    token = create_access_token({"sub": str(user.id), "tenant_id": tenant.id})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


class TestManualTakeoverPriorityQA:
    """Verifies manual takeover takes immediate precedence and increments control epoch."""

    def test_manual_takeover_increments_epoch_and_audits(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        initial_epoch = plan.control_epoch
        assert initial_epoch == 1

        # User clicks "I will do this part"
        updated_plan = OnboardingPlanService.record_manual_takeover(
            db=db_session,
            plan=plan,
            reason="User clicked 'I will do this part'",
        )

        assert updated_plan.control_epoch == initial_epoch + 1
        assert updated_plan.control_epoch == 2

        # Verify audit log entry
        audit = (
            db_session.query(OnboardingAuditLog)
            .filter(
                OnboardingAuditLog.plan_id == plan.id,
                OnboardingAuditLog.action == "manual_takeover",
            )
            .first()
        )
        assert audit is not None
        assert audit.actor == "user"
        assert audit.details["new_control_epoch"] == 2
        assert "I will do this part" in audit.details["reason"]

    def test_manual_takeover_via_api_endpoint(self, test_client, auth_headers, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        assert plan.control_epoch == 1

        response = test_client.post(
            f"/api/business-assistant/onboarding/plan/{plan.id}/takeover",
            headers=auth_headers,
            json={"reason": "User opened manual modal"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["control_epoch"] == 2


class TestControlEpochInvalidationQA:
    """Verifies late agent writes with stale control epochs are strictly rejected."""

    def test_validate_control_epoch_raises_stale_error(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Advance epoch to 3 via 2 takeovers
        OnboardingPlanService.record_manual_takeover(db_session, plan, reason="Takeover 1")
        OnboardingPlanService.record_manual_takeover(db_session, plan, reason="Takeover 2")
        assert plan.control_epoch == 3

        # Validation with current epoch succeeds
        OnboardingPlanService.validate_control_epoch(plan, 3)

        # Validation with stale epoch (1 or 2) fails
        with pytest.raises(StaleControlEpochError) as exc_info:
            OnboardingPlanService.validate_control_epoch(plan, 1)

        assert exc_info.value.expected_epoch == 3
        assert exc_info.value.received_epoch == 1

        with pytest.raises(StaleControlEpochError) as exc_info2:
            OnboardingPlanService.validate_control_epoch(plan, 2)

        assert exc_info2.value.expected_epoch == 3
        assert exc_info2.value.received_epoch == 2

    def test_onboarding_tool_pack_rejects_stale_epoch_write(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        OnboardingPlanService.record_manual_takeover(db_session, plan, reason="Takeover")
        assert plan.control_epoch == 2

        # Toolpack configured with stale epoch 1
        stale_tools = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
            control_epoch=1,
        )

        with pytest.raises(StaleControlEpochError):
            stale_tools.stage_fields(
                step_id="step_1_identity",
                fields={"business_name": "Late Agent Name"},
            )

    def test_api_stage_endpoint_rejects_stale_epoch(self, test_client, auth_headers, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        OnboardingPlanService.record_manual_takeover(db_session, plan, reason="Takeover")
        assert plan.control_epoch == 2

        # Attempt to stage with stale epoch 1
        response = test_client.post(
            f"/api/business-assistant/onboarding/plan/{plan.id}/step/step_1_identity/stage",
            headers=auth_headers,
            json={
                "fields": {"business_name": "Stale Payload"},
                "control_epoch": 1,
            },
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        body = response.json()
        assert "STALE_CONTROL_EPOCH" in str(body) or "stale" in str(body).lower()


class TestSingleTabActiveExecutorLeasingQA:
    """Verifies single-tab active executor leasing, lease expiration, and conflict rejection."""

    def test_lease_validation_permits_matching_and_rejects_mismatch(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(
            db=db_session,
            tenant_id=1,
            user_id=1,
            lease_token="tab-alpha-token-111",
        )

        # Matching lease passes
        OnboardingPlanService.validate_lease(plan, "tab-alpha-token-111")

        # Blank/empty lease token raises LeaseExpiredError
        with pytest.raises(LeaseExpiredError):
            OnboardingPlanService.validate_lease(plan, "")

        with pytest.raises(LeaseExpiredError):
            OnboardingPlanService.validate_lease(plan, "   ")

        # Conflicting/mismatched secondary tab token raises LeaseExpiredError
        with pytest.raises(LeaseExpiredError) as exc_info:
            OnboardingPlanService.validate_lease(plan, "tab-beta-token-222")

        assert exc_info.value.lease_token == "tab-beta-token-222"

    def test_tool_pack_enforces_lease_token(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(
            db=db_session,
            tenant_id=1,
            user_id=1,
            lease_token="tab-alpha-token-111",
        )

        # Valid lease toolpack succeeds
        valid_tools = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
            lease_token="tab-alpha-token-111",
        )
        res = valid_tools.stage_fields(
            step_id="step_1_identity",
            fields={"business_name": "Valid Tab Grooming"},
        )
        assert res["status"] == "ok"

        # Invalid lease toolpack fails
        invalid_tools = OnboardingToolPack(
            db=db_session,
            tenant_id=1,
            user_id=1,
            lease_token="tab-beta-token-222",
        )
        with pytest.raises(LeaseExpiredError):
            invalid_tools.stage_fields(
                step_id="step_1_identity",
                fields={"business_name": "Sneaky Tab Grooming"},
            )

    def test_api_lease_endpoint_rejects_competing_tab_with_conflict(
        self, test_client, auth_headers, db_session
    ):
        plan = OnboardingPlanService.get_or_create_plan(
            db=db_session,
            tenant_id=1,
            user_id=1,
            lease_token="lease-tab-1-original",
        )

        # Competing tab attempts to assert a different lease
        response = test_client.post(
            f"/api/business-assistant/onboarding/plan/{plan.id}/lease",
            headers=auth_headers,
            json={"lease_token": "lease-tab-2-intruder"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        error_code = (
            data.get("error", {}).get("code")
            or data.get("detail", {}).get("error_code")
            or str(data)
        )
        assert "LEASE_CONFLICT" in error_code


class TestMonotonicEpochProtectionQA:
    """Verifies monotonic epoch protection under repeated takeovers and concurrent commands."""

    def test_monotonic_epoch_progression(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        epochs = [plan.control_epoch]

        for i in range(5):
            OnboardingPlanService.record_manual_takeover(
                db=db_session,
                plan=plan,
                reason=f"Takeover {i+1}",
            )
            epochs.append(plan.control_epoch)

        # Must be strictly monotonically increasing: [1, 2, 3, 4, 5, 6]
        assert epochs == [1, 2, 3, 4, 5, 6]
        for idx in range(len(epochs) - 1):
            assert epochs[idx] < epochs[idx + 1]
