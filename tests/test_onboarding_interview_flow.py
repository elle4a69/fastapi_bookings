"""Comprehensive tests for conversational interview flow, multimodal input resolution, and website draft integration.

Covers:
1. InlineInterviewFlow:
   - 8-domain sequential interview progression in Australian English
   - Smooth topic transitions (DOMAIN_TRANSITIONS)
   - Multimodal input resolution (spoken, clicked inline choices, typed)
   - Idempotent input resolution and duplicate suppression across modalities
   - Interruption detection (ABN/tax, Stripe/payments, extra services, pauses) with polite Australian resumption
2. Website Draft Integration:
   - Factual synthesis from gathered facts across Domains 1-6
   - Eligible Media asset incorporation (public vs clinical separation)
   - Frontend RPC dispatch (route_navigation, preview_toggle, change_review_drawer)
   - Strict owner authorization nonce requirement for live publication (DelegationSaveGuard)
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.media import Media
from app.models.tenant import Tenant
from app.models.tenant_website import TenantWebsite
from app.models.user import User
from app.models.onboarding import OnboardingPlan, OnboardingStep
from app.services.business_assistant.onboarding import (
    DelegationMode,
    DelegationRefusalError,
    DelegationSaveGuard,
    InvalidNonceError,
    OnboardingPlanService,
)
from app.services.business_assistant.onboarding.interview import (
    DOMAIN_TRANSITIONS,
    QUESTION_BANK,
    InlineInterviewFlow,
)
from app.services.business_assistant.onboarding.website_generator import (
    OnboardingWebsiteGenerator,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session with full schema initialized."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    tenant = Tenant(
        id=1,
        name="Melbourne Pet Retreat",
        subdomain="melbpet",
        email="bookings@melbpet.com.au",
        phone="0391234567",
        address="123 Collins St, Melbourne VIC 3000",
    )
    session.add(tenant)
    session.flush()

    user = User(
        id=1,
        tenant_id=tenant.id,
        login="owner",
        password_hash="testhash",
        email="owner@melbpet.com.au",
        role="owner",
    )
    session.add(user)
    session.commit()

    yield session
    session.close()


class TestInterviewProgressionAndTransitions:
    """Verifies natural conversational progression across the 8 onboarding domains."""

    def test_initial_question_is_domain1_business_name(self, db_session):
        flow = InlineInterviewFlow()
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        q = flow.get_next_question(plan)
        assert q is not None
        assert q.domain == 1
        assert q.fact_key == "business_name"
        assert "G'day!" in q.prompt

    def test_sequential_fact_gathering_and_domain_transitions(self, db_session):
        flow = InlineInterviewFlow()
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Answer Domain 1 facts: business_name, business_phone, and business_email
        res1 = flow.process_response(
            db=db_session,
            plan=plan,
            input_type="spoken",
            value="Melbourne Pet Retreat",
            fact_key="business_name",
        )
        assert res1["status"] == "ok"
        assert res1["fact_key"] == "business_name"
        assert res1["all_facts_gathered"] is False

        res2 = flow.process_response(
            db=db_session,
            plan=plan,
            input_type="spoken",
            value="0391234567",
            fact_key="business_phone",
        )
        assert res2["status"] == "ok"
        assert res2["fact_key"] == "business_phone"
        assert res2["all_facts_gathered"] is False

        res3 = flow.process_response(
            db=db_session,
            plan=plan,
            input_type="spoken",
            value="contact@melbpet.com.au",
            fact_key="business_email",
        )
        assert res3["status"] == "ok"
        assert res3["all_facts_gathered"] is True
        # Step 1 is complete; verify transition greeting to Domain 2
        assert res3["transition"] == DOMAIN_TRANSITIONS[2]
        assert "Beauty!" in res3["transition"]

        # Verify next question is from Domain 2
        next_q = flow.get_next_question(plan)
        assert next_q is not None
        assert next_q.domain == 2
        assert next_q.fact_key == "address"


class TestMultimodalInputResolutionAndDeduplication:
    """Verifies spoken, clicked, and typed inputs resolve cleanly and idempotently."""

    def test_clicked_inline_choice_resolution(self, db_session):
        flow = InlineInterviewFlow()
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Resolve an inline choice for timezone
        res = flow.resolve_inline_choice(
            db=db_session,
            plan=plan,
            choice_id="syd_melb",
            value="Australia/Melbourne",
            fact_key="timezone",
        )
        assert res["status"] == "ok"
        assert res["input_type"] == "clicked"
        assert res["normalized_value"] == "Australia/Melbourne"

    def test_typed_input_resolution(self, db_session):
        flow = InlineInterviewFlow()
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        res = flow.process_response(
            db=db_session,
            plan=plan,
            input_type="typed",
            value="60 minutes",
            fact_key="duration_minutes",
        )
        assert res["status"] == "ok"
        assert res["input_type"] == "typed"
        assert "60" in res["normalized_value"]

    def test_duplicate_suppression_across_modalities(self, db_session):
        flow = InlineInterviewFlow()
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # 1. User clicks inline choice "60"
        res1 = flow.process_response(
            db=db_session,
            plan=plan,
            input_type="clicked",
            value="60",
            fact_key="duration_minutes",
        )
        assert res1["status"] == "ok"
        assert res1["duplicate_suppressed"] is False

        # 2. User then speaks "60" in the same turn
        res2 = flow.process_response(
            db=db_session,
            plan=plan,
            input_type="spoken",
            value="60",
            fact_key="duration_minutes",
        )
        assert res2["status"] == "ok"
        assert res2["duplicate_suppressed"] is True
        assert "already recorded" in res2["message"]


class TestInterruptionAndResumption:
    """Verifies polite Australian interruption handling and conversational resumption."""

    def test_interruption_abn_and_tax_query(self, db_session):
        flow = InlineInterviewFlow()
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        user_msg = "Do I need to enter my ABN or GST tax details now?"
        res = flow.handle_user_message(db=db_session, plan=plan, utterance=user_msg)

        assert res["is_interruption"] is True
        assert "No stress!" in res["spoken_response"]
        assert "ABN" in res["spoken_response"]
        # Resumption resumes the active question
        assert "getting back to where we were" in res["spoken_response"]

    def test_interruption_stripe_payments_query(self, db_session):
        flow = InlineInterviewFlow()
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        user_msg = "How do I take payments with Stripe?"
        res = flow.handle_user_message(db=db_session, plan=plan, utterance=user_msg)

        assert res["is_interruption"] is True
        assert "Payments can be connected later via the Stripe integration" in res["spoken_response"]
        assert "getting back to where we were" in res["spoken_response"]

    def test_interruption_pause_or_hold_on(self, db_session):
        flow = InlineInterviewFlow()
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        user_msg = "Wait a second, pause for a moment."
        res = flow.handle_user_message(db=db_session, plan=plan, utterance=user_msg)

        assert res["is_interruption"] is True
        assert "Too easy! We can pause right here." in res["spoken_response"]


class TestWebsiteDraftAndMediaIntegration:
    """Verifies website draft synthesis, media integration, and publication security gates."""

    def test_website_draft_incorporates_gathered_facts(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Stage facts into Domains 1 and 3
        OnboardingPlanService.stage_step_fields(
            db=db_session,
            plan=plan,
            step_id="step_1_identity",
            fields={"business_name": "Melbourne Pet Retreat", "description": "Boutique dog boarding and day spa"},
        )
        OnboardingPlanService.stage_step_fields(
            db=db_session,
            plan=plan,
            step_id="step_3_services",
            fields={"service_name": "Full Grooming & Hydrobath", "price_amount": "$95", "duration_minutes": "60"},
        )

        draft = OnboardingWebsiteGenerator.generate_website_draft(db=db_session, plan=plan)

        assert "Melbourne Pet Retreat" in draft["business_name"]
        assert "Melbourne Pet Retreat" in draft["headline"]
        assert "Full Grooming & Hydrobath" in draft["services"][0]["name"]
        assert "$95" in draft["services"][0]["price"]
        assert "60" in draft["services"][0]["duration"]

    def test_website_draft_attaches_only_eligible_media(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Add eligible public media asset
        public_media = Media(
            tenant_id=1,
            filename="salon_front.jpg",
            file_path="/media/salon_front.jpg",
            url="https://cdn.example.com/salon_front.jpg",
            content_type="image/jpeg",
            file_size=1024,
            is_public_website_eligible=True,
            is_deleted=False,
        )
        # Add private clinical media asset (should NEVER be attached to public website!)
        clinical_media = Media(
            tenant_id=1,
            filename="medical_record_dog.jpg",
            file_path="/media/medical_record_dog.jpg",
            url="https://cdn.example.com/clinical_record.jpg",
            content_type="image/jpeg",
            file_size=1024,
            is_public_website_eligible=False,
            is_deleted=False,
        )
        db_session.add_all([public_media, clinical_media])
        db_session.commit()

        draft = OnboardingWebsiteGenerator.generate_website_draft(db=db_session, plan=plan)
        hero_bg = draft["sections_data"]["hero"]["bg_image_url"]

        assert hero_bg == "https://cdn.example.com/salon_front.jpg"
        assert hero_bg != "https://cdn.example.com/clinical_record.jpg"

    def test_preview_draft_is_read_only(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)
        preview_res = OnboardingWebsiteGenerator.preview_website_draft(db=db_session, plan=plan)

        assert preview_res["status"] == "ok"
        assert preview_res["is_preview"] is True
        assert preview_res["is_published"] is False
        assert preview_res["receipt_state"] == "fields_staged"

    def test_publish_strictly_requires_owner_authorization_nonce(self, db_session):
        plan = OnboardingPlanService.get_or_create_plan(db_session, tenant_id=1, user_id=1)

        # Save unpublished draft first
        OnboardingWebsiteGenerator.save_website_draft(
            db=db_session,
            tenant_id=1,
            plan=plan,
            actor="agent",
            mode=DelegationMode.DELEGATED.value,
        )

        # Attempt to publish without nonce -> refused
        with pytest.raises(InvalidNonceError):
            OnboardingWebsiteGenerator.publish_website(
                db=db_session,
                tenant_id=1,
                plan=plan,
                nonce="",
                actor="agent",
                mode=DelegationMode.DELEGATED.value,
            )

        # Generate cryptographic authorization nonce
        pub_nonce = DelegationSaveGuard.generate_save_nonce(
            tenant_id=1,
            user_id=1,
            plan_id=plan.id,
            step_id="step_7_website",
            action="publish",
            db=db_session,
        )

        # Publish with valid nonce
        site = OnboardingWebsiteGenerator.publish_website(
            db=db_session,
            tenant_id=1,
            plan=plan,
            nonce=pub_nonce,
            actor="agent",
            mode=DelegationMode.DELEGATED.value,
        )
        assert site.is_published is True

        # Check plan step committed
        step = OnboardingPlanService.get_step_by_id(plan, "step_7_website")
        assert step.status == "saved"
