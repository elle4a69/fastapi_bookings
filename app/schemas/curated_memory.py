"""Schemas for reviewed durable knowledge and curator proposals."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..services.curation.knowledge_policy import classify_knowledge_safety


class CuratedMemoryBase(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    user_query: str = Field(min_length=5, max_length=2000)
    ideal_response: str = Field(min_length=10, max_length=8000)
    provider_id: Optional[int] = Field(default=None, ge=1)
    embedding: Optional[list[float]] = Field(default=None, exclude=True)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    knowledge_kind: Literal["durable_fact", "response_guidance", "style_example"] = (
        "durable_fact"
    )
    authority: Literal[
        "owner_verified", "admin_verified", "approved_policy", "imported_verified"
    ] = "owner_verified"
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None

    @field_validator("knowledge_kind", mode="before")
    @classmethod
    def default_missing_kind(cls, value):
        return value or "durable_fact"

    @field_validator("authority", mode="before")
    @classmethod
    def default_missing_authority(cls, value):
        return value or "owner_verified"

    @model_validator(mode="after")
    def reject_dynamic_facts(self):
        safety = classify_knowledge_safety(
            self.user_query, self.ideal_response, category=self.category
        )
        if not safety.durable:
            raise ValueError(safety.reason_code)
        if (
            self.effective_from is not None
            and self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effective_until must be later than effective_from")
        return self


class CuratedMemoryCreate(CuratedMemoryBase):
    """Internal trusted-ingestion schema; tenant must still come from auth."""

    tenant_id: int = Field(ge=1)


class CuratedMemoryUpdate(BaseModel):
    category: Optional[str] = Field(default=None, min_length=1, max_length=64)
    user_query: Optional[str] = Field(default=None, min_length=5, max_length=2000)
    ideal_response: Optional[str] = Field(default=None, min_length=10, max_length=8000)
    provider_id: Optional[int] = Field(default=None, ge=1)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    status: Optional[Literal["active", "quarantined", "superseded"]] = None
    conflict_state: Optional[Literal["clear", "needs_review"]] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


class CuratedMemoryInDBBase(CuratedMemoryBase):
    id: int
    tenant_id: int
    status: Literal["active", "quarantined", "superseded"]
    conflict_state: Literal["clear", "needs_review"]
    last_verified_at: datetime
    created_at: datetime
    updated_at: datetime

    @field_validator("status", mode="before")
    @classmethod
    def default_missing_status(cls, value):
        return value or "active"

    @field_validator("conflict_state", mode="before")
    @classmethod
    def default_missing_conflict_state(cls, value):
        return value or "clear"

    model_config = ConfigDict(from_attributes=True)


class CuratedMemory(CuratedMemoryInDBBase):
    pass


class CuratedMemoryResponse(BaseModel):
    ok: bool = True
    data: CuratedMemory


class CuratedMemoryListResponse(BaseModel):
    ok: bool = True
    data: list[CuratedMemory]
    total: int


class CuratedMemorySearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    tenant_id: int = Field(ge=1)
    category: Optional[str] = Field(default=None, max_length=64)
    provider_id: Optional[int] = Field(default=None, ge=1)
    limit: int = Field(default=5, ge=1, le=50)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class CuratedMemorySearchResult(BaseModel):
    memory: CuratedMemory
    semantic_score: float = Field(ge=0.0, le=1.0)
    lexical_score: float = Field(ge=0.0, le=1.0)
    combined_score: float = Field(ge=0.0, le=1.0)
    decision_code: str


class KnowledgeProposalResponse(BaseModel):
    id: int
    provider_id: Optional[int]
    proposal_type: Literal[
        "add", "duplicate", "conflict", "stale", "supersede", "gap", "quarantine"
    ]
    status: Literal["pending", "accepted", "rejected", "dismissed", "resolved"]
    category: str
    reason_code: str
    confidence_score: float
    contains_dynamic_fact: bool
    requires_review: bool
    evidence_count: int
    target_memory_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class KnowledgeProposalReviewRequest(BaseModel):
    decision: Literal["accept", "reject", "dismiss", "resolve"]
    resolution_code: str = Field(min_length=1, max_length=64)
    explicit_conflict_resolution: bool = False
