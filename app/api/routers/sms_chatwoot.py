from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, DatabaseId
from ...models.tenant import Tenant
from ...models.user import User
from ...models.sms_chatwoot import SmsChatwootBinding
from ...schemas.sms_chatwoot import (
    SmsChatwootBindingCreate,
    SmsChatwootBindingUpdate,
    SmsChatwootBindingResponse,
)

router = APIRouter(prefix="/sms/chatwoot", tags=["sms-chatwoot"])

def to_response(binding: SmsChatwootBinding, request: Optional[Request] = None) -> SmsChatwootBindingResponse:
    """Helper to convert SmsChatwootBinding to Response schema, masking the API token."""
    base = "http://localhost:8000"
    if request:
        base = str(request.base_url).rstrip("/")
        
    secret = binding.webhook_secret
    webhook_url = f"{base}/api/sms/chatwoot/webhook?token={secret}" if secret else None

    return SmsChatwootBindingResponse(
        id=binding.id,
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        chatwoot_account_id=binding.chatwoot_account_id,
        chatwoot_inbox_id=binding.chatwoot_inbox_id,
        chatwoot_base_url=binding.chatwoot_base_url,
        chatwoot_api_token="********",
        webhook_secret="********",
        webhook_url=webhook_url,
        is_enabled=binding.is_enabled,
        channel_metadata=binding.channel_metadata,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )

# Webhook receiver
@router.post("/webhook")
async def chatwoot_webhook(
    request: Request,
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Chatwoot incoming webhook receiver endpoint."""
    if not token:
        token = request.query_params.get("token") or request.headers.get("X-Chatwoot-Token") or request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token[7:]

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    from ...services.sms.chatwoot_service import process_chatwoot_webhook
    result = process_chatwoot_webhook(db, payload, token)
    return result

# CRUD Settings Endpoints
@router.post("/bindings", response_model=SmsChatwootBindingResponse, status_code=status.HTTP_201_CREATED)
async def create_chatwoot_binding(
    payload: SmsChatwootBindingCreate,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create a new Chatwoot binding."""
    import secrets
    webhook_secret = secrets.token_hex(32)
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=payload.provider_id,
        chatwoot_account_id=payload.chatwoot_account_id,
        chatwoot_inbox_id=payload.chatwoot_inbox_id,
        chatwoot_base_url=payload.chatwoot_base_url,
        chatwoot_api_token=payload.chatwoot_api_token,
        webhook_secret=webhook_secret,
        is_enabled=payload.is_enabled,
        channel_metadata=payload.channel_metadata,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return to_response(binding, request)

@router.get("/bindings", response_model=List[SmsChatwootBindingResponse])
async def list_chatwoot_bindings(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all Chatwoot bindings for the current tenant."""
    bindings = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.tenant_id == tenant.id
    ).all()
    return [to_response(b, request) for b in bindings]

@router.get("/bindings/{binding_id}", response_model=SmsChatwootBindingResponse)
async def get_chatwoot_binding(
    binding_id: DatabaseId,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get a specific Chatwoot binding."""
    binding = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.id == binding_id,
        SmsChatwootBinding.tenant_id == tenant.id
    ).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Chatwoot binding not found.")
    return to_response(binding, request)

@router.put("/bindings/{binding_id}", response_model=SmsChatwootBindingResponse)
async def update_chatwoot_binding(
    binding_id: DatabaseId,
    payload: SmsChatwootBindingUpdate,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update a specific Chatwoot binding."""
    binding = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.id == binding_id,
        SmsChatwootBinding.tenant_id == tenant.id
    ).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Chatwoot binding not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "chatwoot_api_token":
            if value == "********" or not value:
                continue
            binding.chatwoot_api_token = value
        else:
            setattr(binding, field, value)

    binding.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(binding)
    return to_response(binding, request)

@router.post("/bindings/{binding_id}/rotate-secret", response_model=SmsChatwootBindingResponse)
async def rotate_chatwoot_webhook_secret(
    binding_id: DatabaseId,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Rotate the webhook secret for a specific Chatwoot binding."""
    binding = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.id == binding_id,
        SmsChatwootBinding.tenant_id == tenant.id
    ).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Chatwoot binding not found.")

    import secrets
    binding.webhook_secret = secrets.token_hex(32)
    binding.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(binding)
    return to_response(binding, request)

@router.delete("/bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chatwoot_binding(
    binding_id: DatabaseId,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a specific Chatwoot binding."""
    binding = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.id == binding_id,
        SmsChatwootBinding.tenant_id == tenant.id
    ).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Chatwoot binding not found.")
    db.delete(binding)
    db.commit()
