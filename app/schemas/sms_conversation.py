from datetime import datetime
from typing import Optional, Literal
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


class SmsQuickToolItem(BaseModel):
    id: Optional[int] = None
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    slot_index: int = Field(..., ge=0, le=4)
    label: str = Field(..., min_length=1, max_length=8)
    content: str
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SmsQuickToolCreate(BaseModel):
    slot_index: int = Field(..., ge=0, le=4)
    label: str = Field(..., min_length=1, max_length=8)
    content: str


class SmsAnswerInfoRequest(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = "faq"
    knowledge: Optional[str] = None
    reply: Optional[str] = None
    auto_curate: Optional[bool] = None


class SmsAnswerInfoResponse(BaseModel):
    success: bool = True
    curated_memory_id: int
    proposed_reply: str
    draft_message_id: Optional[int] = None


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


class SmsSimulateInboundRequest(BaseModel):
    account_id: Optional[int] = None
    sender: str
    message: str
    execute_dialogue_turn: Optional[bool] = True


class SmsSeedScenariosRequest(BaseModel):
    account_id: Optional[int] = None
    clear_existing: Optional[bool] = False


class SmsSeedScenariosResponse(BaseModel):
    success: bool = True
    scenarios_count: int
    conversations_count: int
    arrivals_count: int
    drafts_count: int
    message: str
