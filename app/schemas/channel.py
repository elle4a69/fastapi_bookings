"""Pydantic schemas for Channel Accounts."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from ..models.conversation import ChannelType


class ChannelAccountBase(BaseModel):
    provider_id: Optional[int] = None
    channel_type: ChannelType
    inbox_name: str = Field(..., min_length=1, max_length=255)
    account_identifier: str = Field(..., min_length=1, max_length=255)
    chatwoot_inbox_id: Optional[int] = None
    is_active: bool = True


class ChannelAccountCreate(ChannelAccountBase):
    credentials: Optional[Dict[str, Any]] = None


class ChannelAccountUpdate(BaseModel):
    inbox_name: Optional[str] = None
    account_identifier: Optional[str] = None
    chatwoot_inbox_id: Optional[int] = None
    is_active: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None


class ChannelAccountOut(ChannelAccountBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
