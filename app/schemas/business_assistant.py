"""Validated data contracts for the native Business Assistant foundation."""

from datetime import datetime
from uuid import UUID
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BusinessAssistantConversationCreate(BaseModel):
    """Request data for an idempotent staff conversation creation."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    request_key: Optional[str] = Field(default=None, min_length=8, max_length=128)


class BusinessAssistantConversationRead(BaseModel):
    """Safe conversation identity and lifecycle fields."""

    id: int
    title: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessAssistantMessageCreate(BaseModel):
    """Validated persisted staff turn, not a model-execution request."""

    role: Literal["user", "business_assistant", "system"]
    content: str = Field(min_length=1, max_length=20_000)


class BusinessAssistantTextTurnCreate(BaseModel):
    """User input for one bounded text-only turn."""

    content: str = Field(min_length=1, max_length=20_000)
    request_key: str = Field(min_length=8, max_length=128)


class BusinessAssistantMessageRead(BaseModel):
    """One conversation message visible within its authorised scope."""

    id: int
    conversation_id: int
    role: str
    content: str
    channel: str
    in_reply_to_message_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessAssistantTextTurnRead(BaseModel):
    """Persisted user turn and the generated reply, if generation succeeds."""

    user_message: BusinessAssistantMessageRead
    assistant_message: BusinessAssistantMessageRead
    duplicate_request: bool = False


class BusinessAssistantRealtimeTurnCreate(BaseModel):
    """Completed realtime transcript pair from one authenticated voice session."""

    session_id: UUID
    user_item_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")
    assistant_response_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")
    user_transcript: str = Field(min_length=1, max_length=20_000)
    assistant_transcript: str = Field(min_length=1, max_length=20_000)


class BusinessAssistantRealtimeTurnRead(BaseModel):
    """One idempotently persisted user and responder transcript pair."""

    user_message: BusinessAssistantMessageRead
    assistant_message: BusinessAssistantMessageRead
    duplicate_turn: bool = False


OnboardingStep = Literal[
    "review_product_context",
    "review_catalog_readiness",
    "prepare_product_question",
]


class BusinessAssistantSetupCountsRead(BaseModel):
    """Non-sensitive aggregate setup state from native tenant records."""

    active_services: int
    active_providers: int
    active_locations: int


class BusinessAssistantProductContextRead(BaseModel):
    """Strictly allowlisted, read-only context for product help and onboarding."""

    availability: Literal["available", "unavailable"]
    enabled_modules: list[str] = Field(default_factory=list)
    setup_counts: Optional[BusinessAssistantSetupCountsRead] = None


class BusinessAssistantOnboardingProgressRead(BaseModel):
    """Durable personal onboarding progress for the authenticated owner."""

    status: Literal["not_started", "in_progress", "completed"]
    completed_steps: list[OnboardingStep]
    updated_at: Optional[datetime]


class BusinessAssistantOnboardingRead(BaseModel):
    """Onboarding progress paired with its live product-context snapshot."""

    progress: BusinessAssistantOnboardingProgressRead
    product_context: BusinessAssistantProductContextRead


class BusinessAssistantOnboardingProgressUpdate(BaseModel):
    """One fixed onboarding milestone; no tenant-setting mutation is permitted."""

    step: OnboardingStep


class SupportTicketCreate(BaseModel):
    """Sanitised ticket input. Dispatch and worker instructions are excluded."""

    conversation_id: Optional[int] = Field(default=None, ge=1)
    category: Literal["support", "bug", "feature", "access", "security", "upgrade"]
    severity: Literal["low", "normal", "high", "critical"] = "normal"
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=20_000)
    request_key: Optional[str] = Field(default=None, min_length=8, max_length=128)


class SupportTicketRead(BaseModel):
    """User-safe ticket fields for the authenticated tenant scope."""

    id: int
    conversation_id: Optional[int]
    category: str
    severity: str
    status: str
    title: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupportTicketEventRead(BaseModel):
    """One append-only ticket event that is safe to show to its creator."""

    id: int
    event_type: str
    safe_metadata: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupportTicketCreateRead(BaseModel):
    """A created ticket or a scoped duplicate of an active ticket."""

    ticket: SupportTicketRead
    duplicate_ticket: bool


class BusinessAssistantToolExecutionRequest(BaseModel):
    """Tool invocation payload submitted for server-authorised execution."""

    name: str = Field(min_length=1, max_length=96)
    arguments: dict[str, object] = Field(default_factory=dict)


class BusinessAssistantToolExecutionResponse(BaseModel):
    """Authoritative structured output returned from an executed tool."""

    status: str
    result: Optional[dict[str, object]] = None
    reason: Optional[str] = None

