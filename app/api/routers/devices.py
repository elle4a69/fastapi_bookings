from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from ..deps import get_db, DatabaseId
from ...models.notification import DeviceToken as DeviceTokenModel
from ...models.tenant import Tenant
from ...models.user import User
from ...models.client import Client
from ...schemas.notification import DeviceTokenCreate, DeviceTokenResponse

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


def _resolve_tenant_id(request: Request, db: Session, device_in: DeviceTokenCreate) -> Optional[int]:
    """Resolve and validate tenant ownership for device registration."""
    # 1. Resolve from authenticated user or client reference if supplied
    if device_in.user_id:
        user = db.query(User).filter(User.id == device_in.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if device_in.client_id:
            client = db.query(Client).filter(Client.id == device_in.client_id).first()
            if not client or client.tenant_id != user.tenant_id:
                raise HTTPException(status_code=400, detail="Client and user tenant mismatch")
        return user.tenant_id

    if device_in.client_id:
        client = db.query(Client).filter(Client.id == device_in.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client.tenant_id

    # 2. Check header or query param
    subdomain = request.headers.get("X-Tenant") or request.query_params.get("tenant")
    if subdomain:
        tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain.lower()).first()
        if tenant:
            return tenant.id

    # 3. Default to first active tenant if available
    tenant = db.query(Tenant).first()
    return tenant.id if tenant else None


@router.post("/register", response_model=DeviceTokenResponse)
def register_device(
    device_in: DeviceTokenCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Register or update a user device token for push notifications with tenant isolation."""
    tenant_id = _resolve_tenant_id(request, db, device_in)

    # Check if token already exists
    token_record = db.query(DeviceTokenModel).filter(DeviceTokenModel.token == device_in.token).first()

    now = datetime.now(timezone.utc)
    if token_record:
        # Cross-tenant hijack protection
        if token_record.tenant_id is not None and tenant_id is not None and token_record.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device token already registered under another tenant",
            )
        # Update existing
        token_record.tenant_id = tenant_id or token_record.tenant_id
        token_record.client_id = device_in.client_id
        token_record.user_id = device_in.user_id
        token_record.platform = device_in.platform
        token_record.device_id = device_in.device_id
        token_record.enabled = device_in.enabled
        token_record.last_seen_at = now
        token_record.updated_at = now
    else:
        # Create new with tenant_id populated
        token_record = DeviceTokenModel(
            tenant_id=tenant_id,
            client_id=device_in.client_id,
            user_id=device_in.user_id,
            token=device_in.token,
            platform=device_in.platform,
            device_id=device_in.device_id,
            enabled=device_in.enabled,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(token_record)

    db.commit()
    db.refresh(token_record)
    return {"ok": True, "data": token_record}
