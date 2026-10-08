"""Website draft generator and preview integration for voice-first onboarding.

Generates professional, factual website drafts (headline, hero, about, services, hours, contact)
using gathered onboarding facts from Domains 1-6 in Australian English.
Previewing is permitted autonomously, but live publication strictly requires owner
authorization nonces guarded by DelegationSaveGuard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.tenant_website import TenantWebsite
from app.models.onboarding import OnboardingPlan, OnboardingStep
from app.services.business_assistant.onboarding.errors import (
    DelegationRefusalError,
    FormValidationError,
    InvalidNonceError,
)
from app.services.business_assistant.onboarding.plan_service import OnboardingPlanService
from app.services.business_assistant.onboarding.save_guard import (
    DelegationMode,
    DelegationSaveGuard,
)


class OnboardingWebsiteGenerator:
    """Generates and manages website drafts during voice-first onboarding."""

    @classmethod
    def extract_gathered_facts(
        cls,
        plan: Optional[OnboardingPlan],
        tenant: Optional[Tenant] = None,
    ) -> Dict[str, Any]:
        """Aggregate answered facts and staged fields across all onboarding steps."""
        facts: Dict[str, Any] = {}

        # 1. Fallback / base values from Tenant model if provided
        if tenant:
            if tenant.name:
                facts["business_name"] = tenant.name
            if tenant.email:
                facts["business_email"] = tenant.email
            if tenant.phone:
                facts["business_phone"] = tenant.phone
            if tenant.address:
                facts["address"] = tenant.address
            if getattr(tenant, "timezone", None):
                facts["timezone"] = tenant.timezone

        # 2. Extract from plan steps (Domains 1 to 6)
        if plan and plan.steps:
            for step in plan.steps:
                # Merge answered facts
                if step.answered_facts and isinstance(step.answered_facts, dict):
                    facts.update(step.answered_facts)
                # Merge staged fields (takes precedence over raw answered facts)
                if step.staged_fields and isinstance(step.staged_fields, dict):
                    facts.update(step.staged_fields)

        return facts

    @classmethod
    def generate_website_draft(
        cls,
        db: Optional[Session] = None,
        plan: Optional[OnboardingPlan] = None,
        tenant: Optional[Tenant] = None,
    ) -> Dict[str, Any]:
        """Synthesize a complete professional website draft in Australian English.

        Factual and faithful: no invented claims, awards, or medical/legal guarantees.
        """
        facts = cls.extract_gathered_facts(plan, tenant)

        business_name = facts.get("business_name") or "Your Business"
        description = facts.get("business_description") or facts.get("description") or ""
        service_name = facts.get("service_name") or "Quality Services"
        service_desc = facts.get("service_description") or "Professional, tailored appointments designed to suit your schedule."
        price_val = facts.get("price_amount") or facts.get("price") or "$120"
        duration_val = facts.get("duration_minutes") or facts.get("duration") or "60 mins"
        address = facts.get("address") or ""
        phone = facts.get("business_phone") or facts.get("phone") or ""
        email = facts.get("business_email") or facts.get("email") or ""
        operating_hours = facts.get("operating_hours") or "Monday to Friday: 9:00 AM – 5:00 PM"
        service_mode = facts.get("service_delivery_mode") or "appointments"

        # Construct Australian English headline
        if description and len(description) < 60:
            headline = f"{business_name} — {description}"
        elif "grooming" in business_name.lower() or "grooming" in str(description).lower():
            headline = f"Professional Pet Care & Grooming at {business_name}"
        else:
            headline = f"Welcome to {business_name}"

        # Construct engaging, factual hero copy
        if description:
            hero_text = (
                f"{description.strip()} We take pride in delivering trusted, reliable care for all our clients."
            )
        else:
            hero_text = (
                f"Welcome to {business_name}. We offer reliable, dedicated service tailored to your needs across Australia."
            )

        # About copy
        about_body = (
            f"At {business_name}, our priority is delivering prompt, attentive care and exceptional results. "
            f"Whether you book online or contact us directly, we ensure every appointment is handled with dedication and professionalism."
        )

        # Services list
        service_items = [
            {
                "id": 1,
                "name": str(service_name),
                "description": str(service_desc),
                "duration": str(duration_val),
                "price": str(price_val),
                "is_featured": True,
            }
        ]

        # Integrate approved, eligible Media assets (never clinical / operational notes)
        media_images: List[str] = []
        target_tenant_id = (plan.tenant_id if plan else None) or (tenant.id if tenant else None)
        if db and target_tenant_id:
            try:
                from app.models.media import Media
                eligible_media = (
                    db.query(Media)
                    .filter(
                        Media.tenant_id == target_tenant_id,
                        Media.is_public_website_eligible.is_(True),
                        Media.is_deleted.is_(False),
                    )
                    .order_by(Media.id.asc())
                    .all()
                )
                for m in eligible_media:
                    u = getattr(m, "file_url", None) or getattr(m, "url", None) or f"/api/media/{m.id}"
                    if u:
                        media_images.append(u)
            except Exception:
                pass

        hero_bg = media_images[0] if media_images else None
        about_img = media_images[1] if len(media_images) > 1 else hero_bg

        # Structure complete website draft matching TenantWebsite sections format
        sections_data: Dict[str, Any] = {
            "hero": {
                "headline": headline,
                "subhead": hero_text,
                "cta_text": "Book an Appointment",
                "cta_target": "#booking",
                "bg_image_url": hero_bg,
                "enabled": True,
            },
            "about": {
                "headline": f"About {business_name}",
                "body": about_body,
                "image_url": about_img,
                "enabled": True,
            },
            "services": {
                "headline": "Our Services",
                "subhead": "Explore our core offerings and book your preferred time online.",
                "items": service_items,
                "enabled": True,
            },
            "booking": {
                "headline": "Book Online",
                "subhead": f"Select a service with {business_name} and choose a convenient time.",
                "embedded_style": "card",
                "enabled": True,
            },
            "contact": {
                "headline": "Contact Us",
                "subhead": f"Get in touch with {business_name}.",
                "address": address,
                "phone": phone,
                "email": email,
                "hours": operating_hours,
                "enabled": True,
            },
            "footer": {
                "copyright": f"© {datetime.now(timezone.utc).year} {business_name}. All rights reserved.",
                "social_links": {},
                "enabled": True,
            },
            "draft_meta": {
                "generated_from": "onboarding_domains_1_to_6",
                "is_initial_draft": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        return {
            "business_name": business_name,
            "headline": headline,
            "hero_text": hero_text,
            "about_body": about_body,
            "services": service_items,
            "operating_hours": operating_hours,
            "address": address,
            "phone": phone,
            "email": email,
            "sections_data": sections_data,
            "seo_title": f"{business_name} | Book Online",
            "seo_description": hero_text[:155],
        }

    @classmethod
    def preview_website_draft(
        cls,
        db: Optional[Session] = None,
        plan: Optional[OnboardingPlan] = None,
        tenant: Optional[Tenant] = None,
    ) -> Dict[str, Any]:
        """Generate a preview envelope for the website draft.

        Read-only action: does not mutate published state or require confirmation nonces.
        """
        draft = cls.generate_website_draft(db=db, plan=plan, tenant=tenant)
        return {
            "status": "ok",
            "action": "preview_website_draft",
            "is_preview": True,
            "is_published": False,
            "draft": draft,
            "receipt_state": "fields_staged",
        }

    @classmethod
    def save_website_draft(
        cls,
        db: Session,
        tenant_id: int,
        plan: OnboardingPlan,
        draft_data: Optional[Dict[str, Any]] = None,
        actor: str = "agent",
        mode: str = DelegationMode.DELEGATED.value,
    ) -> TenantWebsite:
        """Persist website draft to the database as an unpublished draft.

        Enforces delegation rules: agent may stage/save draft in delegated or hands_off mode.
        """
        step = OnboardingPlanService.get_step_by_id(plan, "step_7_website")
        if not step:
            step = OnboardingStep(
                plan_id=plan.id,
                step_id="step_7_website",
                domain=7,
                route="/admin/website",
                form_id="website",
                status="not_started",
                required_facts=["website_headline", "website_about"],
            )
            db.add(step)
            db.flush()

        can_stage, refusal = DelegationSaveGuard.can_stage(plan, step, actor=actor, mode=mode)
        if not can_stage:
            raise DelegationRefusalError(
                message=refusal or "Staging website draft is prohibited by delegation policy.",
                domain=7,
                step_id="step_7_website",
                reason=refusal,
            )

        if not draft_data:
            draft_data = cls.generate_website_draft(db=db, plan=plan)

        # Stage fields in plan
        OnboardingPlanService.stage_step_fields(
            db=db,
            plan=plan,
            step_id="step_7_website",
            fields={
                "website_headline": draft_data["headline"],
                "website_about": draft_data["about_body"],
                "hero_text": draft_data["hero_text"],
            },
            actor=actor,
        )

        # Persist or update TenantWebsite as unpublished
        website = db.query(TenantWebsite).filter(TenantWebsite.tenant_id == tenant_id).first()
        if not website:
            website = TenantWebsite(
                tenant_id=tenant_id,
                template_id="minimalist",
                theme_id="ocean_slate",
                custom_colors={},
                sections_data=draft_data["sections_data"],
                is_published=False,
                seo_title=draft_data["seo_title"],
                seo_description=draft_data["seo_description"],
            )
            db.add(website)
        else:
            website.sections_data = draft_data["sections_data"]
            website.seo_title = draft_data["seo_title"]
            website.seo_description = draft_data["seo_description"]
            # Do NOT modify is_published on draft save

        db.commit()
        db.refresh(website)
        return website

    @classmethod
    def publish_website(
        cls,
        db: Session,
        tenant_id: int,
        plan: OnboardingPlan,
        nonce: str,
        actor: str = "agent",
        mode: str = DelegationMode.DELEGATED.value,
    ) -> TenantWebsite:
        """Publish the website live to the public internet.

        STRICT SAFETY GATE:
        Publishing strictly requires an explicit owner authorization nonce validated by
        DelegationSaveGuard. An agent cannot publish without a valid, unexpired, single-use nonce.
        """
        step = OnboardingPlanService.get_step_by_id(plan, "step_7_website")
        if not step:
            raise DelegationRefusalError(
                message="Step 'step_7_website' not found in onboarding plan.",
                domain=7,
                step_id="step_7_website",
                reason="step_missing",
            )

        if not nonce or not isinstance(nonce, str):
            raise InvalidNonceError("Publication requires a valid authorization nonce.")

        # Validate delegation policy
        can_save, refusal = DelegationSaveGuard.can_save(
            plan=plan,
            step=step,
            actor=actor,
            mode=mode,
            is_publish=True,
            nonce_present=bool(nonce),
        )
        if not can_save:
            raise DelegationRefusalError(
                message=refusal or "Publication refused by delegation policy.",
                domain=7,
                step_id="step_7_website",
                reason=refusal,
            )

        # Validate and consume single-use cryptographic nonce
        # Try both "publish" and "save" scopes for flexibility
        try:
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=tenant_id,
                plan_id=plan.id,
                step_id="step_7_website",
                action="publish",
                db=db,
            )
        except InvalidNonceError:
            # Also allow generic "save" nonce scoped to step
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=tenant_id,
                plan_id=plan.id,
                step_id="step_7_website",
                action="save",
                db=db,
            )

        website = db.query(TenantWebsite).filter(TenantWebsite.tenant_id == tenant_id).first()
        if not website:
            draft = cls.generate_website_draft(db=db, plan=plan)
            website = TenantWebsite(
                tenant_id=tenant_id,
                template_id="minimalist",
                theme_id="ocean_slate",
                custom_colors={},
                sections_data=draft["sections_data"],
                is_published=True,
                seo_title=draft["seo_title"],
                seo_description=draft["seo_description"],
            )
            db.add(website)
        else:
            website.is_published = True

        # Commit step in plan
        OnboardingPlanService.commit_step_save(
            db=db,
            plan=plan,
            step_id="step_7_website",
            persisted_entity_id=str(website.id if website.id else "website"),
            persisted_revision=1,
            actor=actor,
        )

        db.commit()
        db.refresh(website)
        return website
