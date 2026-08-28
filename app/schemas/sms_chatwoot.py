from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import ConfigDict, BaseModel, Field

class SmsChatwootBindingBase(BaseModel):
    chatwoot_account_id: int
    chatwoot_inbox_id: int
    chatwoot_base_url: str
    is_enabled: bool = True
    channel_metadata: Optional[Dict[str, Any]] = None

class SmsChatwootBindingCreate(SmsChatwootBindingBase):
    provider_id: int
    chatwoot_api_token: str

class SmsChatwootBindingUpdate(BaseModel):
    chatwoot_account_id: Optional[int] = None
    chatwoot_inbox_id: Optional[int] = None
    chatwoot_base_url: Optional[str] = None
    chatwoot_api_token: Optional[str] = None
    is_enabled: Optional[bool] = None
    channel_metadata: Optional[Dict[str, Any]] = None

class SmsChatwootBindingResponse(SmsChatwootBindingBase):
    id: int
    tenant_id: int
    provider_id: int
    chatwoot_api_token: str = "********"
    webhook_secret: str = "********"
    webhook_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
