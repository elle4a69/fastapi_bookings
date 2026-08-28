from datetime import datetime
from typing import Optional
from pydantic import ConfigDict, BaseModel

class SmsConversationResponse(BaseModel):
    id: int
    tenant_id: int
    provider_id: Optional[int] = None
    sms_account_id: Optional[int] = None
    customer_address: str
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    state: str
    unread_count: int
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
