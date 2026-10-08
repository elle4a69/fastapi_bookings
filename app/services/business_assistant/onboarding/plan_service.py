"""Onboarding Planner Service.

Manages tenant onboarding setup plans across the 8 domains defined in spec Section 7:
1. Business identity (profile, phone, email)
2. Locations & timezone
3. Services (catalog services, durations, prices)
4. Providers / team
5. Business hours & schedules
6. General setup settings
7. Media & website draft
8. Final summary

Enforces invariant: staged_fields != saved. Only authoritative save marks a step saved.
Handles control epochs, single-tab active executor leasing, step dependencies, and audit logs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.onboarding import OnboardingAuditLog, OnboardingPlan, OnboardingStep
from app.services.business_assistant.onboarding.errors import (
    LeaseExpiredError,
    OnboardingError,
    StaleControlEpochError,
)

# Specification Section 7 domain definitions
DOMAIN_CONFIGS: List[Dict[str, Any]] = [
    {
        "domain": 1,
        "name": "business_identity",
        "step_id": "step_1_identity",
        "route": "/admin/settings",
        "form_id": "business_settings",
        "required_facts": ["business_name", "business_email", "business_phone"],
    },
    {
        "domain": 2,
        "name": "locations_and_timezone",
        "step_id": "step_2_locations",
        "route": "/admin/settings",
        "form_id": "business_settings",
        "required_facts": ["address", "timezone"],
    },
    {
        "domain": 3,
        "name": "services_catalog",
        "step_id": "step_3_services",
        "route": "/admin/catalog/services",
        "form_id": "catalog_services",
        "required_facts": ["service_name", "duration_minutes", "price_amount"],
    },
    {
        "domain": 4,
        "name": "providers_and_team",
        "step_id": "step_4_providers",
        "route": "/admin/settings",
        "form_id": "business_settings",
        "required_facts": ["provider_name"],
    },
    {
        "domain": 5,
        "name": "business_hours",
        "step_id": "step_5_hours",
        "route": "/admin/settings",
        "form_id": "business_settings",
        "required_facts": ["operating_hours"],
    },
    {
        "domain": 6,
        "name": "general_settings",
        "step_id": "step_6_settings",
        "route": "/admin/settings",
        "form_id": "business_settings",
        "required_facts": ["cancellation_policy"],
    },
    {
        "domain": 7,
        "name": "media_and_website",
        "step_id": "step_7_website",
        "route": "/admin/website",
        "form_id": "website",
        "required_facts": ["website_headline", "website_about"],
    },
    {
        "domain": 8,
        "name": "final_summary",
        "step_id": "step_8_summary",
        "route": "/admin/settings",
        "form_id": "business_settings",
        "required_facts": [],
    },
]


class OnboardingPlanService:
    """Service orchestrating onboarding setup plan lifecycle, step progression, and verification."""

    @classmethod
    def get_or_create_plan(
        cls,
        db: Session,
        tenant_id: int,
        user_id: int,
        lease_token: Optional[str] = None,
    ) -> OnboardingPlan:
        """Retrieve the active onboarding plan or create a new plan with default domain steps."""
        plan = (
            db.query(OnboardingPlan)
            .filter(
                OnboardingPlan.tenant_id == tenant_id,
                OnboardingPlan.user_id == user_id,
                OnboardingPlan.status == "in_progress",
            )
            .first()
        )

        if plan:
            if lease_token and not plan.active_lease_token:
                plan.active_lease_token = lease_token
                db.commit()
                db.refresh(plan)
            return plan

        # Initialize domain states (1 to 8)
        initial_domains_state = {str(cfg["domain"]): "not_started" for cfg in DOMAIN_CONFIGS}

        new_plan = OnboardingPlan(
            tenant_id=tenant_id,
            user_id=user_id,
            status="in_progress",
            current_step_id=DOMAIN_CONFIGS[0]["step_id"],
            domains_state=initial_domains_state,
            control_epoch=1,
            active_lease_token=lease_token,
        )
        db.add(new_plan)
        db.flush()

        # Seed steps for each domain
        for cfg in DOMAIN_CONFIGS:
            step = OnboardingStep(
                plan_id=new_plan.id,
                step_id=cfg["step_id"],
                domain=cfg["domain"],
                route=cfg["route"],
                form_id=cfg["form_id"],
                status="not_started",
                required_facts=cfg["required_facts"],
                answered_facts={},
                staged_fields={},
            )
            db.add(step)

        # Audit initial creation
        audit = OnboardingAuditLog(
            tenant_id=tenant_id,
            plan_id=new_plan.id,
            action="plan_created",
            actor="system",
            details={"step_count": len(DOMAIN_CONFIGS), "initial_step": DOMAIN_CONFIGS[0]["step_id"]},
        )
        db.add(audit)
        db.commit()
        db.refresh(new_plan)
        return new_plan

    @classmethod
    def get_plan(
        cls,
        db: Session,
        plan_id: int,
        tenant_id: int,
    ) -> Optional[OnboardingPlan]:
        """Fetch plan by ID scoped strictly to the given tenant."""
        return (
            db.query(OnboardingPlan)
            .filter(OnboardingPlan.id == plan_id, OnboardingPlan.tenant_id == tenant_id)
            .first()
        )

    @classmethod
    def get_step_by_id(
        cls,
        plan: OnboardingPlan,
        step_id: str,
    ) -> Optional[OnboardingStep]:
        """Find a step in the plan by step_id."""
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        return None

    @classmethod
    def get_current_step(
        cls,
        plan: OnboardingPlan,
    ) -> Optional[OnboardingStep]:
        """Get the current active step in the plan."""
        if plan.current_step_id:
            step = cls.get_step_by_id(plan, plan.current_step_id)
            if step:
                return step

        # Fallback to first non-saved and non-skipped step
        for step in sorted(plan.steps, key=lambda s: s.domain):
            if step.status not in ("saved", "skipped"):
                return step
        return None

    @classmethod
    def validate_control_epoch(
        cls,
        plan: OnboardingPlan,
        incoming_epoch: int,
    ) -> None:
        """Enforce control epoch monotonicity.

        Raises StaleControlEpochError if incoming epoch is older than current plan epoch.
        """
        if incoming_epoch < plan.control_epoch:
            raise StaleControlEpochError(
                message=(
                    f"Command control epoch {incoming_epoch} is stale; "
                    f"current plan epoch is {plan.control_epoch}."
                ),
                expected_epoch=plan.control_epoch,
                received_epoch=incoming_epoch,
            )

    @classmethod
    def validate_lease(
        cls,
        plan: OnboardingPlan,
        lease_token: str,
    ) -> None:
        """Enforce single-tab active executor lease.

        Raises LeaseExpiredError if lease token is invalid or does not match active lease.
        """
        if not lease_token or not lease_token.strip():
            raise LeaseExpiredError(
                message="Command rejected: active executor lease token must be provided.",
                lease_token=lease_token,
            )
        if plan.active_lease_token and plan.active_lease_token != lease_token.strip():
            raise LeaseExpiredError(
                message="Command rejected: lease token does not match active executor tab.",
                lease_token=lease_token,
                details={"active_lease_token": plan.active_lease_token},
            )

    @classmethod
    def stage_step_fields(
        cls,
        db: Session,
        plan: OnboardingPlan,
        step_id: str,
        fields: Dict[str, Any],
        facts: Optional[Dict[str, Any]] = None,
        actor: str = "agent",
    ) -> OnboardingStep:
        """Stage candidate field values without committing to the persistent business store.

        Enforces the invariant: staged_fields != saved.
        """
        step = cls.get_step_by_id(plan, step_id)
        if not step:
            raise OnboardingError(
                message=f"Step '{step_id}' not found in plan {plan.id}.",
                code="STEP_NOT_FOUND",
            )

        updated_staged = dict(step.staged_fields or {})
        updated_staged.update(fields)
        step.staged_fields = updated_staged

        if facts:
            updated_facts = dict(step.answered_facts or {})
            updated_facts.update(facts)
            step.answered_facts = updated_facts

        if step.status in ("not_started", "gathering"):
            step.status = "staged"

        # Update domains state if not already saved
        domain_key = str(step.domain)
        domains_state = dict(plan.domains_state or {})
        if domains_state.get(domain_key) != "saved":
            domains_state[domain_key] = "staged"
            plan.domains_state = domains_state
            flag_modified(plan, "domains_state")

        audit = OnboardingAuditLog(
            tenant_id=plan.tenant_id,
            plan_id=plan.id,
            action="stage_fields",
            actor=actor,
            details={"step_id": step_id, "staged_keys": list(fields.keys())},
        )
        db.add(audit)
        db.commit()
        db.refresh(step)
        return step

    @classmethod
    def commit_step_save(
        cls,
        db: Session,
        plan: OnboardingPlan,
        step_id: str,
        persisted_entity_id: Optional[str] = None,
        persisted_revision: Optional[int] = None,
        actor: str = "agent",
    ) -> OnboardingStep:
        """Authoritative save: only committed persistence marks a step 'saved'."""
        step = cls.get_step_by_id(plan, step_id)
        if not step:
            raise OnboardingError(
                message=f"Step '{step_id}' not found in plan {plan.id}.",
                code="STEP_NOT_FOUND",
            )

        step.status = "saved"
        step.persisted_entity_id = persisted_entity_id
        step.persisted_revision = persisted_revision

        # Update domains state
        domain_key = str(step.domain)
        domains_state = dict(plan.domains_state or {})
        domains_state[domain_key] = "saved"
        plan.domains_state = domains_state
        flag_modified(plan, "domains_state")

        audit = OnboardingAuditLog(
            tenant_id=plan.tenant_id,
            plan_id=plan.id,
            action="save_fields",
            actor=actor,
            details={
                "step_id": step_id,
                "persisted_entity_id": persisted_entity_id,
                "persisted_revision": persisted_revision,
            },
        )
        db.add(audit)

        # Advance step to next available if current step was saved
        if plan.current_step_id == step_id:
            cls.advance_step(db, plan, current_step_id=step_id, commit=False)

        # Check for plan completion
        cls._check_and_update_plan_completion(plan)

        db.commit()
        db.refresh(step)
        db.refresh(plan)
        return step

    @classmethod
    def skip_step(
        cls,
        db: Session,
        plan: OnboardingPlan,
        step_id: str,
        reason: str = "",
        actor: str = "user",
    ) -> OnboardingStep:
        """Skip an optional onboarding step."""
        step = cls.get_step_by_id(plan, step_id)
        if not step:
            raise OnboardingError(
                message=f"Step '{step_id}' not found in plan {plan.id}.",
                code="STEP_NOT_FOUND",
            )

        step.status = "skipped"

        domain_key = str(step.domain)
        domains_state = dict(plan.domains_state or {})
        domains_state[domain_key] = "skipped"
        plan.domains_state = domains_state
        flag_modified(plan, "domains_state")

        audit = OnboardingAuditLog(
            tenant_id=plan.tenant_id,
            plan_id=plan.id,
            action="skip_step",
            actor=actor,
            details={"step_id": step_id, "reason": reason},
        )
        db.add(audit)

        if plan.current_step_id == step_id:
            cls.advance_step(db, plan, current_step_id=step_id, commit=False)

        cls._check_and_update_plan_completion(plan)

        db.commit()
        db.refresh(step)
        db.refresh(plan)
        return step

    @classmethod
    def mark_step_needs_review(
        cls,
        db: Session,
        plan: OnboardingPlan,
        step_id: str,
        reason: str = "",
        actor: str = "agent",
    ) -> OnboardingStep:
        """Mark a step as requiring user review or manual completion."""
        step = cls.get_step_by_id(plan, step_id)
        if not step:
            raise OnboardingError(
                message=f"Step '{step_id}' not found in plan {plan.id}.",
                code="STEP_NOT_FOUND",
            )

        step.status = "needs_review"

        domain_key = str(step.domain)
        domains_state = dict(plan.domains_state or {})
        domains_state[domain_key] = "needs_review"
        plan.domains_state = domains_state
        flag_modified(plan, "domains_state")

        audit = OnboardingAuditLog(
            tenant_id=plan.tenant_id,
            plan_id=plan.id,
            action="mark_needs_review",
            actor=actor,
            details={"step_id": step_id, "reason": reason},
        )
        db.add(audit)
        db.commit()
        db.refresh(step)
        return step

    @classmethod
    def record_manual_takeover(
        cls,
        db: Session,
        plan: OnboardingPlan,
        reason: str = "user_manual_takeover",
    ) -> OnboardingPlan:
        """Record manual takeover by incrementing control epoch and invalidating stale agent writes."""
        plan.control_epoch += 1

        audit = OnboardingAuditLog(
            tenant_id=plan.tenant_id,
            plan_id=plan.id,
            action="manual_takeover",
            actor="user",
            details={"new_control_epoch": plan.control_epoch, "reason": reason},
        )
        db.add(audit)
        db.commit()
        db.refresh(plan)
        return plan

    @classmethod
    def advance_step(
        cls,
        db: Session,
        plan: OnboardingPlan,
        current_step_id: Optional[str] = None,
        commit: bool = True,
    ) -> Optional[OnboardingStep]:
        """Find the next eligible step and advance the plan's current_step_id."""
        sorted_steps = sorted(plan.steps, key=lambda s: s.domain)
        next_step: Optional[OnboardingStep] = None

        if current_step_id:
            current_idx = -1
            for idx, s in enumerate(sorted_steps):
                if s.step_id == current_step_id:
                    current_idx = idx
                    break
            if current_idx != -1 and current_idx + 1 < len(sorted_steps):
                for candidate in sorted_steps[current_idx + 1 :]:
                    if candidate.status not in ("saved", "skipped"):
                        next_step = candidate
                        break

        if not next_step:
            for s in sorted_steps:
                if s.status not in ("saved", "skipped"):
                    next_step = s
                    break

        if next_step:
            plan.current_step_id = next_step.step_id
        else:
            plan.current_step_id = None

        if commit:
            db.commit()
            db.refresh(plan)

        return next_step

    @classmethod
    def _check_and_update_plan_completion(cls, plan: OnboardingPlan) -> None:
        """Mark plan as completed if all domain steps are saved or skipped."""
        all_done = all(
            step.status in ("saved", "skipped")
            for step in plan.steps
            if step.domain < 8  # domain 8 is final summary
        )
        if all_done:
            summary_step = cls.get_step_by_id(plan, "step_8_summary")
            if summary_step and summary_step.status == "not_started":
                summary_step.status = "saved"
            plan.status = "completed"

    @classmethod
    def get_plan_summary(cls, plan: OnboardingPlan) -> Dict[str, Any]:
        """Generate truthful summary of plan progress across all 8 domains."""
        steps = plan.steps
        saved_count = sum(1 for s in steps if s.status == "saved")
        staged_count = sum(1 for s in steps if s.status == "staged")
        skipped_count = sum(1 for s in steps if s.status == "skipped")
        needs_review_count = sum(1 for s in steps if s.status == "needs_review")
        not_started_count = sum(1 for s in steps if s.status == "not_started")
        total = len(steps)

        return {
            "plan_id": plan.id,
            "tenant_id": plan.tenant_id,
            "user_id": plan.user_id,
            "status": plan.status,
            "control_epoch": plan.control_epoch,
            "current_step_id": plan.current_step_id,
            "domains_state": plan.domains_state,
            "total_steps": total,
            "saved_steps": saved_count,
            "staged_steps": staged_count,
            "skipped_steps": skipped_count,
            "needs_review_steps": needs_review_count,
            "not_started_steps": not_started_count,
            "completion_percentage": round((saved_count + skipped_count) / total * 100, 1) if total > 0 else 0.0,
            "is_fully_completed": plan.status == "completed",
        }
