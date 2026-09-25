import hashlib
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, DatabaseId
from ...models.tenant import Tenant
from ...models.user import User
from ...models.sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile
from ...models.curated_memory import CuratedMemory, KnowledgeProposal
from ...schemas.sms_settings import (
    SmsKnowledgeEntryCreate, SmsKnowledgeEntryUpdate, SmsKnowledgeEntryResponse,
    SmsPromptProfileCreate, SmsPromptProfileUpdate, SmsPromptProfileResponse
)

router = APIRouter(prefix="/sms", tags=["sms-settings"])
settings_router = APIRouter(prefix="/settings")

# --- Knowledge Base Endpoints ---

@settings_router.post("/knowledge", response_model=SmsKnowledgeEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_entry(
    payload: SmsKnowledgeEntryCreate,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if payload.provider_id:
        from ...models.provider import Provider
        prov = db.query(Provider).filter(Provider.id == payload.provider_id, Provider.tenant_id == tenant.id).first()
        if not prov:
            raise HTTPException(status_code=400, detail="Invalid provider ID for this tenant.")
            
    if payload.sms_account_id:
        from ...models.sms_account import SmsAccount
        acc = db.query(SmsAccount).filter(SmsAccount.id == payload.sms_account_id, SmsAccount.tenant_id == tenant.id).first()
        if not acc:
            raise HTTPException(status_code=400, detail="Invalid SMS account ID for this tenant.")

    entry = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=payload.provider_id,
        sms_account_id=payload.sms_account_id,
        category=payload.category,
        text=payload.text,
        source=payload.source,
        provenance=payload.provenance,
        status="approved" if payload.provenance == "manual" else "proposed"
    )
    if entry.status == "approved":
        entry.approved_at = datetime.now(timezone.utc)
        entry.approved_by_id = admin_user.id

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@settings_router.get("/knowledge", response_model=List[SmsKnowledgeEntryResponse])
async def list_knowledge_entries(
    provider_id: Optional[int] = None,
    sms_account_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(SmsKnowledgeEntry).filter(SmsKnowledgeEntry.tenant_id == tenant.id)
    
    if provider_id is not None:
        query = query.filter(SmsKnowledgeEntry.provider_id == provider_id)
    if sms_account_id is not None:
        query = query.filter(SmsKnowledgeEntry.sms_account_id == sms_account_id)
    if status_filter is not None:
        query = query.filter(SmsKnowledgeEntry.status == status_filter)
        
    return query.order_by(SmsKnowledgeEntry.created_at.desc()).all()

@settings_router.get("/knowledge/{entry_id}", response_model=SmsKnowledgeEntryResponse)
async def get_knowledge_entry(
    entry_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    entry = db.query(SmsKnowledgeEntry).filter(
        SmsKnowledgeEntry.id == entry_id,
        SmsKnowledgeEntry.tenant_id == tenant.id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")
    return entry

@settings_router.put("/knowledge/{entry_id}", response_model=SmsKnowledgeEntryResponse)
async def update_knowledge_entry(
    entry_id: DatabaseId,
    payload: SmsKnowledgeEntryUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    entry = db.query(SmsKnowledgeEntry).filter(
        SmsKnowledgeEntry.id == entry_id,
        SmsKnowledgeEntry.tenant_id == tenant.id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")

    if payload.provider_id:
        from ...models.provider import Provider
        prov = db.query(Provider).filter(Provider.id == payload.provider_id, Provider.tenant_id == tenant.id).first()
        if not prov:
            raise HTTPException(status_code=400, detail="Invalid provider ID for this tenant.")
            
    if payload.sms_account_id:
        from ...models.sms_account import SmsAccount
        acc = db.query(SmsAccount).filter(SmsAccount.id == payload.sms_account_id, SmsAccount.tenant_id == tenant.id).first()
        if not acc:
            raise HTTPException(status_code=400, detail="Invalid SMS account ID for this tenant.")

    update_data = payload.model_dump(exclude_unset=True)
    
    # Handle status transition (approving)
    if "status" in update_data and update_data["status"] == "approved" and entry.status != "approved":
        entry.approved_at = datetime.now(timezone.utc)
        entry.approved_by_id = admin_user.id

    for field, value in update_data.items():
        setattr(entry, field, value)

    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry

@settings_router.delete("/knowledge/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_entry(
    entry_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    entry = db.query(SmsKnowledgeEntry).filter(
        SmsKnowledgeEntry.id == entry_id,
        SmsKnowledgeEntry.tenant_id == tenant.id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")
    db.delete(entry)
    db.commit()


# --- Prompt Profile Endpoints ---

@settings_router.post("/prompts", response_model=SmsPromptProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_profile(
    payload: SmsPromptProfileCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if payload.provider_id:
        from ...models.provider import Provider
        prov = db.query(Provider).filter(Provider.id == payload.provider_id, Provider.tenant_id == tenant.id).first()
        if not prov:
            raise HTTPException(status_code=400, detail="Invalid provider ID for this tenant.")
            
    if payload.sms_account_id:
        from ...models.sms_account import SmsAccount
        acc = db.query(SmsAccount).filter(SmsAccount.id == payload.sms_account_id, SmsAccount.tenant_id == tenant.id).first()
        if not acc:
            raise HTTPException(status_code=400, detail="Invalid SMS account ID for this tenant.")

    if payload.provider_id is None:
        db.query(SmsPromptProfile).filter(
            SmsPromptProfile.tenant_id == tenant.id,
            SmsPromptProfile.provider_id.is_(None)
        ).update({"is_active": False}, synchronize_session=False)
    else:
        db.query(SmsPromptProfile).filter(
            SmsPromptProfile.tenant_id == tenant.id,
            SmsPromptProfile.provider_id == payload.provider_id
        ).update({"is_active": False}, synchronize_session=False)

    profile = SmsPromptProfile(
        tenant_id=tenant.id,
        provider_id=payload.provider_id,
        sms_account_id=payload.sms_account_id,
        name=payload.name,
        system_prompt=payload.system_prompt,
        is_active=True
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile

@settings_router.get("/prompts", response_model=List[SmsPromptProfileResponse])
async def list_prompt_profiles(
    provider_id: Optional[int] = None,
    sms_account_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(SmsPromptProfile).filter(SmsPromptProfile.tenant_id == tenant.id)
    
    if provider_id is not None:
        query = query.filter(SmsPromptProfile.provider_id == provider_id)
    if sms_account_id is not None:
        query = query.filter(SmsPromptProfile.sms_account_id == sms_account_id)
        
    return query.order_by(SmsPromptProfile.created_at.desc()).all()

@settings_router.get("/prompts/{profile_id}", response_model=SmsPromptProfileResponse)
async def get_prompt_profile(
    profile_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    profile = db.query(SmsPromptProfile).filter(
        SmsPromptProfile.id == profile_id,
        SmsPromptProfile.tenant_id == tenant.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Prompt profile not found.")
    return profile

@settings_router.put("/prompts/{profile_id}", response_model=SmsPromptProfileResponse)
async def update_prompt_profile(
    profile_id: DatabaseId,
    payload: SmsPromptProfileUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    profile = db.query(SmsPromptProfile).filter(
        SmsPromptProfile.id == profile_id,
        SmsPromptProfile.tenant_id == tenant.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Prompt profile not found.")

    update_data = payload.model_dump(exclude_unset=True)

    if "provider_id" in update_data and update_data["provider_id"] is not None:
        from ...models.provider import Provider
        prov = db.query(Provider).filter(Provider.id == update_data["provider_id"], Provider.tenant_id == tenant.id).first()
        if not prov:
            raise HTTPException(status_code=400, detail="Invalid provider ID for this tenant.")
            
    if "sms_account_id" in update_data and update_data["sms_account_id"] is not None:
        from ...models.sms_account import SmsAccount
        acc = db.query(SmsAccount).filter(SmsAccount.id == update_data["sms_account_id"], SmsAccount.tenant_id == tenant.id).first()
        if not acc:
            raise HTTPException(status_code=400, detail="Invalid SMS account ID for this tenant.")

    new_is_active = update_data.get("is_active", profile.is_active)
    if new_is_active:
        new_provider_id = update_data["provider_id"] if "provider_id" in update_data else profile.provider_id
        if new_provider_id is None:
            db.query(SmsPromptProfile).filter(
                SmsPromptProfile.tenant_id == tenant.id,
                SmsPromptProfile.provider_id.is_(None),
                SmsPromptProfile.id != profile.id
            ).update({"is_active": False}, synchronize_session=False)
        else:
            db.query(SmsPromptProfile).filter(
                SmsPromptProfile.tenant_id == tenant.id,
                SmsPromptProfile.provider_id == new_provider_id,
                SmsPromptProfile.id != profile.id
            ).update({"is_active": False}, synchronize_session=False)

    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile

@settings_router.delete("/prompts/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_profile(
    profile_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    profile = db.query(SmsPromptProfile).filter(
        SmsPromptProfile.id == profile_id,
        SmsPromptProfile.tenant_id == tenant.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Prompt profile not found.")
    db.delete(profile)
    db.commit()


# --- Knowledge Curator Proposals ---

class SmsProposalResolveRequest(BaseModel):
    action: str = Field(..., description="approve | dismiss | merge | reject")
    resolution_code: Optional[str] = None
    target_memory_id: Optional[int] = None
    category: Optional[str] = None
    user_query: Optional[str] = None
    ideal_response: Optional[str] = None


def _proposal_to_dict(p: KnowledgeProposal) -> dict:
    return {
        "id": p.id,
        "tenant_id": p.tenant_id,
        "provider_id": p.provider_id,
        "proposal_type": p.proposal_type,
        "status": p.status,
        "category": p.category,
        "knowledge_kind": p.knowledge_kind,
        "authority": p.authority,
        "user_query": p.user_query,
        "proposed_response": p.proposed_response,
        "target_memory_id": p.target_memory_id,
        "fingerprint": p.fingerprint,
        "reason_code": p.reason_code,
        "confidence_score": p.confidence_score,
        "contains_dynamic_fact": p.contains_dynamic_fact,
        "requires_review": p.requires_review,
        "evidence_count": p.evidence_count,
        "reviewed_by_user_id": p.reviewed_by_user_id,
        "resolution_code": p.resolution_code,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "reviewed_at": p.reviewed_at,
    }


proposals_router = APIRouter(prefix="/knowledge/proposals", tags=["sms-knowledge-proposals"])


@proposals_router.get("", response_model=List[dict])
@proposals_router.get("/", response_model=List[dict])
async def list_knowledge_proposals(
    status: Optional[str] = "pending",
    proposal_type: Optional[str] = None,
    provider_id: Optional[int] = None,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List knowledge proposals for the current tenant. Defaults to status='pending'."""
    query = db.query(KnowledgeProposal).filter(KnowledgeProposal.tenant_id == tenant.id)
    if status is not None and status.lower() != "all":
        query = query.filter(KnowledgeProposal.status == status.lower())
    if proposal_type is not None:
        query = query.filter(KnowledgeProposal.proposal_type == proposal_type)
    if provider_id is not None:
        query = query.filter(KnowledgeProposal.provider_id == provider_id)

    proposals = query.order_by(KnowledgeProposal.created_at.desc()).all()
    return [_proposal_to_dict(p) for p in proposals]


@proposals_router.post("/{proposal_id}/resolve")
async def resolve_knowledge_proposal(
    proposal_id: DatabaseId,
    payload: SmsProposalResolveRequest,
    tenant: Tenant = Depends(get_current_tenant),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Resolve a knowledge proposal with action: approve, dismiss, merge, or reject.

    If approved: safely creates/activates CuratedMemory and SmsKnowledgeEntry for tenant.
    """
    proposal = (
        db.query(KnowledgeProposal)
        .filter(
            KnowledgeProposal.id == proposal_id,
            KnowledgeProposal.tenant_id == tenant.id,
        )
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Knowledge proposal not found.")

    action = payload.action.lower().strip()
    if action not in ("approve", "dismiss", "merge", "reject"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{payload.action}'. Allowed actions: approve, dismiss, merge, reject",
        )

    now = datetime.now(timezone.utc)

    if action == "approve":
        category = payload.category or proposal.category or "faq"
        user_query = (payload.user_query if payload.user_query is not None else proposal.user_query) or "General Inquiry"
        ideal_response = (payload.ideal_response if payload.ideal_response is not None else proposal.proposed_response) or ""

        # Safely create CuratedMemory for the tenant
        content_hash = hashlib.sha256(f"{user_query}::{ideal_response}".encode("utf-8")).hexdigest()
        curated = CuratedMemory(
            tenant_id=tenant.id,
            provider_id=proposal.provider_id,
            category=category,
            user_query=user_query,
            ideal_response=ideal_response,
            confidence_score=1.0,
            knowledge_kind="durable_fact",
            authority="owner_verified",
            status="active",
            conflict_state="clear",
            content_hash=content_hash,
            source_reference=f"proposal:{proposal.id}",
            verified_by_user_id=admin_user.id,
            last_verified_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(curated)
        db.flush()

        # Also create approved SmsKnowledgeEntry
        knowledge_text = f"Q: {user_query}\nA: {ideal_response}" if user_query != "General Inquiry" else ideal_response
        knowledge_entry = SmsKnowledgeEntry(
            tenant_id=tenant.id,
            provider_id=proposal.provider_id,
            category=category,
            text=knowledge_text,
            source=f"proposal:{proposal.id}",
            status="approved",
            provenance="info_request" if proposal.proposal_type == "gap" else "manual",
            approved_at=now,
            approved_by_id=admin_user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(knowledge_entry)

        proposal.status = "accepted"
        proposal.resolution_code = payload.resolution_code or "approved"
        proposal.target_memory_id = curated.id
        proposal.reviewed_by_user_id = admin_user.id
        proposal.reviewed_at = now
        proposal.updated_at = now

    elif action in ("dismiss", "reject"):
        proposal.status = "dismissed" if action == "dismiss" else "rejected"
        proposal.resolution_code = payload.resolution_code or action
        proposal.reviewed_by_user_id = admin_user.id
        proposal.reviewed_at = now
        proposal.updated_at = now

    elif action == "merge":
        target_id = payload.target_memory_id or proposal.target_memory_id
        if target_id:
            target_mem = (
                db.query(CuratedMemory)
                .filter(
                    CuratedMemory.id == target_id,
                    CuratedMemory.tenant_id == tenant.id,
                )
                .first()
            )
            if not target_mem:
                raise HTTPException(status_code=404, detail="Target curated memory not found for merge.")
            if payload.ideal_response:
                target_mem.ideal_response = payload.ideal_response
            target_mem.updated_at = now
            target_mem.last_verified_at = now
            target_mem.verified_by_user_id = admin_user.id
            proposal.target_memory_id = target_mem.id
        else:
            category = payload.category or proposal.category or "faq"
            user_query = (payload.user_query if payload.user_query is not None else proposal.user_query) or "General Inquiry"
            ideal_response = (payload.ideal_response if payload.ideal_response is not None else proposal.proposed_response) or ""
            content_hash = hashlib.sha256(f"{user_query}::{ideal_response}".encode("utf-8")).hexdigest()
            curated = CuratedMemory(
                tenant_id=tenant.id,
                provider_id=proposal.provider_id,
                category=category,
                user_query=user_query,
                ideal_response=ideal_response,
                confidence_score=1.0,
                knowledge_kind="durable_fact",
                authority="owner_verified",
                status="active",
                conflict_state="clear",
                content_hash=content_hash,
                source_reference=f"proposal:{proposal.id}",
                verified_by_user_id=admin_user.id,
                last_verified_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(curated)
            db.flush()
            proposal.target_memory_id = curated.id

        proposal.status = "resolved"
        proposal.resolution_code = payload.resolution_code or "merged"
        proposal.reviewed_by_user_id = admin_user.id
        proposal.reviewed_at = now
        proposal.updated_at = now

    db.commit()
    db.refresh(proposal)
    return {
        "status": "success",
        "action": action,
        "proposal": _proposal_to_dict(proposal),
    }


router.include_router(settings_router)
router.include_router(proposals_router)
