from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import DatabaseId, get_db
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
    db: Session = Depends(get_db),
) -> dict:
    """Register or update a user device token bound to the active tenant."""
    tenant_id: Optional[int] = None

    # 1. Check for token-based authentication / subject identity
    x_token = request.headers.get("X-Token")
    if x_token:
        payload = decode_access_token(x_token)
        if payload and "sub" in payload:
            sub = payload["sub"]
            try:
                uid = int(sub)
                user = db.query(User).filter(User.id == uid).first()
                if user:
                    tenant_id = user.tenant_id
                    if device_in.user_id is None:
                        device_in.user_id = user.id
                else:
                    client = db.query(Client).filter(Client.id == uid).first()
                    if client:
                        tenant_id = client.tenant_id
                        if device_in.client_id is None:
                            device_in.client_id = client.id
            except (ValueError, TypeError):
                pass

    # 2. Check X-Tenant header, query param, or host subdomain
    subdomain = request.headers.get("X-Tenant") or request.query_params.get("tenant")
    if not subdomain:
        host = request.headers.get("host", "")
        parts = host.split(":")
        hostname = parts[0]
        host_parts = hostname.split(".")
        if len(host_parts) > 1 and not hostname.endswith(".run.app"):
            first_part = host_parts[0]
            if first_part.lower() not in ("www", "api", "localhost", "127"):
                subdomain = first_part

    if subdomain:
        tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain.lower()).first()
        if not tenant:
            raise HTTPException(status_code=404, detail=f"Tenant '{subdomain}' not found")
        tenant_id = tenant.id

    # 3. Validate user_id / client_id within tenant if provided
    if tenant_id is not None:
        if device_in.user_id is not None:
            user = db.query(User).filter(User.id == device_in.user_id, User.tenant_id == tenant_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found in this tenant")
        if device_in.client_id is not None:
            client = db.query(Client).filter(Client.id == device_in.client_id, Client.tenant_id == tenant_id).first()
            if not client:
                raise HTTPException(status_code=404, detail="Client not found in this tenant")
    else:
        if device_in.user_id is not None:
            user = db.query(User).filter(User.id == device_in.user_id).first()
            if user:
                tenant_id = user.tenant_id
            else:
                raise HTTPException(status_code=404, detail="User not found")
        elif device_in.client_id is not None:
            client = db.query(Client).filter(Client.id == device_in.client_id).first()
            if client:
                tenant_id = client.tenant_id
            else:
                raise HTTPException(status_code=404, detail="Client not found")

    # 4. Fallback to default tenant if available in unadorned environment
    if tenant_id is None:
        first_tenant = db.query(Tenant).first()
        if first_tenant:
            tenant_id = first_tenant.id

    # Check if token already exists
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
