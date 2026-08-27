from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class SmsConversationResponse(BaseModel):
    id: int
    tenant_id: int
    provider_id: int
    sms_account_id: int
    customer_address: str
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    state: str
    unread_count: int
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
