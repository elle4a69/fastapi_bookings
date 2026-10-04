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


class BusinessRuleDraftCreate(BaseModel):
    """Input payload to create or update a drafted business rule."""

    memory_key: str = Field(min_length=2, max_length=128)
    content: str = Field(min_length=5, max_length=10_000)
    category: str = Field(default="policy", max_length=64)
    curator_item_id: Optional[int] = Field(default=None, ge=1)


class BusinessRuleRead(BaseModel):
    """User-safe representation of a business rule and its assistant interpretation."""

    id: int
    memory_key: str
    content: str
    interpretation: Optional[str] = None
    category: str
    status: str
    version: int
    payload_hash: Optional[str] = None
    provenance: dict = Field(default_factory=dict)
    curator_item_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    activated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BusinessRuleDraftResponse(BaseModel):
    """Result of drafting a business rule including confirmation token for activation."""

    rule: BusinessRuleRead
    interpretation: str
    confirmation_token: str
    payload_hash: str


class BusinessRuleActivateRequest(BaseModel):
    """Explicit confirmation payload bound to versioned payload hash."""

    confirmation_token: str = Field(min_length=16)


class CuratorQuestionRead(BaseModel):
    """Pending or reviewable curator question visible to tenant staff."""

    id: int
    category: str
    user_query: Optional[str] = None
    proposed_response: Optional[str] = None
    reason_code: str
    status: str
    confidence_score: float = 0.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CuratorQuestionResolveRequest(BaseModel):
    """Input for explicitly resolving or dismissing a curator question."""

    resolution: Literal["resolved", "dismissed", "rejected"] = "resolved"
    note: Optional[str] = Field(default=None, max_length=500)


class CustomerOptInStatusRead(BaseModel):
    """Customer opt-in, SMS consent, and marketing acceptance record."""

    opted_out: bool = False
    sms_consent: bool = True
    accepts_marketing: bool = False
    client_active: Optional[bool] = True


class CustomerConversationSummaryRead(BaseModel):
    """Summary of an authorised customer conversation for search results."""

    id: int
    contact_name: Optional[str] = None
    contact_identifier: str
    status: str
    channel_type: Optional[str] = None
    provider_id: Optional[int] = None
    updated_at: Optional[datetime] = None
    opt_in_status: CustomerOptInStatusRead


class CustomerConversationMessageRead(BaseModel):
    """Single message item within a customer conversation thread."""

    id: int
    direction: str
    source: str
    content: str
    delivery_status: str
    created_at: Optional[datetime] = None


class CustomerConversationThreadRead(BaseModel):
    """Authorised customer conversation thread with messages and consent status."""

    conversation_id: int
    contact_name: Optional[str] = None
    contact_identifier: str
    status: str
    channel_type: Optional[str] = None
    provider_id: Optional[int] = None
    opt_in_status: CustomerOptInStatusRead
    messages: list[CustomerConversationMessageRead] = Field(default_factory=list)


class CustomerMessageDraftCreate(BaseModel):
    """Input payload to prepare a customer response message draft."""

    content: str = Field(min_length=1, max_length=10_000)
    request_key: Optional[str] = Field(default=None, min_length=8, max_length=128)


class CustomerMessageDraftRead(BaseModel):
    """Persisted response draft with recipient preview and versioning."""

    id: int
    conversation_id: int
    content: str
    recipient_preview: str
    status: str
    version: int
    payload_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerMessageDraftResponse(BaseModel):
    """Response containing prepared message draft and confirmation token."""

    draft: CustomerMessageDraftRead
    confirmation_token: str
    preview: dict = Field(default_factory=dict)


class CampaignAudienceCriteriaInput(BaseModel):
    """Configurable inclusion criteria for audience calculation."""

    marketing_opt_in_only: bool = True
    active_only: bool = True
    exclude_pending_holds: bool = True
    min_completed_bookings: int = 0
    provider_id: Optional[int] = None


class CampaignAudiencePreviewRead(BaseModel):
    """Audience preview containing recipient count and explainable summary."""

    recipient_count: int
    summary: dict = Field(default_factory=dict)
    sample_recipients: list[dict] = Field(default_factory=list)


class CampaignProposalCreate(BaseModel):
    """Input payload to create an audience-selected campaign proposal."""

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10_000)
    marketing_opt_in_only: bool = True
    active_only: bool = True
    exclude_pending_holds: bool = True
    min_completed_bookings: int = 0
    provider_id: Optional[int] = None
    request_key: Optional[str] = Field(default=None, min_length=8, max_length=128)


class CampaignProposalRead(BaseModel):
    """Explainable campaign proposal with snapshot and approval status."""

    id: int
    title: str
    content: str
    recipient_count: int
    status: str
    version: int
    payload_hash: Optional[str] = None
    target_audience_criteria: dict = Field(default_factory=dict)
    audience_snapshot: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignProposalResponse(BaseModel):
    """Result of creating a campaign proposal including confirmation token."""

    proposal: CampaignProposalRead
    confirmation_token: str
    summary: dict = Field(default_factory=dict)


class CampaignProposalApproveRequest(BaseModel):
    """Explicit confirmation payload bound to proposal version and payload hash."""

    confirmation_token: str = Field(min_length=16)



