from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db, DatabaseId
from ...models.tenant import Tenant
from ...models.provider import Provider
from ...models.location import Location
from ...models.user import User
from ...models.sms_chatwoot import SmsChatwootBinding
from ...schemas.sms_chatwoot import (
    SmsChatwootBindingCreate,
    SmsChatwootBindingUpdate,
    SmsChatwootBindingResponse,
)

import logging
from ...services.sms.chatwoot_service import generate_webhook_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms/chatwoot", tags=["sms-chatwoot"])

def to_response(binding: SmsChatwootBinding, request: Optional[Request] = None) -> SmsChatwootBindingResponse:
    """Helper to convert SmsChatwootBinding to Response schema, masking the API token."""
    base = "http://localhost:8000"
    if request:
        base = str(request.base_url).rstrip("/")
        
    secret = binding.webhook_secret
    webhook_url = generate_webhook_url(base) if secret else None

    return SmsChatwootBindingResponse(
        id=binding.id,
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        location_id=binding.location_id,
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
    raw_body = await request.body()
    try:
        import json
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    header_token = request.headers.get("X-Chatwoot-Token") or request.headers.get("Authorization")
    if header_token and header_token.startswith("Bearer "):
        header_token = header_token[7:].strip()

    query_token = request.query_params.get("token") or token
    if query_token and not header_token:
        logger.warning(
            "Passing Chatwoot webhook token via query parameter ?token= is deprecated and insecure. "
            "Use X-Chatwoot-Token, Authorization, or X-Chatwoot-Signature headers instead."
        )
        effective_token = query_token
    else:
        effective_token = header_token or query_token
    token = effective_token

    signature_header = request.headers.get("X-Chatwoot-Signature")
    timestamp_header = (
        request.headers.get("X-Chatwoot-Signature-Timestamp")
        or request.headers.get("X-Chatwoot-Timestamp")
        or request.query_params.get("timestamp")
    )

    from ...services.sms.chatwoot_service import process_chatwoot_webhook
    result = process_chatwoot_webhook(
        db=db,
        payload=payload,
        token=token,
        raw_body=raw_body,
        signature_header=signature_header,
        timestamp_header=timestamp_header,
        headers=dict(request.headers),
    )
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
    # 1. Validate provider and location belong to tenant if supplied
    if payload.provider_id is not None:
        provider = db.query(Provider).filter(
            Provider.id == payload.provider_id,
            Provider.tenant_id == tenant.id,
        ).first()
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider does not belong to the current tenant.",
            )

    if payload.location_id is not None:
        location = db.query(Location).filter(
            Location.id == payload.location_id,
            Location.tenant_id == tenant.id,
        ).first()
        if not location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Location does not belong to the current tenant.",
            )

    # 2. Enforce Tenant <-> Chatwoot Account 1-to-1 mapping
    if tenant.chatwoot_account_id is not None:
        if payload.chatwoot_account_id is not None and tenant.chatwoot_account_id != payload.chatwoot_account_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot bind to a Chatwoot account outside your tenancy.",
            )
        account_id_to_use = tenant.chatwoot_account_id
    else:
        if payload.chatwoot_account_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chatwoot_account_id is required when tenant does not have a linked account.",
            )
        existing_tenant = db.query(Tenant).filter(
            Tenant.chatwoot_account_id == payload.chatwoot_account_id,
            Tenant.id != tenant.id,
        ).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chatwoot account {payload.chatwoot_account_id} is already mapped to another tenant.",
            )
        tenant.chatwoot_account_id = payload.chatwoot_account_id
        account_id_to_use = payload.chatwoot_account_id

    # 3. Check inbox uniqueness across tenants
    existing_inbox = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.chatwoot_inbox_id == payload.chatwoot_inbox_id,
        SmsChatwootBinding.is_enabled == True,
    ).first()
    if existing_inbox and existing_inbox.tenant_id != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chatwoot inbox {payload.chatwoot_inbox_id} is already bound to another tenant.",
        )

    from ...core.config import settings
    chatwoot_base_url_to_use = payload.chatwoot_base_url or settings.CHATWOOT_BASE_URL
    chatwoot_api_token_to_use = payload.chatwoot_api_token or settings.CHATWOOT_API_ACCESS_TOKEN or settings.CHATWOOT_PLATFORM_ACCESS_TOKEN

    import secrets
    webhook_secret = secrets.token_hex(32)
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=payload.provider_id,
        location_id=payload.location_id,
        chatwoot_account_id=account_id_to_use,
        chatwoot_inbox_id=payload.chatwoot_inbox_id,
        chatwoot_base_url=chatwoot_base_url_to_use,
        chatwoot_api_token=chatwoot_api_token_to_use,
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

    if "chatwoot_account_id" in update_data and update_data["chatwoot_account_id"] is not None and update_data["chatwoot_account_id"] != binding.chatwoot_account_id:
        new_account_id = update_data["chatwoot_account_id"]
        if tenant.chatwoot_account_id is not None and tenant.chatwoot_account_id != new_account_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot bind to a Chatwoot account outside your tenancy.",
            )
        existing_tenant = db.query(Tenant).filter(
            Tenant.chatwoot_account_id == new_account_id,
            Tenant.id != tenant.id,
        ).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chatwoot account {new_account_id} is already mapped to another tenant.",
            )
        tenant.chatwoot_account_id = new_account_id

    if "chatwoot_inbox_id" in update_data and update_data["chatwoot_inbox_id"] != binding.chatwoot_inbox_id:
        existing_inbox = db.query(SmsChatwootBinding).filter(
            SmsChatwootBinding.chatwoot_inbox_id == update_data["chatwoot_inbox_id"],
            SmsChatwootBinding.id != binding.id,
            SmsChatwootBinding.is_enabled == True,
        ).first()
        if existing_inbox and existing_inbox.tenant_id != tenant.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chatwoot inbox {update_data['chatwoot_inbox_id']} is already bound to another tenant.",
            )

    if "provider_id" in update_data and update_data["provider_id"] is not None:
        prov = db.query(Provider).filter(
            Provider.id == update_data["provider_id"],
            Provider.tenant_id == tenant.id,
        ).first()
        if not prov:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider does not belong to the current tenant.",
            )

    if "location_id" in update_data and update_data["location_id"] is not None:
        loc = db.query(Location).filter(
            Location.id == update_data["location_id"],
            Location.tenant_id == tenant.id,
        ).first()
        if not loc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Location does not belong to the current tenant.",
            )

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


class ChatwootProvisionRequest(BaseModel):
    provider_ids: Optional[List[int]] = None


@router.post("/provision")
def trigger_chatwoot_provisioning(
    payload: Optional[ChatwootProvisionRequest] = None,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Trigger automated Chatwoot provisioning for the current tenant and providers."""
    from ...services.sms.chatwoot_provisioning_service import provision_tenant_chatwoot
    provider_ids = payload.provider_ids if payload else None
    result = provision_tenant_chatwoot(db=db, tenant_id=tenant.id, provider_ids=provider_ids)
    if not result.success and result.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chatwoot provisioning failed: {result.error_message}",
        )
    return result
