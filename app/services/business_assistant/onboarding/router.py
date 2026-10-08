"""FastAPI router for tenant-scoped voice-first onboarding workflow operations.

Exposes endpoints for plan creation and retrieval, field staging with Australian-English
normalization, authoritative step saving with delegation guard enforcement, manual takeover,
tab lease management, and cryptographic save nonce generation.
"""

from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant, get_current_user, get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.onboarding.errors import (
    DelegationRefusalError,
    InvalidNonceError,
    LeaseExpiredError,
    NonceAlreadyUsedError,
    NonceExpiredError,
    OnboardingError,
    StaleControlEpochError,
)
from app.services.business_assistant.onboarding.normalizer import IntentNormalizer
from app.services.business_assistant.onboarding.plan_service import OnboardingPlanService
from app.services.business_assistant.onboarding.save_guard import (
    DelegationMode,
    DelegationSaveGuard,
)

router = APIRouter(prefix="/api/business-assistant/onboarding", tags=["Onboarding"])


# ---------------------------------------------------------------------------
# Request and Response Schemas
# ---------------------------------------------------------------------------


class PlanCreateRequest(BaseModel):
    """Payload for plan retrieval or initialization."""

    model_config = ConfigDict(extra="ignore")

    lease_token: Optional[str] = Field(default=None, description="Active executor tab lease token")
    mode: Optional[str] = Field(
        default=DelegationMode.DELEGATED.value,
        description="Initial operational delegation mode",
    )


class StageStepRequest(BaseModel):
    """Payload for staging normalized field values for a specific step."""

    model_config = ConfigDict(extra="ignore")

    fields: Dict[str, Any] = Field(default_factory=dict, description="Field dictionary to stage")
    facts: Optional[Dict[str, Any]] = Field(default=None, description="Raw answered facts")
    utterance: Optional[str] = Field(
        default=None,
        description="Spoken utterance to normalize into target field",
    )
    field_key: Optional[str] = Field(
        default=None,
        description="Target field key when normalizing utterance",
    )
    field_type: Optional[str] = Field(
        default="string",
        description="Field data type: string, number, duration, price, phone, email",
    )
    actor: str = Field(default="agent", description="Actor performing staging: 'agent' or 'user'")
    mode: str = Field(
        default=DelegationMode.DELEGATED.value,
        description="Current delegation mode: 'hands_off', 'guided', 'delegated', 'manual_only'",
    )
    lease_token: Optional[str] = Field(default=None, description="Active executor tab lease token")
    control_epoch: Optional[int] = Field(default=None, description="Current client control epoch")


class SaveStepRequest(BaseModel):
    """Payload for authoritative step save."""

    model_config = ConfigDict(extra="ignore")

    nonce: Optional[str] = Field(default=None, description="Single-use authorization nonce")
    lease_token: Optional[str] = Field(default=None, description="Active executor tab lease token")
    control_epoch: Optional[int] = Field(default=None, description="Current client control epoch")
    actor: str = Field(default="agent", description="Actor executing save: 'agent' or 'user'")
    mode: str = Field(
        default=DelegationMode.DELEGATED.value,
        description="Current delegation mode: 'hands_off', 'guided', 'delegated', 'manual_only'",
    )
    is_edit_mode: bool = Field(
        default=False,
        description="True if modifying an existing record rather than creating new",
    )
    is_publish: bool = Field(
        default=False,
        description="True if attempting publication (e.g. Domain 7 website)",
    )
    persisted_entity_id: Optional[str] = Field(
        default=None,
        description="Committed business entity ID",
    )
    persisted_revision: Optional[int] = Field(
        default=None,
        description="Committed business revision number",
    )


class SkipStepRequest(BaseModel):
    """Payload for skipping an optional step."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(default="", description="Reason for skipping step")
    actor: str = Field(default="user", description="Actor: 'user' or 'agent'")


class TakeoverRequest(BaseModel):
    """Payload for triggering manual takeover ('I will do this part')."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(default="user_manual_takeover", description="Takeover trigger reason")


class LeaseRequest(BaseModel):
    """Payload for acquiring or heartbeating active tab lease."""

    model_config = ConfigDict(extra="ignore")

    lease_token: Optional[str] = Field(
        default=None,
        description="Existing lease token to heartbeat, or None to allocate new",
    )
    ttl_seconds: int = Field(default=300, description="Lease time-to-live in seconds")


class NonceRequest(BaseModel):
    """Payload for issuing a single-use save authorization nonce."""

    model_config = ConfigDict(extra="ignore")

    step_id: str = Field(..., min_length=1, description="Target step identifier")
    action: str = Field(default="save", description="Action scope: 'save' or 'publish'")
    expires_in_seconds: int = Field(
        default=DelegationSaveGuard.DEFAULT_NONCE_EXPIRY_SECONDS,
        description="Nonce validity window in seconds (default 300 / 5 mins)",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/plan")
def get_or_create_plan(
    payload: Optional[PlanCreateRequest] = None,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get or create active onboarding plan for current tenant and user."""
    lease_token = payload.lease_token if payload else None
    plan = OnboardingPlanService.get_or_create_plan(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        lease_token=lease_token,
    )

    return {
        "id": plan.id,
        "tenant_id": plan.tenant_id,
        "user_id": plan.user_id,
        "status": plan.status,
        "current_step_id": plan.current_step_id,
        "control_epoch": plan.control_epoch,
        "active_lease_token": plan.active_lease_token,
        "domains_state": plan.domains_state,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "summary": OnboardingPlanService.get_plan_summary(plan),
    }


@router.get("/plan/{plan_id}")
def get_plan(
    plan_id: int = Path(..., ge=1),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve full plan state, domains progress, current step, and step details."""
    plan = OnboardingPlanService.get_plan(db=db, plan_id=plan_id, tenant_id=tenant.id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found for this tenant."},
        )

    steps_data = [
        {
            "id": step.id,
            "step_id": step.step_id,
            "domain": step.domain,
            "route": step.route,
            "form_id": step.form_id,
            "status": step.status,
            "required_facts": step.required_facts,
            "answered_facts": step.answered_facts,
            "staged_fields": step.staged_fields,
            "persisted_entity_id": step.persisted_entity_id,
            "persisted_revision": step.persisted_revision,
        }
        for step in plan.steps
    ]

    return {
        "id": plan.id,
        "tenant_id": plan.tenant_id,
        "user_id": plan.user_id,
        "status": plan.status,
        "current_step_id": plan.current_step_id,
        "control_epoch": plan.control_epoch,
        "active_lease_token": plan.active_lease_token,
        "domains_state": plan.domains_state,
        "steps": steps_data,
        "summary": OnboardingPlanService.get_plan_summary(plan),
    }


@router.post("/plan/{plan_id}/step/{step_id}/stage")
def stage_step(
    plan_id: int = Path(..., ge=1),
    step_id: str = Path(..., min_length=1),
    payload: StageStepRequest = ...,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Stage candidate field values for a step, applying Australian-English normalization."""
    plan = OnboardingPlanService.get_plan(db=db, plan_id=plan_id, tenant_id=tenant.id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found for this tenant."},
        )

    step = OnboardingPlanService.get_step_by_id(plan, step_id)
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "STEP_NOT_FOUND", "message": f"Step '{step_id}' not found in plan {plan_id}."},
        )

    # Validate epoch and lease if provided
    try:
        if payload.control_epoch is not None:
            OnboardingPlanService.validate_control_epoch(plan, payload.control_epoch)
        if payload.lease_token is not None:
            OnboardingPlanService.validate_lease(plan, payload.lease_token)
    except StaleControlEpochError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_dict())
    except LeaseExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_dict())

    # Check delegation policy for staging
    allowed, reason = DelegationSaveGuard.can_stage(
        plan=plan,
        step=step,
        actor=payload.actor,
        mode=payload.mode,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "DELEGATION_REFUSED", "message": reason},
        )

    # Process and normalize fields
    fields_to_stage = dict(payload.fields)

    # Normalize utterance if provided
    if payload.utterance and payload.field_key:
        norm_result = IntentNormalizer.normalize_field(
            field_key=payload.field_key,
            utterance=payload.utterance,
            field_type=payload.field_type or "string",
        )
        if norm_result.normalized_value is not None:
            fields_to_stage[payload.field_key] = norm_result.normalized_value

    # Normalize Australian spelling for any plain text fields in fields_to_stage
    for key, val in list(fields_to_stage.items()):
        if isinstance(val, str):
            fields_to_stage[key] = IntentNormalizer.enforce_australian_spelling(val)

    # Execute staging in plan service
    updated_step = OnboardingPlanService.stage_step_fields(
        db=db,
        plan=plan,
        step_id=step_id,
        fields=fields_to_stage,
        facts=payload.facts,
        actor=payload.actor,
    )

    return {
        "ok": True,
        "step_id": updated_step.step_id,
        "status": updated_step.status,
        "staged_fields": updated_step.staged_fields,
        "answered_facts": updated_step.answered_facts,
        "plan_summary": OnboardingPlanService.get_plan_summary(plan),
    }


@router.post("/plan/{plan_id}/step/{step_id}/save")
def save_step(
    plan_id: int = Path(..., ge=1),
    step_id: str = Path(..., min_length=1),
    payload: SaveStepRequest = ...,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Authoritative save: enforces DelegationSaveGuard, single-use nonce validation, and audit logging."""
    plan = OnboardingPlanService.get_plan(db=db, plan_id=plan_id, tenant_id=tenant.id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found for this tenant."},
        )

    step = OnboardingPlanService.get_step_by_id(plan, step_id)
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "STEP_NOT_FOUND", "message": f"Step '{step_id}' not found in plan {plan_id}."},
        )

    # Enforce delegation guard, epoch, lease, and authorization nonce
    try:
        DelegationSaveGuard.authorize_save(
            db=db,
            plan=plan,
            step=step,
            actor=payload.actor,
            mode=payload.mode,
            control_epoch=payload.control_epoch,
            lease_token=payload.lease_token,
            nonce=payload.nonce,
            is_edit_mode=payload.is_edit_mode,
            is_publish=payload.is_publish,
            user_role=getattr(user, "role", None),
        )
    except StaleControlEpochError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_dict())
    except LeaseExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_dict())
    except DelegationRefusalError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.to_dict())
    except (NonceExpiredError, NonceAlreadyUsedError, InvalidNonceError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.to_dict())
    except OnboardingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.to_dict())

    # Commit step save
    updated_step = OnboardingPlanService.commit_step_save(
        db=db,
        plan=plan,
        step_id=step_id,
        persisted_entity_id=payload.persisted_entity_id,
        persisted_revision=payload.persisted_revision,
        actor=payload.actor,
    )

    return {
        "ok": True,
        "step_id": updated_step.step_id,
        "status": updated_step.status,
        "persisted_entity_id": updated_step.persisted_entity_id,
        "persisted_revision": updated_step.persisted_revision,
        "plan_summary": OnboardingPlanService.get_plan_summary(plan),
    }


@router.post("/plan/{plan_id}/step/{step_id}/skip")
def skip_step(
    plan_id: int = Path(..., ge=1),
    step_id: str = Path(..., min_length=1),
    payload: SkipStepRequest = ...,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Skip an optional onboarding step."""
    plan = OnboardingPlanService.get_plan(db=db, plan_id=plan_id, tenant_id=tenant.id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found for this tenant."},
        )

    try:
        updated_step = OnboardingPlanService.skip_step(
            db=db,
            plan=plan,
            step_id=step_id,
            reason=payload.reason,
            actor=payload.actor,
        )
    except OnboardingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.to_dict())

    return {
        "ok": True,
        "step_id": updated_step.step_id,
        "status": updated_step.status,
        "plan_summary": OnboardingPlanService.get_plan_summary(plan),
    }


@router.post("/plan/{plan_id}/takeover")
def manual_takeover(
    plan_id: int = Path(..., ge=1),
    payload: TakeoverRequest = ...,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger manual takeover: increments control epoch, revokes active agent writes."""
    plan = OnboardingPlanService.get_plan(db=db, plan_id=plan_id, tenant_id=tenant.id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found for this tenant."},
        )

    updated_plan = OnboardingPlanService.record_manual_takeover(
        db=db,
        plan=plan,
        reason=payload.reason,
    )

    return {
        "ok": True,
        "plan_id": updated_plan.id,
        "control_epoch": updated_plan.control_epoch,
        "status": updated_plan.status,
        "reason": payload.reason,
    }


@router.post("/plan/{plan_id}/lease")
def manage_lease(
    plan_id: int = Path(..., ge=1),
    payload: LeaseRequest = ...,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Acquire or heartbeat single-tab active executor lease token."""
    plan = OnboardingPlanService.get_plan(db=db, plan_id=plan_id, tenant_id=tenant.id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found for this tenant."},
        )

    if payload.lease_token:
        # Check conflict with existing different active lease
        if plan.active_lease_token and plan.active_lease_token != payload.lease_token:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "LEASE_CONFLICT",
                    "message": "Another tab holds the active executor lease for this plan.",
                    "active_lease_token": plan.active_lease_token,
                },
            )
        plan.active_lease_token = payload.lease_token
    else:
        # Generate new lease token
        new_lease = f"lease-{secrets.token_hex(16)}"
        plan.active_lease_token = new_lease

    db.commit()
    db.refresh(plan)

    return {
        "ok": True,
        "plan_id": plan.id,
        "lease_token": plan.active_lease_token,
        "ttl_seconds": payload.ttl_seconds,
    }


@router.post("/plan/{plan_id}/nonce")
def issue_nonce(
    plan_id: int = Path(..., ge=1),
    payload: NonceRequest = ...,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Issue a cryptographically secure, tenant-scoped, single-use save authorization nonce."""
    plan = OnboardingPlanService.get_plan(db=db, plan_id=plan_id, tenant_id=tenant.id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found for this tenant."},
        )

    nonce = DelegationSaveGuard.generate_save_nonce(
        tenant_id=tenant.id,
        user_id=user.id,
        plan_id=plan.id,
        step_id=payload.step_id,
        action=payload.action,
        expires_in_seconds=payload.expires_in_seconds,
        db=db,
    )

    return {
        "ok": True,
        "plan_id": plan.id,
        "step_id": payload.step_id,
        "nonce": nonce,
        "expires_in_seconds": payload.expires_in_seconds,
    }
