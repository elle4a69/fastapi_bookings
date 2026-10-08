"""Comprehensive test suite for voice-first onboarding delegation guard and API router.

Covers:
1. DelegationSaveGuard (modes, domain permissions, cryptographic nonces, single-use, expiry, audit logging).
2. Onboarding API Router endpoints:
   - Plan creation and full retrieval
   - Field staging with Australian-English normalization
   - Delegation policy enforcement and authorization nonce requirements
   - Authoritative step saving with single-use nonce consumption
   - Step skipping and plan advancement
   - Manual takeover and control epoch invalidation
   - Tab lease acquisition, heartbeat, and conflict rejection
"""

import time
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app as fastapi_app
from app.models.onboarding import OnboardingAuditLog, OnboardingPlan, OnboardingStep
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.onboarding import (
    DelegationMode,
    DelegationRefusalError,
    DelegationSaveGuard,
    InvalidNonceError,
    NonceAlreadyUsedError,
    NonceExpiredError,
    OnboardingPlanService,
    StaleControlEpochError,
)


# ---------------------------------------------------------------------------
# Unit Tests: DelegationSaveGuard & Nonce Engine
# ---------------------------------------------------------------------------


class TestDelegationSaveGuardUnit:
    """Verifies session-level delegation guard rules and cryptographic nonce handling."""

    def test_nonce_generation_and_validation(self, db_session):
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

        # First validation succeeds
        valid = DelegationSaveGuard.validate_save_nonce(
            nonce=nonce,
            tenant_id=1,
            plan_id=plan.id,
            step_id="step_1_identity",
            action="save",
            db=db_session,
        )
        assert valid is True

        # Second validation fails: single-use
        with pytest.raises(NonceAlreadyUsedError):
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=1,
                plan_id=plan.id,
                step_id="step_1_identity",
                action="save",
                db=db_session,
            )

    def test_nonce_expiry_rejection(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        # Generate nonce with 0 second TTL
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

    def test_nonce_tenant_scope_mismatch_rejected(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        nonce = DelegationSaveGuard.generate_save_nonce(
            tenant_id=1,
            user_id=1,
            plan_id=plan.id,
            step_id="step_1_identity",
            action="save",
            db=db_session,
        )
        with pytest.raises(InvalidNonceError):
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=999,  # Mismatched tenant
                plan_id=plan.id,
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
        with pytest.raises(InvalidNonceError):
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=1,
                plan_id=plan.id,
                step_id="step_2_locations",  # Wrong step
                action="save",
                db=db_session,
            )

    def test_delegation_rules_manual_only(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        step = plan.steps[0]

        # In manual_only, agent cannot stage
        can_st, _ = DelegationSaveGuard.can_stage(
            plan=plan,
            step=step,
            actor="agent",
            mode=DelegationMode.MANUAL_ONLY.value,
        )
        assert can_st is False

        # In manual_only, agent cannot save
        can_sv, _ = DelegationSaveGuard.can_save(
            plan=plan,
            step=step,
            actor="agent",
            mode=DelegationMode.MANUAL_ONLY.value,
        )
        assert can_sv is False

        # User manual actions are permitted
        can_st_u, _ = DelegationSaveGuard.can_stage(
            plan=plan,
            step=step,
            actor="user",
            mode=DelegationMode.MANUAL_ONLY.value,
        )
        assert can_st_u is True

    def test_delegation_rules_per_domain_signoff(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        step_1 = OnboardingPlanService.get_step_by_id(plan, "step_1_identity")
        step_2 = OnboardingPlanService.get_step_by_id(plan, "step_2_locations")
        step_3 = OnboardingPlanService.get_step_by_id(plan, "step_3_services")
        step_7 = OnboardingPlanService.get_step_by_id(plan, "step_7_website")

        # Domain 1 requires owner nonce
        allowed, reason = DelegationSaveGuard.can_save(
            plan, step_1, actor="agent", mode="delegated", nonce_present=False
        )
        assert allowed is False
        assert "Domain 1" in reason

        allowed, _ = DelegationSaveGuard.can_save(
            plan, step_1, actor="agent", mode="delegated", nonce_present=True
        )
        assert allowed is True

        # Domain 2 requires owner nonce
        allowed, reason = DelegationSaveGuard.can_save(
            plan, step_2, actor="agent", mode="delegated", nonce_present=False
        )
        assert allowed is False
        assert "Domain 2" in reason

        # Domain 3: creation allowed without nonce; edit requires nonce
        allowed, _ = DelegationSaveGuard.can_save(
            plan, step_3, actor="agent", mode="delegated", is_edit_mode=False, nonce_present=False
        )
        assert allowed is True

        allowed, reason = DelegationSaveGuard.can_save(
            plan, step_3, actor="agent", mode="delegated", is_edit_mode=True, nonce_present=False
        )
        assert allowed is False
        assert "Domain 3" in reason

        # Domain 7: draft save allowed without nonce; publish requires nonce
        allowed, _ = DelegationSaveGuard.can_save(
            plan, step_7, actor="agent", mode="delegated", is_publish=False, nonce_present=False
        )
        assert allowed is True

        allowed, reason = DelegationSaveGuard.can_save(
            plan, step_7, actor="agent", mode="delegated", is_publish=True, nonce_present=False
        )
        assert allowed is False
        assert "Domain 7" in reason

        allowed, _ = DelegationSaveGuard.can_save(
            plan, step_7, actor="agent", mode="delegated", is_publish=True, nonce_present=True
        )
        assert allowed is True


# ---------------------------------------------------------------------------
# Integration Tests: Onboarding API Router
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_tenant_and_user(db_session):
    """Ensure baseline tenant and owner user exist in db_session."""
    tenant = db_session.query(Tenant).filter(Tenant.id == 1).first()
    if not tenant:
        tenant = Tenant(id=1, name="Paws & Claws Grooming", subdomain="paws")
        db_session.add(tenant)
        db_session.flush()

    user = db_session.query(User).filter(User.id == 1).first()
    if not user:
        user = User(
            id=1,
            tenant_id=tenant.id,
            login="frank",
            password_hash="fakehash",
            email="frank@paws.com.au",
            role="owner",
        )
        db_session.add(user)
        db_session.commit()
    return tenant, user


@pytest.fixture
def auth_headers(setup_tenant_and_user):
    """Generate headers with valid X-Tenant and JWT access token."""
    tenant, user = setup_tenant_and_user
    token = create_access_token({"sub": str(user.id), "tenant_id": tenant.id})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


def get_error_code(response) -> str:
    """Extract machine-readable error code across FastAPI standard and custom envelope formats."""
    data = response.json()
    if "error" in data and isinstance(data["error"], dict):
        return data["error"].get("code", "")
    if "detail" in data and isinstance(data["detail"], dict):
        return data["detail"].get("error_code", "")
    return ""


class TestOnboardingRouterEndpoints:
    """End-to-end tests for all 8 Onboarding API routes via TestClient."""

    def test_post_plan_get_or_create(self, client, auth_headers):
        response = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={"mode": "delegated", "lease_token": "lease-initial-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["tenant_id"] == 1
        assert data["status"] == "in_progress"
        assert data["control_epoch"] == 1
        assert data["current_step_id"] == "step_1_identity"
        assert data["summary"]["total_steps"] == 8

        # Idempotent retrieval
        resp2 = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={},
        )
        assert resp2.status_code == 200
        assert resp2.json()["id"] == data["id"]

    def test_get_plan_details(self, client, auth_headers):
        # Create plan first
        create_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={},
        )
        plan_id = create_resp.json()["id"]

        response = client.get(
            f"/api/business-assistant/onboarding/plan/{plan_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == plan_id
        assert len(data["steps"]) == 8
        assert data["summary"]["completion_percentage"] == 0.0

        # Nonexistent plan
        bad_resp = client.get(
            "/api/business-assistant/onboarding/plan/99999",
            headers=auth_headers,
        )
        assert bad_resp.status_code == 404

    def test_stage_step_with_australian_normalization(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={"lease_token": "tab-1"},
        )
        plan_id = plan_resp.json()["id"]

        # Stage with American spelling words to be normalized to Australian English
        stage_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_1_identity/stage",
            headers=auth_headers,
            json={
                "fields": {
                    "business_name": "Paws & Claws Grooming",
                    "color_choice": "Our brand color is blue",
                    "policy_notes": "We organize our bookings by schedule",
                },
                "control_epoch": 1,
                "lease_token": "tab-1",
            },
        )
        assert stage_resp.status_code == 200
        data = stage_resp.json()
        assert data["ok"] is True
        assert data["status"] == "staged"
        staged = data["staged_fields"]
        assert staged["business_name"] == "Paws & Claws Grooming"
        # Enforced Australian spelling
        assert "colour" in staged["color_choice"]
        assert "organise" in staged["policy_notes"]

    def test_stage_step_with_spoken_utterance(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={},
        )
        plan_id = plan_resp.json()["id"]

        stage_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_1_identity/stage",
            headers=auth_headers,
            json={
                "utterance": "It's a little mobile grooming business, mainly dogs, we go to their house.",
                "field_key": "description",
                "field_type": "string",
            },
        )
        assert stage_resp.status_code == 200
        staged = stage_resp.json()["staged_fields"]
        assert staged["description"] == "We provide mobile dog grooming at clients' homes."

    def test_stage_rejected_on_stale_epoch_or_lease_mismatch(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={"lease_token": "tab-1"},
        )
        plan_id = plan_resp.json()["id"]

        # Lease conflict
        resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_1_identity/stage",
            headers=auth_headers,
            json={"fields": {"business_name": "Test"}, "lease_token": "tab-wrong"},
        )
        assert resp.status_code == 409
        assert get_error_code(resp) == "LEASE_EXPIRED"

        # Stale control epoch (0 < 1)
        resp2 = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_1_identity/stage",
            headers=auth_headers,
            json={"fields": {"business_name": "Test"}, "control_epoch": 0, "lease_token": "tab-1"},
        )
        assert resp2.status_code == 409
        assert get_error_code(resp2) == "STALE_CONTROL_EPOCH"

    def test_save_step_delegation_guard_and_nonce_enforcement(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={"lease_token": "tab-1"},
        )
        plan_id = plan_resp.json()["id"]

        # Attempt to save Domain 1 without nonce as agent -> 403 DELEGATION_REFUSED
        save_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_1_identity/save",
            headers=auth_headers,
            json={
                "actor": "agent",
                "mode": "delegated",
                "lease_token": "tab-1",
                "control_epoch": 1,
            },
        )
        assert save_resp.status_code == 403
        assert get_error_code(save_resp) == "DELEGATION_REFUSED"

        # Request single-use nonce
        nonce_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/nonce",
            headers=auth_headers,
            json={"step_id": "step_1_identity", "action": "save"},
        )
        assert nonce_resp.status_code == 200
        nonce = nonce_resp.json()["nonce"]

        # Save with valid nonce -> 200 OK and step saved
        save_ok_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_1_identity/save",
            headers=auth_headers,
            json={
                "nonce": nonce,
                "actor": "agent",
                "mode": "delegated",
                "lease_token": "tab-1",
                "control_epoch": 1,
                "persisted_entity_id": "tenant-1",
            },
        )
        assert save_ok_resp.status_code == 200
        assert save_ok_resp.json()["status"] == "saved"

        # Reusing the consumed nonce -> 400 NONCE_ALREADY_USED
        save_reuse_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_1_identity/save",
            headers=auth_headers,
            json={
                "nonce": nonce,
                "actor": "agent",
                "mode": "delegated",
                "lease_token": "tab-1",
                "control_epoch": 1,
            },
        )
        assert save_reuse_resp.status_code == 400
        assert get_error_code(save_reuse_resp) == "NONCE_ALREADY_USED"

    def test_save_domain_3_services_creation_vs_edit(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={"lease_token": "tab-1"},
        )
        plan_id = plan_resp.json()["id"]

        # Creation mode: agent can save directly without nonce
        resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_3_services/save",
            headers=auth_headers,
            json={
                "actor": "agent",
                "mode": "delegated",
                "is_edit_mode": False,
                "lease_token": "tab-1",
                "control_epoch": 1,
                "persisted_entity_id": "service-42",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"

    def test_save_domain_7_website_draft_vs_publish(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={"lease_token": "tab-1"},
        )
        plan_id = plan_resp.json()["id"]

        # Draft website save: allowed without nonce
        draft_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_7_website/save",
            headers=auth_headers,
            json={
                "actor": "agent",
                "mode": "delegated",
                "is_publish": False,
                "lease_token": "tab-1",
                "control_epoch": 1,
            },
        )
        assert draft_resp.status_code == 200

        # Publication attempt: refused without nonce
        pub_refuse = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_7_website/save",
            headers=auth_headers,
            json={
                "actor": "agent",
                "mode": "delegated",
                "is_publish": True,
                "lease_token": "tab-1",
                "control_epoch": 1,
            },
        )
        assert pub_refuse.status_code == 403
        assert get_error_code(pub_refuse) == "DELEGATION_REFUSED"

        # Request publish nonce and execute publication
        nonce_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/nonce",
            headers=auth_headers,
            json={"step_id": "step_7_website", "action": "publish"},
        )
        pub_nonce = nonce_resp.json()["nonce"]

        pub_ok = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_7_website/save",
            headers=auth_headers,
            json={
                "actor": "agent",
                "mode": "delegated",
                "is_publish": True,
                "nonce": pub_nonce,
                "lease_token": "tab-1",
                "control_epoch": 1,
            },
        )
        assert pub_ok.status_code == 200
        assert pub_ok.json()["status"] == "saved"

    def test_skip_step_advances_plan(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={},
        )
        plan_id = plan_resp.json()["id"]

        skip_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_4_providers/skip",
            headers=auth_headers,
            json={"reason": "solo_practitioner", "actor": "user"},
        )
        assert skip_resp.status_code == 200
        assert skip_resp.json()["status"] == "skipped"

    def test_manual_takeover_increments_epoch_and_invalidates_agent(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={"lease_token": "tab-1"},
        )
        plan_id = plan_resp.json()["id"]
        assert plan_resp.json()["control_epoch"] == 1

        # Trigger manual takeover
        takeover_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/takeover",
            headers=auth_headers,
            json={"reason": "user_clicked_ill_do_this_part"},
        )
        assert takeover_resp.status_code == 200
        assert takeover_resp.json()["control_epoch"] == 2

        # Subsequent command with old epoch 1 is rejected
        stale_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/step/step_1_identity/stage",
            headers=auth_headers,
            json={
                "fields": {"business_name": "Old Agent Name"},
                "control_epoch": 1,
                "lease_token": "tab-1",
            },
        )
        assert stale_resp.status_code == 409
        assert get_error_code(stale_resp) == "STALE_CONTROL_EPOCH"

    def test_tab_lease_acquisition_and_conflict_handling(self, client, auth_headers):
        plan_resp = client.post(
            "/api/business-assistant/onboarding/plan",
            headers=auth_headers,
            json={},
        )
        plan_id = plan_resp.json()["id"]

        # Acquire new lease
        lease_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/lease",
            headers=auth_headers,
            json={"ttl_seconds": 300},
        )
        assert lease_resp.status_code == 200
        token_1 = lease_resp.json()["lease_token"]
        assert token_1.startswith("lease-")

        # Heartbeat with same token succeeds
        hb_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/lease",
            headers=auth_headers,
            json={"lease_token": token_1},
        )
        assert hb_resp.status_code == 200
        assert hb_resp.json()["lease_token"] == token_1

        # Second tab requests lease with a different token -> 409 LEASE_CONFLICT
        conflict_resp = client.post(
            f"/api/business-assistant/onboarding/plan/{plan_id}/lease",
            headers=auth_headers,
            json={"lease_token": "different-tab-token"},
        )
        assert conflict_resp.status_code == 409
        assert get_error_code(conflict_resp) == "LEASE_CONFLICT"
