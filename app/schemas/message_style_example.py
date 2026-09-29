"""Pydantic schemas for MessageStyleExample domain model."""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.knowledge.classifier import validate_style_placeholders


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

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "client_message" not in data and "user_query" in data:
                data["client_message"] = data["user_query"]
            if "assistant_reply" not in data and "ideal_response" in data:
                data["assistant_reply"] = data["ideal_response"]
        return data

    @property
    def user_query(self) -> str:
        """Alias for client_message for prompt policy alignment."""
        return self.client_message

    @property
    def ideal_response(self) -> str:
        """Alias for assistant_reply for prompt policy alignment."""
        return self.assistant_reply

    @field_validator("client_message", "assistant_reply")
    @classmethod
    def validate_message_placeholders(cls, v: str) -> str:
        if v:
            is_valid, err = validate_style_placeholders(v, is_approved_source=False)
            if not is_valid:
                raise ValueError(err)
        return v


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

    @field_validator("client_message", "assistant_reply")
    @classmethod
    def validate_update_placeholders(cls, v: Optional[str]) -> Optional[str]:
        if v:
            is_valid, err = validate_style_placeholders(v, is_approved_source=False)
            if not is_valid:
                raise ValueError(err)
        return v


class MessageStyleExampleRead(MessageStyleExampleBase):
    """Schema for reading a MessageStyleExample."""
    id: int
    tenant_id: Optional[int] = None
    provider_id: Optional[int] = None
    content_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime

