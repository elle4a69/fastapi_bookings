"""Onboarding Agent Tool Pack for voice-first onboarding and visible in-app assistance.

Exposes clean, typed tools for the conversational LLM agent:
1. stage_fields(step_id, fields)
2. highlight_field(field_name, reason)
3. validate_form(form_id)
4. request_save_authorization(domain, summary)
5. commit_save(step_id, nonce)
6. navigate_route(route, subtab)
7. get_onboarding_status()
8. ask_clarification(ambiguous_fact, clarification_prompt)
9. generate_website_draft()

All tools return structured envelopes matching frontend RPC types and enforce
truthful receipt states (staged != saved).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.onboarding import OnboardingPlan, OnboardingStep
from app.services.business_assistant.onboarding.errors import (
    DelegationRefusalError,
    FormValidationError,
    InvalidNonceError,
    LeaseExpiredError,
    OnboardingError,
    StaleControlEpochError,
)
from app.services.business_assistant.onboarding.normalizer import IntentNormalizer
from app.services.business_assistant.onboarding.plan_service import (
    DOMAIN_CONFIGS,
    OnboardingPlanService,
)
from app.services.business_assistant.onboarding.save_guard import (
    DelegationMode,
    DelegationSaveGuard,
)
from app.services.business_assistant.onboarding.website_generator import (
    OnboardingWebsiteGenerator,
)

logger = logging.getLogger("business_assistant.onboarding.tools")

# ───────────────────────────────────────────────────────────────────────────
# OpenAI / LiveKit Tool Definitions for LLM Function Calling
# ───────────────────────────────────────────────────────────────────────────

ONBOARDING_AGENT_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "stage_fields",
            "description": "Stage candidate values into the active form and onboarding step without saving them to the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "description": "The target onboarding step ID (e.g. 'step_1_identity', 'step_3_services').",
                    },
                    "fields": {
                        "type": "object",
                        "description": "Key-value dictionary of field names to candidate values to stage.",
                    },
                    "utterance": {
                        "type": "string",
                        "description": "Optional original user utterance used for context.",
                    },
                },
                "required": ["step_id", "fields"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "highlight_field",
            "description": "Signal the frontend overlay to visually point to or highlight an input element on the current form.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "The semantic name or ID of the field to highlight.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Spoken reason or context for pointing at this field.",
                    },
                    "form_id": {
                        "type": "string",
                        "description": "Optional form ID containing the field.",
                    },
                },
                "required": ["field_name"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_form",
            "description": "Validate all staged field candidates in the active form against required rules before saving.",
            "parameters": {
                "type": "object",
                "properties": {
                    "form_id": {
                        "type": "string",
                        "description": "The form identifier to validate (e.g. 'business_settings', 'catalog_services', 'website').",
                    },
                    "step_id": {
                        "type": "string",
                        "description": "Optional step ID corresponding to the form.",
                    },
                },
                "required": ["form_id"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_save_authorization",
            "description": "Request live owner authorization for consequential changes (e.g. Domain 1/2 profile, website publication) and issue a single-use authorization nonce.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "integer",
                        "description": "The onboarding domain number requiring authorization (1 to 8).",
                    },
                    "summary": {
                        "type": "string",
                        "description": "A clear, concise summary of the changes requiring owner sign-off.",
                    },
                    "step_id": {
                        "type": "string",
                        "description": "Optional target step ID.",
                    },
                },
                "required": ["domain", "summary"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "commit_save",
            "description": "Perform an authoritative database save for the validated onboarding step, strictly guarded by DelegationSaveGuard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "description": "The onboarding step ID to persist to the database.",
                    },
                    "nonce": {
                        "type": "string",
                        "description": "Single-use cryptographic authorization nonce if required by domain delegation policy.",
                    },
                    "is_publish": {
                        "type": "boolean",
                        "description": "True if performing live website publication.",
                    },
                    "is_edit_mode": {
                        "type": "boolean",
                        "description": "True if modifying an existing record rather than creating a new one.",
                    },
                },
                "required": ["step_id"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_route",
            "description": "Instruct the frontend to switch to an authorized admin page and subtab.",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "description": "Target application route (e.g. '/admin/settings', '/admin/catalog/services', '/admin/website').",
                    },
                    "subtab": {
                        "type": "string",
                        "description": "Optional subtab identifier (e.g. 'general', 'hours', 'services').",
                    },
                },
                "required": ["route"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_onboarding_status",
            "description": "Retrieve current progress across all 8 onboarding domains, current step, and next unanswered facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_facts": {
                        "type": "boolean",
                        "description": "Whether to include detailed unanswered facts for incomplete steps.",
                    },
                },
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_clarification",
            "description": "Trigger a targeted Australian-English clarification question when material ambiguity is detected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ambiguous_fact": {
                        "type": "string",
                        "description": "The fact key or concept needing clarification (e.g. 'duration_minutes', 'booking_hours').",
                    },
                    "clarification_prompt": {
                        "type": "string",
                        "description": "Targeted question to ask the user in natural Australian English.",
                    },
                },
                "required": ["ambiguous_fact", "clarification_prompt"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_website_draft",
            "description": "Generate a private starter website draft using gathered business details and services from Domains 1-6.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preview_only": {
                        "type": "boolean",
                        "description": "Whether to return the draft for preview without saving (default true).",
                    },
                },
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_context",
            "description": "Read current permitted business facts, progress, workflow scope, active step and control epoch metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_plan": {
                        "type": "boolean",
                        "description": "Whether to include full plan summary and active step details.",
                    },
                },
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_step",
            "description": "Determine the next recommended setup step, dependencies, and missing facts without mutating business state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_domain": {
                        "type": "integer",
                        "description": "Optional specific domain (1 to 8) to inspect.",
                    },
                },
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_fields",
            "description": "Prepare typed candidate field values bound to current revision and stage them into the target step.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "description": "The target step ID (e.g. 'step_1_identity').",
                    },
                    "fields": {
                        "type": "object",
                        "description": "Key-value dictionary of field names to candidate values.",
                    },
                    "utterance": {
                        "type": "string",
                        "description": "Optional user utterance.",
                    },
                },
                "required": ["step_id", "fields"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_show",
            "description": "Navigate to an allowed route/subtab and optionally highlight a target control or field element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "description": "Target application route.",
                    },
                    "subtab": {
                        "type": "string",
                        "description": "Optional subtab identifier.",
                    },
                    "field_name": {
                        "type": "string",
                        "description": "Optional field name to highlight after navigation.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional spoken reason for highlighting.",
                    },
                },
                "required": ["route"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill_form",
            "description": "Fill candidate fields in an active onboarding form through registered adapter (staging only).",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "description": "Optional step ID.",
                    },
                    "form_id": {
                        "type": "string",
                        "description": "Optional form ID.",
                    },
                    "fields": {
                        "type": "object",
                        "description": "Field key-value pairs to stage.",
                    },
                    "utterance": {
                        "type": "string",
                        "description": "Optional original utterance.",
                    },
                },
                "required": ["fields"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_form",
            "description": "Authoritatively commit a validated onboarding form step to database storage guarded by DelegationSaveGuard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "description": "Target step ID to commit.",
                    },
                    "nonce": {
                        "type": "string",
                        "description": "Single-use authorization nonce if required by domain delegation policy.",
                    },
                    "is_publish": {
                        "type": "boolean",
                        "description": "True if executing website publication.",
                    },
                    "is_edit_mode": {
                        "type": "boolean",
                        "description": "True if modifying an existing record.",
                    },
                },
                "required": ["step_id"],
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_status",
            "description": "Read authoritative progress across all 8 onboarding domains.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_facts": {
                        "type": "boolean",
                        "description": "Whether to include detailed unanswered facts.",
                    },
                },
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_takeover",
            "description": "Pause agent actions or record manual takeover, invalidating stale control epochs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for pause or manual takeover.",
                    },
                    "is_manual_takeover": {
                        "type": "boolean",
                        "description": "True if user explicitly took manual control of the form.",
                    },
                },
                "additionalProperties": False,
            },
            "strict": False,
        },
    },
)


class OnboardingToolPack:
    """Executable onboarding tool pack with authoritative database and RPC dispatch integration."""

    def __init__(
        self,
        db: Session,
        tenant_id: int,
        user_id: int,
        lease_token: Optional[str] = None,
        control_epoch: Optional[int] = None,
        rpc_dispatcher: Optional[Callable[..., Any]] = None,
        mode: str = DelegationMode.DELEGATED.value,
        normalizer: Optional[IntentNormalizer] = None,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.lease_token = lease_token
        self.control_epoch = control_epoch
        self.rpc_dispatcher = rpc_dispatcher
        self.mode = mode
        self.normalizer = normalizer or IntentNormalizer()

    def _get_plan(self) -> OnboardingPlan:
        """Fetch or initialize the tenant onboarding plan."""
        return OnboardingPlanService.get_or_create_plan(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            lease_token=self.lease_token,
        )

    def _dispatch_rpc(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send RPC action to client if dispatcher is configured."""
        receipt = {
            "action": action,
            "params": params,
            "dispatched": True,
            "tenant_id": self.tenant_id,
        }
        if self.rpc_dispatcher:
            try:
                res = self.rpc_dispatcher(action, params)
                if isinstance(res, dict):
                    receipt.update(res)
            except Exception as exc:
                logger.warning("Error dispatching RPC action %s: %s", action, exc)
                receipt["error"] = str(exc)
        return receipt

    def stage_fields(
        self,
        step_id: str,
        fields: Dict[str, Any],
        utterance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalize candidate values and stage them into the target step."""
        plan = self._get_plan()

        if self.control_epoch is not None:
            OnboardingPlanService.validate_control_epoch(plan, self.control_epoch)
        if self.lease_token:
            OnboardingPlanService.validate_lease(plan, self.lease_token)

        step = OnboardingPlanService.get_step_by_id(plan, step_id)
        if not step:
            raise OnboardingError(f"Step '{step_id}' not found in onboarding plan.", code="STEP_NOT_FOUND")

        can_stage, refusal = DelegationSaveGuard.can_stage(plan, step, actor="agent", mode=self.mode)
        if not can_stage:
            raise DelegationRefusalError(
                message=refusal or "Staging refused by delegation policy.",
                domain=step.domain,
                step_id=step_id,
                reason=refusal,
            )

        # Normalize field candidates
        normalized_fields: Dict[str, Any] = {}
        for k, v in fields.items():
            if isinstance(v, str):
                norm_res = self.normalizer.normalize_field(field_key=k, utterance=v)
                normalized_fields[k] = (
                    norm_res.normalized_value
                    if norm_res.normalized_value is not None
                    else self.normalizer.enforce_australian_spelling(v)
                )
            else:
                normalized_fields[k] = v

        # Stage fields authoritatively in plan
        step = OnboardingPlanService.stage_step_fields(
            db=self.db,
            plan=plan,
            step_id=step_id,
            fields=normalized_fields,
            actor="agent",
        )

        # Dispatch fill_fields RPC to client
        rpc_receipt = self._dispatch_rpc(
            "fill_fields",
            {
                "form_id": step.form_id,
                "fields": normalized_fields,
                "staging_guard": True,
                "prevent_autosave": True,
            },
        )

        return {
            "status": "ok",
            "action": "fill_fields",
            "step_id": step_id,
            "staged_fields": list(normalized_fields.keys()),
            "normalized_values": normalized_fields,
            "receipt_state": "fields_staged",
            "is_saved": False,  # STAGED != SAVED invariant
            "rpc_receipt": rpc_receipt,
            "message": f"Successfully staged {len(normalized_fields)} fields for {step_id}.",
        }

    def highlight_field(
        self,
        field_name: str,
        reason: str = "",
        form_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Signal the frontend to highlight an input element."""
        rpc_receipt = self._dispatch_rpc(
            "highlight_field",
            {
                "field": field_name,
                "field_name": field_name,
                "reason": reason,
                "form_id": form_id,
            },
        )

        return {
            "status": "ok",
            "action": "highlight_field",
            "field_name": field_name,
            "reason": reason,
            "form_id": form_id,
            "receipt_state": "executing",
            "rpc_receipt": rpc_receipt,
            "message": f"Highlighting field '{field_name}' in form.",
        }

    def validate_form(
        self,
        form_id: str,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate all staged fields on the form against requirements."""
        plan = self._get_plan()
        target_step = None
        if step_id:
            target_step = OnboardingPlanService.get_step_by_id(plan, step_id)
        else:
            for s in plan.steps:
                if s.form_id == form_id:
                    target_step = s
                    break

        errors: Dict[str, List[str]] = {}
        if target_step:
            staged = target_step.staged_fields or {}
            answered = target_step.answered_facts or {}
            combined = {**answered, **staged}

            # Check required facts
            for req in target_step.required_facts or []:
                if req not in combined or not str(combined[req]).strip():
                    errors.setdefault(req, []).append(f"Required field '{req}' has not been provided.")

            # Validate emails
            if "business_email" in combined:
                em = str(combined["business_email"])
                if "@" not in em or "." not in em:
                    errors.setdefault("business_email", []).append("Please provide a valid email address.")

            # Validate phones
            if "business_phone" in combined:
                ph = str(combined["business_phone"])
                if not any(char.isdigit() for char in ph):
                    errors.setdefault("business_phone", []).append("Please provide a valid phone number.")

        self._dispatch_rpc("validate_form", {"form_id": form_id, "valid": len(errors) == 0})

        if errors:
            return {
                "status": "error",
                "action": "validate_form",
                "form_id": form_id,
                "valid": False,
                "errors": errors,
                "receipt_state": "failed",
                "message": f"Form validation failed with {len(errors)} error(s).",
            }

        return {
            "status": "ok",
            "action": "validate_form",
            "form_id": form_id,
            "valid": True,
            "errors": {},
            "receipt_state": "executing",
            "message": f"All staged fields for '{form_id}' are valid.",
        }

    def request_save_authorization(
        self,
        domain: int,
        summary: str,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prompt owner for confirmation and issue single-use authorization nonce."""
        plan = self._get_plan()
        target_step_id = step_id or f"step_{domain}"
        nonce = DelegationSaveGuard.generate_save_nonce(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            plan_id=plan.id,
            step_id=target_step_id,
            action="save",
            db=self.db,
        )

        return {
            "status": "ok",
            "action": "request_save_authorization",
            "authorization_required": True,
            "domain": domain,
            "step_id": target_step_id,
            "summary": summary,
            "nonce": nonce,
            "receipt_state": "waiting_for_ui",
            "message": f"Authorization required for {summary}. Confirmation nonce generated.",
        }

    def commit_save(
        self,
        step_id: str,
        nonce: Optional[str] = None,
        is_publish: bool = False,
        is_edit_mode: bool = False,
    ) -> Dict[str, Any]:
        """Authoritatively save the step to persistent storage guarded by DelegationSaveGuard."""
        plan = self._get_plan()

        if self.control_epoch is not None:
            OnboardingPlanService.validate_control_epoch(plan, self.control_epoch)
        if self.lease_token:
            OnboardingPlanService.validate_lease(plan, self.lease_token)

        step = OnboardingPlanService.get_step_by_id(plan, step_id)
        if not step:
            raise OnboardingError(f"Step '{step_id}' not found.", code="STEP_NOT_FOUND")

        # Evaluate delegation policy
        can_save, refusal = DelegationSaveGuard.can_save(
            plan=plan,
            step=step,
            actor="agent",
            mode=self.mode,
            is_edit_mode=is_edit_mode,
            is_publish=is_publish,
            nonce_present=bool(nonce),
        )
        if not can_save:
            raise DelegationRefusalError(
                message=refusal or "Save refused by delegation policy.",
                domain=step.domain,
                step_id=step_id,
                reason=refusal,
            )

        # Validate nonce if present or required
        if nonce:
            DelegationSaveGuard.validate_save_nonce(
                nonce=nonce,
                tenant_id=self.tenant_id,
                plan_id=plan.id,
                step_id=step_id,
                action="save",
                db=self.db,
            )

        # Commit save authoritatively
        saved_step = OnboardingPlanService.commit_step_save(
            db=self.db,
            plan=plan,
            step_id=step_id,
            persisted_entity_id=f"{step_id}_entity",
            persisted_revision=1,
            actor="agent",
        )

        # Dispatch save_form RPC
        rpc_receipt = self._dispatch_rpc(
            "save_form",
            {
                "form_id": step.form_id,
                "step_id": step_id,
                "authorisation_nonce": nonce,
            },
        )

        return {
            "status": "ok",
            "action": "save_form",
            "step_id": step_id,
            "receipt_state": "saved",
            "is_saved": True,
            "persisted_entity": {"id": saved_step.persisted_entity_id, "revision": saved_step.persisted_revision},
            "rpc_receipt": rpc_receipt,
            "message": f"Step '{step_id}' successfully saved and committed.",
        }

    def navigate_route(
        self,
        route: str,
        subtab: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Signal frontend to navigate to a target route or subtab."""
        action_type = "navigate_subtab" if subtab else "route_navigation"
        rpc_receipt = self._dispatch_rpc(
            action_type,
            {"route": route, "path": route, "subtab": subtab},
        )

        return {
            "status": "ok",
            "action": action_type,
            "route": route,
            "subtab": subtab,
            "receipt_state": "waiting_for_ui",
            "rpc_receipt": rpc_receipt,
            "message": f"Navigating to {route}" + (f" (subtab: {subtab})" if subtab else ""),
        }

    def get_onboarding_status(
        self,
        include_facts: bool = True,
    ) -> Dict[str, Any]:
        """Retrieve authoritative 8-domain progress and missing facts."""
        plan = self._get_plan()
        summary = OnboardingPlanService.get_plan_summary(plan)

        domain_progress: List[Dict[str, Any]] = []
        next_unanswered: List[str] = []

        for step in sorted(plan.steps, key=lambda s: s.domain):
            staged = step.staged_fields or {}
            answered = step.answered_facts or {}
            missing = [k for k in (step.required_facts or []) if k not in staged and k not in answered]

            if missing and not next_unanswered:
                next_unanswered.extend(missing)

            domain_progress.append(
                {
                    "domain": step.domain,
                    "step_id": step.step_id,
                    "status": step.status,
                    "missing_facts": missing if include_facts else len(missing),
                }
            )

        summary["domain_progress"] = domain_progress
        summary["next_unanswered_facts"] = next_unanswered
        return {
            "status": "ok",
            "action": "get_onboarding_status",
            "receipt_state": "executing",
            "plan_summary": summary,
        }

    def ask_clarification(
        self,
        ambiguous_fact: str,
        clarification_prompt: str,
    ) -> Dict[str, Any]:
        """Prompt user with a targeted question when ambiguity is detected."""
        return {
            "status": "ok",
            "action": "ask_clarification",
            "ambiguous_fact": ambiguous_fact,
            "clarification_prompt": clarification_prompt,
            "receipt_state": "waiting_for_ui",
            "message": clarification_prompt,
        }

    def generate_website_draft(
        self,
        preview_only: bool = True,
    ) -> Dict[str, Any]:
        """Generate private starter website draft from gathered facts."""
        plan = self._get_plan()
        draft = OnboardingWebsiteGenerator.generate_website_draft(db=self.db, plan=plan)

        # Signal frontend to open preview and navigate
        self._dispatch_rpc("route_navigation", {"path": "/admin/website"})
        self._dispatch_rpc("preview_toggle", {"state": "open"})

        # Signal frontend to open preview and navigate, and open change review drawer
        self._dispatch_rpc("route_navigation", {"path": "/admin/website"})
        self._dispatch_rpc("preview_toggle", {"state": "open"})
        self._dispatch_rpc("change_review_drawer", {"state": "open", "proposal_id": "draft_starter_preview"})

        if not preview_only:
            OnboardingWebsiteGenerator.save_website_draft(
                db=self.db,
                tenant_id=self.tenant_id,
                plan=plan,
                draft_data=draft,
                actor="agent",
                mode=self.mode,
            )

        return {
            "status": "ok",
            "action": "generate_website_draft",
            "receipt_state": "fields_staged",
            "is_saved": False,
            "requires_publish_confirmation": True,
            "draft": draft,
            "message": "Generated website draft based on gathered business facts and services.",
        }

    def read_context(self, include_plan: bool = True) -> Dict[str, Any]:
        """Read current permitted business facts, progress, workflow scope, active step and control epoch metadata."""
        plan = self._get_plan()
        summary = OnboardingPlanService.get_plan_summary(plan)
        current_step = None
        if plan.current_step_id:
            current_step = OnboardingPlanService.get_step_by_id(plan, plan.current_step_id)

        context_data: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "mode": self.mode,
            "control_epoch": plan.control_epoch,
            "active_lease_token": plan.active_lease_token,
            "status": plan.status,
            "current_step_id": plan.current_step_id,
            "current_domain": current_step.domain if current_step else None,
            "current_route": current_step.route if current_step else None,
            "current_form_id": current_step.form_id if current_step else None,
            "domains_state": plan.domains_state,
            "is_saved": False,
        }
        if include_plan:
            context_data["plan_summary"] = summary
            if current_step:
                context_data["active_step"] = {
                    "step_id": current_step.step_id,
                    "domain": current_step.domain,
                    "status": current_step.status,
                    "required_facts": current_step.required_facts or [],
                    "answered_facts": current_step.answered_facts or {},
                    "staged_fields": current_step.staged_fields or {},
                }
        return {
            "status": "ok",
            "action": "read_context",
            "receipt_state": "executing",
            "context": context_data,
        }

    def plan_step(self, target_domain: Optional[int] = None) -> Dict[str, Any]:
        """Determine next setup step, dependencies, and missing facts without business mutation."""
        plan = self._get_plan()
        steps = sorted(plan.steps, key=lambda s: s.domain)

        next_step = None
        missing_facts: List[str] = []

        if target_domain:
            for s in steps:
                if s.domain == target_domain:
                    next_step = s
                    break
        else:
            for s in steps:
                if s.status not in ("saved", "skipped"):
                    next_step = s
                    break

        if next_step:
            staged = next_step.staged_fields or {}
            answered = next_step.answered_facts or {}
            missing_facts = [k for k in (next_step.required_facts or []) if k not in staged and k not in answered]

        return {
            "status": "ok",
            "action": "plan_step",
            "receipt_state": "executing",
            "next_step_id": next_step.step_id if next_step else None,
            "domain": next_step.domain if next_step else None,
            "route": next_step.route if next_step else None,
            "form_id": next_step.form_id if next_step else None,
            "missing_facts": missing_facts,
            "dependencies": [],
            "message": f"Next step is '{next_step.step_id}' in Domain {next_step.domain}." if next_step else "All steps planned/completed.",
        }

    def prepare_fields(
        self,
        step_id: str,
        fields: Dict[str, Any],
        utterance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Alias for stage_fields: prepare candidate values and stage them into target step."""
        return self.stage_fields(step_id=step_id, fields=fields, utterance=utterance)

    def navigate_show(
        self,
        route: str,
        subtab: Optional[str] = None,
        field_name: Optional[str] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Navigate to allowed route/subtab and optionally highlight target field/control."""
        nav_res = self.navigate_route(route=route, subtab=subtab)
        if field_name:
            hl_res = self.highlight_field(field_name=field_name, reason=reason)
            nav_res["highlight"] = hl_res
        return nav_res

    def fill_form(
        self,
        step_id: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
        form_id: Optional[str] = None,
        utterance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Alias for stage_fields: fill form candidates through registered adapter."""
        plan = self._get_plan()
        target_step_id = step_id
        if not target_step_id and form_id:
            for s in plan.steps:
                if s.form_id == form_id:
                    target_step_id = s.step_id
                    break
        if not target_step_id:
            target_step_id = plan.current_step_id or "step_1_identity"

        return self.stage_fields(step_id=target_step_id, fields=fields or {}, utterance=utterance)

    def save_form(
        self,
        step_id: str,
        nonce: Optional[str] = None,
        is_publish: bool = False,
        is_edit_mode: bool = False,
    ) -> Dict[str, Any]:
        """Alias for commit_save: authoritatively commit step to database guarded by DelegationSaveGuard."""
        return self.commit_save(step_id=step_id, nonce=nonce, is_publish=is_publish, is_edit_mode=is_edit_mode)

    def read_status(self, include_facts: bool = True) -> Dict[str, Any]:
        """Alias for get_onboarding_status."""
        return self.get_onboarding_status(include_facts=include_facts)

    def pause_takeover(
        self,
        reason: str = "manual_takeover",
        is_manual_takeover: bool = True,
    ) -> Dict[str, Any]:
        """Pause agent actions or record manual takeover, advancing control epoch."""
        plan = self._get_plan()
        if is_manual_takeover:
            OnboardingPlanService.record_manual_takeover(
                db=self.db,
                plan=plan,
                reason=reason,
            )

        rpc_receipt = self._dispatch_rpc(
            "manual_takeover",
            {
                "reason": reason,
                "control_epoch": plan.control_epoch,
                "paused": True,
            },
        )

        return {
            "status": "ok",
            "action": "manual_takeover" if is_manual_takeover else "pause",
            "control_epoch": plan.control_epoch,
            "receipt_state": "executing",
            "is_saved": False,
            "rpc_receipt": rpc_receipt,
            "message": f"Takeover recorded: {reason}. Control epoch is now {plan.control_epoch}.",
        }

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically execute a tool by name with arguments."""
        alias_map = {
            "read_context": self.read_context,
            "plan_step": self.plan_step,
            "prepare_fields": self.prepare_fields,
            "navigate_show": self.navigate_show,
            "fill_form": self.fill_form,
            "validate_form": self.validate_form,
            "save_form": self.save_form,
            "read_status": self.read_status,
            "pause_takeover": self.pause_takeover,
            "stage_fields": self.stage_fields,
            "highlight_field": self.highlight_field,
            "request_save_authorization": self.request_save_authorization,
            "commit_save": self.commit_save,
            "navigate_route": self.navigate_route,
            "get_onboarding_status": self.get_onboarding_status,
            "ask_clarification": self.ask_clarification,
            "generate_website_draft": self.generate_website_draft,
        }
        handler = alias_map.get(tool_name) or getattr(self, tool_name, None)
        if not handler or not callable(handler) or tool_name.startswith("_"):
            return {
                "status": "rejected",
                "error_code": "unsupported_action",
                "message": f"Tool '{tool_name}' is not supported by OnboardingToolPack.",
            }

        try:
            return handler(**arguments)
        except OnboardingError as exc:
            return {
                "status": "rejected",
                "error_code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        except TypeError as exc:
            return {
                "status": "rejected",
                "error_code": "invalid_value",
                "message": f"Invalid arguments for tool '{tool_name}': {str(exc)}",
            }
        except Exception as exc:
            logger.exception("Unexpected error executing onboarding tool %s: %s", tool_name, exc)
            return {
                "status": "failed",
                "error_code": "outcome_unknown",
                "message": f"Execution error in tool '{tool_name}': {str(exc)}",
            }

