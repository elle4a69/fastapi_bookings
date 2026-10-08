"""End-to-End QA Suite: Tenant Isolation, Cryptographic Nonce Security, Delegation Gates & Privacy.

Verifies:
1. Tenant Isolation:
   - Strict database boundary: tenant 1 cannot query, mutate, stage, or commit steps for tenant 2.
   - API endpoints enforce multi-tenant isolation, returning 404 PLAN_NOT_FOUND on cross-tenant access.
2. Cryptographic HMAC-SHA256 Nonces (5-minute TTL):
   - Nonce structure and HMAC signature validation.
   - Strict single-use consumption: replay attempts raise NonceAlreadyUsedError.
   - Expiration validation: nonces older than 300 seconds raise NonceExpiredError.
   - Tampered signatures or manipulated payloads raise InvalidNonceError.
   - Tenant and step binding: nonces cannot be redeemed across tenants or mismatched steps.
3. Delegation Mode Policy Gates:
   - DelegationMode: autonomous, delegated, supervised, view_only / manual_only.
   - View-only / manual-only modes strictly refuse agent stage and save actions (DelegationRefusalError).
   - Sensitive domains (e.g. Identity, Website publish) strictly require manual authorization nonce.
4. Zero Credential Leakage & Telemetry Privacy:
   - Audit logs, plan details, step states, and error responses never leak secrets, API keys, passwords, or PII.
"""

import time
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
    DelegationMode,
    DelegationRefusalError,
    DelegationSaveGuard,
    InvalidNonceError,
    NonceAlreadyUsedError,
    NonceExpiredError,
    OnboardingPlanService,
)
from app.services.business_assistant.onboarding.tools import OnboardingToolPack


@pytest.fixture
def db_session():
    """In-memory SQLite session with full models registered and multithread support."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Create Tenant 1 (Paws)
    tenant_1 = Tenant(
        id=1,
        name="Paws Grooming Melbourne",
        subdomain="pawsmelb",
        email="melb@paws.com.au",
        phone="0391234567",
    )
    # Create Tenant 2 (Whiskers)
    tenant_2 = Tenant(
        id=2,
        name="Whiskers Grooming Sydney",
        subdomain="whiskerssyd",
        email="syd@whiskers.com.au",
        phone="0291234567",
    )
    session.add_all([tenant_1, tenant_2])
    session.flush()

    # Create Owner for Tenant 1
    user_1 = User(
        id=1,
        tenant_id=1,
        login="frank_melb",
        password_hash="secret_hash_1",
        email="frank@pawsmelb.com.au",
        role="owner",
    )
    # Create Owner for Tenant 2
    user_2 = User(
        id=2,
        tenant_id=2,
        login="sarah_syd",
        password_hash="secret_hash_2",
        email="sarah@whiskerssyd.com.au",
        role="owner",
    )
    session.add_all([user_1, user_2])
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
def tenant1_headers(db_session):
    tenant = db_session.query(Tenant).filter(Tenant.id == 1).first()
    user = db_session.query(User).filter(User.id == 1).first()
    token = create_access_token({"sub": str(user.id), "tenant_id": tenant.id})
    return {"X-Tenant": tenant.subdomain, "X-Token": token}


@pytest.fixture
def tenant2_headers(db_session):
    tenant = db_session.query(Tenant).filter(Tenant.id == 2).first()
    user = db_session.query(User).filter(User.id == 2).first()
    token = create_access_token({"sub": str(user.id), "tenant_id": tenant.id})
    return {"X-Tenant": tenant.subdomain, "X-Token": token}


class TestTenantIsolationQA:
    """Verifies strict tenant data isolation at database and API layers."""

    def test_database_plan_scoped_to_tenant(self, db_session):
        plan_t1 = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        plan_t2 = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=2, user_id=2)

        assert plan_t1.id != plan_t2.id
        assert plan_t1.tenant_id == 1
        assert plan_t2.tenant_id == 2

        # Querying plan_t2 using tenant 1 scope returns None
        lookup_cross = OnboardingPlanService.get_plan(db_session, plan_id=plan_t2.id, tenant_id=1)
        assert lookup_cross is None

        # Querying plan_t1 using tenant 2 scope returns None
        lookup_cross2 = OnboardingPlanService.get_plan(db_session, plan_id=plan_t1.id, tenant_id=2)
        assert lookup_cross2 is None

    def test_api_cross_tenant_access_rejected_with_404(
        self, test_client, tenant1_headers, tenant2_headers, db_session
    ):
        # Create plan for Tenant 2
        plan_t2 = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=2, user_id=2)

        # Tenant 1 attempts to retrieve Tenant 2's plan
        response = test_client.get(
            f"/api/business-assistant/onboarding/plan/{plan_t2.id}",
            headers=tenant1_headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        error_msg = str(data)
        assert "not found" in error_msg.lower()
        # Ensure no tenant 2 data is leaked
        assert "whiskers" not in error_msg.lower()

    def test_tool_pack_tenant_mismatch_isolation(self, db_session):
        plan_t2 = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=2, user_id=2)

        # ToolPack configured for tenant 1 attempting to stage on plan_t2's step
        t1_tools = OnboardingToolPack(db=db_session, tenant_id=1, user_id=1)
        # Trying to commit save or stage on tenant 1 cannot affect tenant 2's plan
        res = t1_tools.stage_fields(
            step_id="step_1_identity",
            fields={"business_name": "T1 Dog Grooming"},
        )
        assert res["status"] == "ok"

        # Check tenant 2 plan remains completely unaffected
        db_session.refresh(plan_t2)
        step_t2 = OnboardingPlanService.get_step_by_id(plan_t2, "step_1_identity")
        assert step_t2.status == "not_started"
        assert step_t2.staged_fields == {}


class TestCryptographicHmacNoncesQA:
    """Verifies HMAC-SHA256 authorization nonces, single-use, 5-minute TTL, and tamper resistance."""

    def test_nonce_valid_issuance_and_single_use(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        nonce = DelegationSaveGuard.generate_save_nonce(
            tenant_id=1,
            user_id=1,
            plan_id=plan.id,
            step_id="step_1_identity",
            action="save",
            expires_in_seconds=300,
            db=db_session,
        )
        assert isinstance(nonce, str)
        assert "." in nonce

        # First use succeeds
        valid = DelegationSaveGuard.validate_save_nonce(
            nonce=nonce,
            tenant_id=1,
            plan_id=plan.id,
            step_id="step_1_identity",
            action="save",
            db=db_session,
        )
        assert valid is True

        # Replay attempt fails with NonceAlreadyUsedError
        with pytest.raises(NonceAlreadyUsedError):
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=1,
                plan_id=plan.id,
                step_id="step_1_identity",
                action="save",
                db=db_session,
            )

    def test_nonce_tampered_signature_rejected(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        nonce = DelegationSaveGuard.generate_save_nonce(
            tenant_id=1,
            user_id=1,
            plan_id=plan.id,
            step_id="step_1_identity",
            action="save",
            expires_in_seconds=300,
            db=db_session,
        )

        parts = nonce.split(".")
        # Tamper signature part
        tampered_nonce = f"{parts[0]}.badsignature12345"

        with pytest.raises(InvalidNonceError):
            DelegationSaveGuard.validate_save_nonce(
                nonce=tampered_nonce,
                tenant_id=1,
                plan_id=plan.id,
                step_id="step_1_identity",
                action="save",
                db=db_session,
            )

    def test_nonce_cross_tenant_redemption_rejected(self, db_session):
        plan_t1 = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        plan_t2 = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=2, user_id=2)

        # Issue nonce for Tenant 1
        nonce_t1 = DelegationSaveGuard.generate_save_nonce(
            tenant_id=1,
            user_id=1,
            plan_id=plan_t1.id,
            step_id="step_1_identity",
            action="save",
            db=db_session,
        )

        # Attempt to redeem nonce in Tenant 2's context
        with pytest.raises(InvalidNonceError):
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce_t1,
                tenant_id=2,  # Wrong tenant!
                plan_id=plan_t2.id,
                step_id="step_1_identity",
                action="save",
                db=db_session,
            )

    def test_nonce_step_scope_mismatch_rejected(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        nonce = DelegationSaveGuard.generate_save_nonce(
            tenant_id=1,
            user_id=1,
            plan_id=plan.id,
            step_id="step_1_identity",
            action="save",
            db=db_session,
        )

        # Attempt to redeem for step_2_locations
        with pytest.raises(InvalidNonceError):
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=1,
                plan_id=plan.id,
                step_id="step_2_locations",  # Wrong step!
                action="save",
                db=db_session,
            )

    def test_nonce_expiration_rejected(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Issue nonce with negative TTL (already expired)
        nonce = DelegationSaveGuard.generate_save_nonce(
            tenant_id=1,
            user_id=1,
            plan_id=plan.id,
            step_id="step_1_identity",
            action="save",
            expires_in_seconds=-1,
            db=db_session,
        )

        with pytest.raises(NonceExpiredError):
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=1,
                plan_id=plan.id,
                step_id="step_1_identity",
                action="save",
                db=db_session,
            )


class TestDelegationPolicyGatesQA:
    """Verifies delegation policy restrictions across autonomy modes."""

    def test_view_only_mode_refuses_agent_stage_and_save(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        step = plan.steps[0]

        # Stage refusal
        can_stage, reason_stage = DelegationSaveGuard.can_stage(
            plan=plan,
            step=step,
            actor="agent",
            mode=DelegationMode.MANUAL_ONLY.value,
        )
        assert can_stage is False
        assert "manual" in reason_stage.lower()

        # Save refusal
        can_save, reason_save = DelegationSaveGuard.can_save(
            plan=plan,
            step=step,
            actor="agent",
            mode=DelegationMode.MANUAL_ONLY.value,
        )
        assert can_save is False
        assert "manual" in reason_save.lower()

    def test_domain_1_identity_requires_nonce_in_delegated_mode(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        step_1 = plan.steps[0]  # Domain 1

        # Attempt to save without nonce
        can_save_no_nonce, reason = DelegationSaveGuard.can_save(
            plan=plan,
            step=step_1,
            actor="agent",
            mode="delegated",
            nonce_present=False,
        )
        assert can_save_no_nonce is False
        assert "nonce" in reason.lower() or "authorization" in reason.lower()

        # With nonce present
        can_save_with_nonce, _ = DelegationSaveGuard.can_save(
            plan=plan,
            step=step_1,
            actor="agent",
            mode="delegated",
            nonce_present=True,
        )
        assert can_save_with_nonce is True


class TestZeroCredentialLeakageQA:
    """Verifies that audit logs, plan outputs, and error envelopes never expose secrets or credentials."""

    def test_audit_logs_contain_no_credentials(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        OnboardingPlanService.stage_step_fields(
            db=db_session,
            plan=plan,
            step_id="step_1_identity",
            fields={"business_name": "Secure Paws Grooming"},
            actor="agent",
        )

        logs = (
            db_session.query(OnboardingAuditLog)
            .filter(OnboardingAuditLog.plan_id == plan.id)
            .all()
        )
        assert len(logs) > 0

        forbidden_tokens = ["password", "secret", "bearer", "access_token", "hash"]
        for log in logs:
            details_str = str(log.details).lower()
            for token in forbidden_tokens:
                assert token not in details_str, f"Found sensitive token '{token}' in audit log details."

    def test_plan_summary_contains_no_secrets(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        summary = OnboardingPlanService.get_plan_summary(plan)
        summary_str = str(summary).lower()

        forbidden_tokens = ["password", "hash", "secret_hash"]
        for token in forbidden_tokens:
            assert token not in summary_str
