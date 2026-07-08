from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from ..deps import get_db
from ...models.notification import DeviceToken as DeviceTokenModel
from ...schemas.notification import DeviceTokenCreate, DeviceTokenResponse

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])

@router.post("/register", response_model=DeviceTokenResponse)
def register_device(
    device_in: DeviceTokenCreate,
    db: Session = Depends(get_db)
) -> dict:
    """Register or update a user device token for push notifications."""
    # Check if token already exists
    token_record = db.query(DeviceTokenModel).filter(DeviceTokenModel.token == device_in.token).first()
    
    if token_record:
        # Update existing
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
            client_id=device_in.client_id,
            user_id=device_in.user_id,
            token=device_in.token,
            platform=device_in.platform,
            device_id=device_in.device_id,
            enabled=device_in.enabled,
            last_seen_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(token_record)
        
    db.commit()
    db.refresh(token_record)
    return {"ok": True, "data": token_record}
