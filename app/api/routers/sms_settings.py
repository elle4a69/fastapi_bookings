from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, DatabaseId
from ...models.tenant import Tenant
from ...models.user import User
from ...models.sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile
from ...schemas.sms_settings import (
    SmsKnowledgeEntryCreate, SmsKnowledgeEntryUpdate, SmsKnowledgeEntryResponse,
    SmsPromptProfileCreate, SmsPromptProfileUpdate, SmsPromptProfileResponse
)

router = APIRouter(prefix="/sms/settings", tags=["sms-settings"])

# --- Knowledge Base Endpoints ---

@router.post("/knowledge", response_model=SmsKnowledgeEntryResponse, status_code=status.HTTP_201_CREATED)
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

@router.get("/knowledge", response_model=List[SmsKnowledgeEntryResponse])
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

@router.get("/knowledge/{entry_id}", response_model=SmsKnowledgeEntryResponse)
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

@router.put("/knowledge/{entry_id}", response_model=SmsKnowledgeEntryResponse)
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

@router.delete("/knowledge/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
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

@router.post("/prompts", response_model=SmsPromptProfileResponse, status_code=status.HTTP_201_CREATED)
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

@router.get("/prompts", response_model=List[SmsPromptProfileResponse])
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

@router.get("/prompts/{profile_id}", response_model=SmsPromptProfileResponse)
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

@router.put("/prompts/{profile_id}", response_model=SmsPromptProfileResponse)
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

@router.delete("/prompts/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
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
