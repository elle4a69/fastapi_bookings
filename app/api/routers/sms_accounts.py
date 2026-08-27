from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...models.tenant import Tenant
from ...models.user import User
from ...models.sms_account import SmsAccount
from ...schemas.sms_account import SmsAccountCreate, SmsAccountUpdate, SmsAccountResponse

router = APIRouter(prefix="/sms/accounts", tags=["sms-accounts"])

def redact_credentials(account: SmsAccount) -> SmsAccountResponse:
    """Helper to convert SmsAccount to SmsAccountResponse, redacting raw passwords."""
    has_creds = False
    if account.credentials:
        # Check if there is password or secret
        has_creds = any(k in account.credentials for k in ("password", "api_key", "secret"))
        
    return SmsAccountResponse(
        id=account.id,
        public_id=account.public_id,
        tenant_id=account.tenant_id,
        provider_id=account.provider_id,
        display_name=account.display_name,
        transport_type=account.transport_type,
        sender_address=account.sender_address,
        autoresponder_enabled=account.autoresponder_enabled,
        autoresponder_text=account.autoresponder_text,
        ai_enabled=account.ai_enabled,
        ai_mode=account.ai_mode,
        line_prompt=account.line_prompt,
        catchup_cutoff_days=account.catchup_cutoff_days,
        is_enabled=account.is_enabled,
        has_credentials=has_creds,
        created_at=account.created_at,
        updated_at=account.updated_at
    )

@router.post("", response_model=SmsAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_sms_account(
    payload: SmsAccountCreate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Verify account sender address is normalized
    from ...services.sms.transports.base import normalize_sms_destination
    norm_address = normalize_sms_destination(payload.sender_address)
    if not norm_address:
        raise HTTPException(status_code=422, detail="Sender address must be a valid E.164 phone number.")

    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=payload.provider_id,
        transport_type=payload.transport_type,
        display_name=payload.display_name,
        sender_address=norm_address,
        credentials=payload.credentials or {},
        is_enabled=payload.is_enabled,
        autoresponder_enabled=payload.autoresponder_enabled,
        autoresponder_text=payload.autoresponder_text,
        ai_enabled=payload.ai_enabled,
        ai_mode=payload.ai_mode,
        line_prompt=payload.line_prompt,
        catchup_cutoff_days=payload.catchup_cutoff_days
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return redact_credentials(account)

@router.get("", response_model=List[SmsAccountResponse])
async def list_sms_accounts(
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    accounts = db.query(SmsAccount).filter(SmsAccount.tenant_id == tenant.id).all()
    return [redact_credentials(acc) for acc in accounts]

@router.get("/{account_id}", response_model=SmsAccountResponse)
async def get_sms_account(
    account_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    account = db.query(SmsAccount).filter(
        SmsAccount.id == account_id,
        SmsAccount.tenant_id == tenant.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="SMS account not found.")
    return redact_credentials(account)

@router.put("/{account_id}", response_model=SmsAccountResponse)
async def update_sms_account(
    account_id: int,
    payload: SmsAccountUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    account = db.query(SmsAccount).filter(
        SmsAccount.id == account_id,
        SmsAccount.tenant_id == tenant.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="SMS account not found.")

    update_data = payload.model_dump(exclude_unset=True)
    
    # Handle credentials merge
    if "credentials" in update_data:
        existing_creds = dict(account.credentials or {})
        new_creds = update_data.pop("credentials") or {}
        # Merge, but if a password/secret key is empty, preserve existing value (do not overwrite with empty)
        for k, v in new_creds.items():
            if v == "" and k in existing_creds:
                continue
            existing_creds[k] = v
        account.credentials = existing_creds

    for field, value in update_data.items():
        if field == "sender_address" and value:
            from ...services.sms.transports.base import normalize_sms_destination
            value = normalize_sms_destination(value)
            if not value:
                raise HTTPException(status_code=422, detail="Sender address must be a valid E.164 phone number.")
        setattr(account, field, value)

    account.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(account)
    return redact_credentials(account)

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sms_account(
    account_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    account = db.query(SmsAccount).filter(
        SmsAccount.id == account_id,
        SmsAccount.tenant_id == tenant.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="SMS account not found.")
    db.delete(account)
    db.commit()
