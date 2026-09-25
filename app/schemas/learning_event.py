"""Schemas for unified learning events."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LearningEventRead(BaseModel):
    id: str
    tenant_id: int
    provider_id: Optional[int] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    event_type: str
    source: str
    customer_message: Optional[str] = None
    original_ai_content: Optional[str] = None
    human_content: Optional[str] = None
    diff_payload: Optional[Dict[str, Any]] = None
    metadata_payload: Optional[Dict[str, Any]] = None
    status: str
    confidence_score: float
    created_at: datetime
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    attempt_count: int = 0
    next_attempt_at: Optional[datetime] = None
    last_error: Optional[str] = None
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LearningEventFilter(BaseModel):
    tenant_id: Optional[int] = None
    provider_id: Optional[int] = None
    conversation_id: Optional[str] = None
    event_type: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class LearningEventSummary(BaseModel):
    total_count: int
    pending_count: int
    processed_count: int
    ignored_count: int
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
