from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import DatabaseId, get_db, get_public_tenant
from ...core.security import decode_access_token
from ...models.client import Client
from ...models.notification import DeviceToken as DeviceTokenModel
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.notification import DeviceTokenCreate, DeviceTokenResponse

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.post("/register", response_model=DeviceTokenResponse)
def register_device(
    device_in: DeviceTokenCreate,
    request: Request,
    tenant: Tenant = Depends(get_public_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Register or update a user device token bound to the active tenant."""
    tenant_id = tenant.id

    # 1. Check for token-based authentication / subject identity
    x_token = request.headers.get("X-Token")
    if x_token:
        payload = decode_access_token(x_token)
        if payload and "sub" in payload:
            sub = payload["sub"]
            try:
                uid = int(sub)
                user = db.query(User).filter(User.id == uid, User.tenant_id == tenant_id).first()
                if user:
                    if device_in.user_id is None:
                        device_in.user_id = user.id
                else:
                    client = db.query(Client).filter(Client.id == uid, Client.tenant_id == tenant_id).first()
                    if client:
                        if device_in.client_id is None:
                            device_in.client_id = client.id
            except (ValueError, TypeError):
                pass

    # 2. Validate user_id / client_id strictly within the active tenant
    if device_in.user_id is not None:
        user = db.query(User).filter(User.id == device_in.user_id, User.tenant_id == tenant_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant")

    if device_in.client_id is not None:
        client = db.query(Client).filter(Client.id == device_in.client_id, Client.tenant_id == tenant_id).first()
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found in this tenant")

    # 3. Check if token already exists
    token_record = db.query(DeviceTokenModel).filter(DeviceTokenModel.token == device_in.token).first()

    if token_record:
        # Update existing
        token_record.tenant_id = tenant_id
        token_record.client_id = device_in.client_id
        token_record.user_id = device_in.user_id
        token_record.platform = device_in.platform
        token_record.device_id = device_in.device_id
        token_record.enabled = device_in.enabled
        token_record.last_seen_at = datetime.utcnow()
        token_record.updated_at = datetime.utcnow()
    else:
        # Create new
        token_record = DeviceTokenModel(
            tenant_id=tenant_id,
            client_id=device_in.client_id,
            user_id=device_in.user_id,
            token=device_in.token,
            platform=device_in.platform,
            device_id=device_in.device_id,
            enabled=device_in.enabled,
            last_seen_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(token_record)

    db.commit()
    db.refresh(token_record)
    return {"ok": True, "data": token_record}

