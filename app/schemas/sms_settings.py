from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SmsKnowledgeEntryCreate(BaseModel):
    provider_id: Optional[int] = None
    sms_account_id: Optional[int] = None
    category: str
    text: str
    source: Optional[str] = None
    provenance: str = "manual"

class SmsKnowledgeEntryUpdate(BaseModel):
    category: Optional[str] = None
    text: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None  # 'proposed', 'approved', 'rejected', 'archived'

class SmsKnowledgeEntryResponse(BaseModel):
    id: int
    tenant_id: int
    provider_id: Optional[int] = None
    sms_account_id: Optional[int] = None
    category: str
    text: str
    source: Optional[str] = None
    status: str
    provenance: str
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    approved_by_id: Optional[int] = None

    class Config:
        from_attributes = True


class SmsPromptProfileCreate(BaseModel):
    provider_id: Optional[int] = None
    sms_account_id: Optional[int] = None
    name: str
    system_prompt: str

class SmsPromptProfileUpdate(BaseModel):
    provider_id: Optional[int] = None
    sms_account_id: Optional[int] = None
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None

class SmsPromptProfileResponse(BaseModel):
    id: int
    tenant_id: int
    provider_id: Optional[int] = None
    sms_account_id: Optional[int] = None
    name: str
    system_prompt: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
