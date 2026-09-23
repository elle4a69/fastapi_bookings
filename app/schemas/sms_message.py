from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, BaseModel, Field, field_validator

class SmsMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=1600)
    client_request_id: str = Field(..., min_length=8, max_length=128)

    @field_validator("body")
    @classmethod
    def strip_non_empty_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("client_request_id")
    @classmethod
    def strip_valid_request_id(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 8:
            raise ValueError("must contain at least 8 non-whitespace characters")
        return value

class SmsMessageResponse(BaseModel):
    id: int
    tenant_id: int
    provider_id: int
    sms_account_id: Optional[int] = None
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

    model_config = ConfigDict(from_attributes=True)
