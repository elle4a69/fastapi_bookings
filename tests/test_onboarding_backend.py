"""Comprehensive tests for voice-first onboarding backend.

Covers:
1. SQLAlchemy Models (OnboardingPlan, OnboardingStep, OnboardingAuditLog, constraints, cascades)
2. Intent Normalizer (Australian spelling, numbers/units, ambiguity detection, corrections, synthesis)
3. Onboarding Planner Service (domain progression 1-8, staged != saved invariant, control epoch, leasing)
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.onboarding import (
    OnboardingAuditLog,
    OnboardingPlan,
    OnboardingStep,
)
from app.services.business_assistant.onboarding import (
    DOMAIN_CONFIGS,
    IntentNormalizer,
    LeaseExpiredError,
    OnboardingPlanService,
    StaleControlEpochError,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session with all models registered."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Create dummy Tenant and User
    tenant = Tenant(id=1, name="Paws & Claws Grooming", subdomain="paws")
    session.add(tenant)
    session.flush()

    user = User(
        id=1,
        tenant_id=tenant.id,
        login="frank",
        password_hash="fakehash",
        email="frank@paws.com.au",
        role="owner",
    )
    session.add(user)
    session.commit()

    yield session
    session.close()


class TestOnboardingModels:
    """Verifies schema structure, defaults, indexes, and cascades for onboarding models."""

    def test_create_onboarding_plan_and_defaults(self, db_session):
        plan = OnboardingPlan(
            tenant_id=1,
            user_id=1,
            active_lease_token="lease-abc-123",
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        assert plan.id is not None
        assert plan.tenant_id == 1
        assert plan.user_id == 1
        assert plan.status == "in_progress"
        assert plan.control_epoch == 1
        assert plan.domains_state == {}
        assert plan.active_lease_token == "lease-abc-123"
        assert plan.created_at is not None
        assert plan.updated_at is not None

    def test_create_onboarding_step_and_relationships(self, db_session):
        plan = OnboardingPlan(tenant_id=1, user_id=1)
        db_session.add(plan)
        db_session.commit()

        step = OnboardingStep(
            plan_id=plan.id,
            step_id="step_1_identity",
            domain=1,
            route="/admin/settings",
            form_id="business_settings",
            required_facts=["business_name", "business_email"],
        )
        db_session.add(step)
        db_session.commit()
        db_session.refresh(plan)

        assert len(plan.steps) == 1
        assert plan.steps[0].step_id == "step_1_identity"
        assert plan.steps[0].domain == 1
        assert plan.steps[0].status == "not_started"
        assert plan.steps[0].required_facts == ["business_name", "business_email"]
        assert plan.steps[0].answered_facts == {}
        assert plan.steps[0].staged_fields == {}

    def test_unique_constraint_on_plan_id_and_step_id(self, db_session):
        plan = OnboardingPlan(tenant_id=1, user_id=1)
        db_session.add(plan)
        db_session.commit()

        step1 = OnboardingStep(
            plan_id=plan.id,
            step_id="step_1_identity",
            domain=1,
            route="/admin/settings",
            form_id="business_settings",
        )
        db_session.add(step1)
        db_session.commit()

        step2 = OnboardingStep(
            plan_id=plan.id,
            step_id="step_1_identity",  # Duplicate step_id in same plan
            domain=1,
            route="/admin/settings",
            form_id="business_settings",
        )
        db_session.add(step2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_cascade_delete_removes_steps_and_audit_logs(self, db_session):
        plan = OnboardingPlan(tenant_id=1, user_id=1)
        db_session.add(plan)
        db_session.flush()

        step = OnboardingStep(
            plan_id=plan.id,
            step_id="step_1_identity",
            domain=1,
            route="/admin/settings",
            form_id="business_settings",
        )
        audit = OnboardingAuditLog(
            tenant_id=1,
            plan_id=plan.id,
            action="plan_created",
            actor="system",
            details={"test": True},
        )
        db_session.add_all([step, audit])
        db_session.commit()

        plan_id = plan.id
        db_session.delete(plan)
        db_session.commit()

        assert db_session.query(OnboardingStep).filter(OnboardingStep.plan_id == plan_id).count() == 0
        assert db_session.query(OnboardingAuditLog).filter(OnboardingAuditLog.plan_id == plan_id).count() == 0


class TestIntentNormalizer:
    """Verifies Australian spelling, number/unit preservation, ambiguity detection, and synthesis."""

    def test_australian_spelling_enforcement(self):
        sample = (
            "The color of the center theater is organized and customized "
            "for traveling clients with a defense license."
        )
        converted = IntentNormalizer.enforce_australian_spelling(sample)
        expected = (
            "The colour of the centre theatre is organised and customised "
            "for travelling clients with a defence licence."
        )
        assert converted == expected

    def test_australian_spelling_case_preservation(self):
        assert IntentNormalizer.enforce_australian_spelling("Organize your Colors") == "Organise your Colours"
        assert IntentNormalizer.enforce_australian_spelling("CENTER") == "CENTRE"

    def test_exact_currency_preservation(self):
        result = IntentNormalizer.normalize_field("price", "It is $120 AUD per session", field_type="price")
        assert result.normalized_value == 120
        assert result.unit == "currency"
        assert result.qualifier == "AUD"
        assert not result.ambiguous

        result2 = IntentNormalizer.normalize_field("price", "Charge 85.50 dollars", field_type="price")
        assert result2.normalized_value == 85.50
        assert result2.qualifier == "AUD"

    def test_exact_duration_preservation(self):
        res1 = IntentNormalizer.normalize_field("duration", "Appointments take 60 minutes", field_type="duration")
        assert res1.normalized_value == 60
        assert res1.unit == "minutes"
        assert not res1.ambiguous

        res2 = IntentNormalizer.normalize_field("duration", "Session lasts 1.5 hours", field_type="duration")
        assert res2.normalized_value == 90
        assert res2.unit == "minutes"

        res3 = IntentNormalizer.normalize_field("duration", "We take forty-five minutes", field_type="duration")
        assert res3.normalized_value == 45
        assert res3.unit == "minutes"

    def test_exact_distance_preservation(self):
        res = IntentNormalizer.normalize_field("travel_radius", "We travel up to 15 km", field_type="string")
        val, unit, qual = IntentNormalizer.extract_number_and_units("15 km")
        assert val == 15
        assert unit == "km"
        assert qual == "distance"

    def test_material_ambiguity_detection_does_not_guess_or_save(self):
        utterance = "About an hour, sometimes longer for the bigger ones."
        result = IntentNormalizer.normalize_field("duration", utterance, field_type="duration")

        assert result.ambiguous is True
        # Must NOT silently set 60 minutes when ambiguous!
        assert result.normalized_value is None
        assert result.clarification_prompt is not None
        assert "specify the standard duration" in result.clarification_prompt

    def test_correction_detection_replaces_candidate_and_invalidates_prior(self):
        utterance = "Actually, make that ninety, not sixty."
        result = IntentNormalizer.normalize_field("duration", utterance, previous_value=60, field_type="duration")

        assert result.is_correction is True
        assert result.normalized_value == 90
        assert result.invalidated_previous_value == 60
        assert result.unit == "minutes"

    def test_faithful_synthesis_no_hallucinations(self):
        # Spec Section 6 exact requirement:
        # "It's a little mobile grooming business, mainly dogs, we go to their house."
        # -> "We provide mobile dog grooming at clients' homes." (no cats, horses, or invented claims)
        utterance = "It's a little mobile grooming business, mainly dogs, we go to their house."
        result = IntentNormalizer.synthesize_professional_text(utterance)
        assert result == "We provide mobile dog grooming at clients' homes."

        # Tone/prompt synthesis
        utterance2 = "Don't be all salesy. Friendly, short answers, and ask if you're unsure."
        result2 = IntentNormalizer.synthesize_professional_text(utterance2)
        assert "Use a friendly, concise tone." in result2
        assert "Avoid pushy sales language." in result2

    def test_exact_identity_fields_preserved(self):
        email_res = IntentNormalizer.normalize_field("business_email", "My email is Frank.Grooming@Example.com.au")
        assert email_res.normalized_value == "frank.grooming@example.com.au"

        phone_res = IntentNormalizer.normalize_field("business_phone", "Call +61 412 345 678")
        assert phone_res.normalized_value == "+61 412 345 678"

        name_res = IntentNormalizer.normalize_field("business_name", "Frank's Paws Mobile Grooming")
        assert name_res.normalized_value == "Frank's Paws Mobile Grooming"


class TestOnboardingPlanService:
    """Verifies domain progression, staged != saved invariant, control epoch, and lease enforcement."""

    def test_get_or_create_plan_initializes_all_eight_domains(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(
            db=db_session,
            tenant_id=1,
            user_id=1,
            lease_token="lease-test-1",
        )

        assert plan.id is not None
        assert plan.control_epoch == 1
        assert plan.status == "in_progress"
        assert len(plan.steps) == 8
        assert plan.current_step_id == "step_1_identity"

        # Check all 8 domains represented in order
        domains = [step.domain for step in plan.steps]
        assert domains == [1, 2, 3, 4, 5, 6, 7, 8]

        # Check initial domains_state
        for d in range(1, 9):
            assert plan.domains_state[str(d)] == "not_started"

    def test_staged_fields_does_not_mark_step_saved(self, db_session):
        """Invariant: staged_fields != saved."""
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Stage fields on step 1
        step = OnboardingPlanService.stage_step_fields(
            db=db_session,
            plan=plan,
            step_id="step_1_identity",
            fields={"business_name": "Paws Mobile"},
            facts={"raw_name": "Paws Mobile"},
            actor="agent",
        )

        assert step.status == "staged"
        assert step.status != "saved"
        assert step.staged_fields["business_name"] == "Paws Mobile"
        assert step.persisted_entity_id is None
        assert plan.domains_state["1"] == "staged"
        assert plan.domains_state["1"] != "saved"

    def test_authoritative_save_commits_step_and_advances(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Stage first
        OnboardingPlanService.stage_step_fields(
            db=db_session,
            plan=plan,
            step_id="step_1_identity",
            fields={"business_name": "Paws Mobile"},
        )

        # Authoritative commit
        saved_step = OnboardingPlanService.commit_step_save(
            db=db_session,
            plan=plan,
            step_id="step_1_identity",
            persisted_entity_id="tenant-1",
            persisted_revision=1,
            actor="agent",
        )

        assert saved_step.status == "saved"
        assert saved_step.persisted_entity_id == "tenant-1"
        assert saved_step.persisted_revision == 1
        assert plan.domains_state["1"] == "saved"

        # Plan advances to domain 2
        assert plan.current_step_id == "step_2_locations"

    def test_skip_step_advances_plan(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        skipped_step = OnboardingPlanService.skip_step(
            db=db_session,
            plan=plan,
            step_id="step_1_identity",
            reason="Already configured in profile",
            actor="user",
        )

        assert skipped_step.status == "skipped"
        assert plan.domains_state["1"] == "skipped"
        assert plan.current_step_id == "step_2_locations"

    def test_control_epoch_advancement_and_stale_rejection(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        assert plan.control_epoch == 1

        # Manual takeover increments epoch
        OnboardingPlanService.record_manual_takeover(db_session, plan, reason="User clicked 'I will do this part'")
        assert plan.control_epoch == 2

        # Validating current epoch succeeds
        OnboardingPlanService.validate_control_epoch(plan, 2)

        # Validating older epoch raises StaleControlEpochError
        with pytest.raises(StaleControlEpochError) as exc_info:
            OnboardingPlanService.validate_control_epoch(plan, 1)
        assert exc_info.value.expected_epoch == 2
        assert exc_info.value.received_epoch == 1

    def test_lease_validation_rejects_expired_or_mismatched(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(
            db_session, tenant_id=1, user_id=1, lease_token="valid-tab-token"
        )

        # Matching lease passes
        OnboardingPlanService.validate_lease(plan, "valid-tab-token")

        # Blank lease rejected
        with pytest.raises(LeaseExpiredError):
            OnboardingPlanService.validate_lease(plan, "")

        # Mismatched lease rejected
        with pytest.raises(LeaseExpiredError):
            OnboardingPlanService.validate_lease(plan, "other-tab-token")

    def test_full_plan_completion_lifecycle(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        summary_initial = OnboardingPlanService.get_plan_summary(plan)
        assert summary_initial["status"] == "in_progress"
        assert summary_initial["total_steps"] == 8
        assert summary_initial["saved_steps"] == 0
        assert summary_initial["completion_percentage"] == 0.0

        # Complete steps 1 to 7
        for step in plan.steps:
            if step.domain < 8:
                OnboardingPlanService.commit_step_save(
                    db_session, plan, step.step_id, persisted_entity_id=f"ent-{step.domain}", persisted_revision=1
                )

        summary_final = OnboardingPlanService.get_plan_summary(plan)
        assert summary_final["is_fully_completed"] is True
        assert summary_final["status"] == "completed"
        assert summary_final["saved_steps"] == 8  # 1-7 plus automatically finalized summary step
        assert summary_final["completion_percentage"] == 100.0
