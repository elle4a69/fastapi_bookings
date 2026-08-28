from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import ConfigDict, BaseModel, Field

class SmsAccountBase(BaseModel):
    display_name: str
    transport_type: str = Field(description="e.g. 'simulator', 'mobilemessage'")
    sender_address: str = Field(description="E.164 phone number")
    autoresponder_enabled: bool = False
    autoresponder_text: Optional[str] = None
    ai_enabled: bool = False
    ai_mode: str = "off"
    line_prompt: Optional[str] = None
    catchup_cutoff_days: int = 30
    is_enabled: bool = True

class SmsAccountCreate(SmsAccountBase):
    provider_id: int
    credentials: Optional[Dict[str, Any]] = None

class SmsAccountUpdate(BaseModel):
    display_name: Optional[str] = None
    sender_address: Optional[str] = None
    autoresponder_enabled: Optional[bool] = None
    autoresponder_text: Optional[str] = None
    ai_enabled: Optional[bool] = None
    ai_mode: Optional[str] = None
    line_prompt: Optional[str] = None
    catchup_cutoff_days: Optional[int] = None
    is_enabled: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None

class SmsAccountResponse(SmsAccountBase):
    id: int
    public_id: str
    tenant_id: int
    provider_id: int
    has_credentials: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
