from datetime import datetime
from typing import Literal, Optional
from pydantic import ConfigDict, BaseModel, Field

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
    is_pinned: bool = False
    is_blocked: bool = False
    ai_enabled: bool = True
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SmsConversationControlsUpdate(BaseModel):
    ai_enabled: Optional[bool] = None
    is_pinned: Optional[bool] = None
    is_blocked: Optional[bool] = None


class SmsDraftReviewRequest(BaseModel):
    action: Literal["approve", "discard", "edit"]
    text: Optional[str] = Field(None, min_length=1, max_length=1600)
    body: Optional[str] = Field(None, min_length=1, max_length=1600)


class SmsConversationActionRequest(BaseModel):
    reason: Optional[str] = Field(None, min_length=1, max_length=1000)


class SmsInternalNoteCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class SmsCorrectionCreate(BaseModel):
    message_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=2000)
    corrected_wording: Optional[str] = Field(None, min_length=1, max_length=2000)
    contains_dynamic_facts: bool = False


class SmsBulkDraftDiscardRequest(BaseModel):
    message_ids: list[int] = Field(..., min_length=1, max_length=250)
    reason: str = Field(..., min_length=1, max_length=1000)


class SmsOperationResponse(BaseModel):
    status: str
    detail: str


class SmsOutboundJobResponse(BaseModel):
    id: int
    message_id: int
    sms_account_id: Optional[int] = None
    status: str
    retry_count: int
    has_error: bool
    created_at: datetime


class SmsDraftQueueItem(BaseModel):
    id: int
    message_id: int
    conversation_id: int
    customer_address: str
    client_name: Optional[str] = None
    body: str
    direction: str
    author_type: str
    status: str
    occurred_at: datetime
    received_at: datetime


class SmsBulkDraftDiscardResponse(BaseModel):
    discarded_count: int


class SmsInternalNoteResponse(BaseModel):
    id: int
    created_at: datetime


class SmsCorrectionResponse(BaseModel):
    status: Literal["recorded"]
    knowledge_changed: Literal[False]
