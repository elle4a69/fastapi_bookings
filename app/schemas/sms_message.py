from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel

class SmsMessageCreate(BaseModel):
    body: str
    client_request_id: Optional[str] = None

class SmsMessageResponse(BaseModel):
    id: int
    tenant_id: int
    provider_id: int
    sms_account_id: int
    conversation_id: int
    body: str
    direction: str
    author_type: str
    author_id: Optional[int] = None
    status: str
    provider_message_id: Optional[str] = None
    parent_message_id: Optional[int] = None
    client_request_id: Optional[str] = None
    customer_turn_ref: Optional[str] = None
    occurred_at: datetime
    received_at: datetime

    class Config:
        from_attributes = True
