"""Pydantic schemas for Conversations and Messages."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from ..models.conversation import ChannelType, DeliveryStatus, MessageDirection, MessageSource


class ConversationMetadataContract(BaseModel):
    """Metadata contract preserving cross-system integration context."""

    tenant_id: int
    provider_id: Optional[int] = None
    channel_type: Optional[ChannelType] = None
    chatwoot_inbox_id: Optional[int] = None
    external_conversation_id: Optional[str] = None
    external_message_id: Optional[str] = None
    delivery_status: Optional[DeliveryStatus] = None
    source: Optional[MessageSource] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class MessageBase(BaseModel):
    content: str = Field(..., min_length=1)
    direction: MessageDirection = MessageDirection.OUTBOUND
    source: MessageSource = MessageSource.OPERATOR
    delivery_status: DeliveryStatus = DeliveryStatus.SENT
    external_message_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class MessageCreate(MessageBase):
    pass


class MessageOut(MessageBase):
    id: int
    conversation_id: int
    tenant_id: int
    provider_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationBase(BaseModel):
    provider_id: Optional[int] = None
    channel_account_id: Optional[int] = None
    external_conversation_id: Optional[str] = None
    contact_identifier: str = Field(..., min_length=1, max_length=255)
    contact_name: Optional[str] = None
    status: str = Field(default="active")
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class ConversationCreate(ConversationBase):
    channel_type: Optional[ChannelType] = None


class ConversationOut(ConversationBase):
    id: int
    tenant_id: int
    channel_type: Optional[ChannelType] = None
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[MessageOut]] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailOut(ConversationOut):
    messages: List[MessageOut] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    ok: bool = True
    data: List[ConversationOut]
    total: int
