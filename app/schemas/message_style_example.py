"""Pydantic schemas for MessageStyleExample domain model."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MessageStyleExampleBase(BaseModel):
    """Base schema for procedural message style examples."""
    model_config = ConfigDict(from_attributes=True)

    intent: str = Field(..., max_length=64, description="Primary conversation intent")
    client_message: str = Field(..., min_length=1, description="Incoming user message")
    assistant_reply: str = Field(..., min_length=1, description="Exemplar assistant reply")
    category: str = Field(default="procedural", max_length=64, description="Category classification")
    tags: List[str] = Field(default_factory=list, description="Tags or placeholder labels")
    is_approved: bool = Field(default=True, description="Whether verified and approved for prompt conditioning")
    is_active: bool = Field(default=True, description="Whether currently active for retrieval")
    source: str = Field(default="assistant_ui_import", max_length=64, description="Provenance source")


class MessageStyleExampleCreate(MessageStyleExampleBase):
    """Schema for creating a new MessageStyleExample."""
    tenant_id: Optional[int] = Field(None, description="Tenant scope ID (null for platform defaults)")
    provider_id: Optional[int] = Field(None, description="Provider scope ID (null for tenant/platform wide)")


class MessageStyleExampleUpdate(BaseModel):
    """Schema for updating an existing MessageStyleExample."""
    model_config = ConfigDict(from_attributes=True)

    intent: Optional[str] = Field(None, max_length=64)
    client_message: Optional[str] = None
    assistant_reply: Optional[str] = None
    category: Optional[str] = Field(None, max_length=64)
    tags: Optional[List[str]] = None
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None


class MessageStyleExampleRead(MessageStyleExampleBase):
    """Schema for reading a MessageStyleExample."""
    id: int
    tenant_id: Optional[int] = None
    provider_id: Optional[int] = None
    content_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
