"""Domain models and type definitions for the knowledge subsystem.

Spec references: Sections 6, 7, 34, 35, 36, 49, 50.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class KnowledgeKind(str, Enum):
    """Categorisation of knowledge items in the graph."""
    durable_fact = "durable_fact"
    behaviour_rule = "behaviour_rule"
    response_guidance = "response_guidance"
    style_example = "style_example"
    policy_guidance = "policy_guidance"
    preference = "preference"
    boundary = "boundary"


class Authority(str, Enum):
    """Source authority levels determining curation precedence."""
    explicit_provider_instruction = "explicit_provider_instruction"
    explicit_provider_correction = "explicit_provider_correction"
    explicit_provider_answer = "explicit_provider_answer"
    provider_draft_edit = "provider_draft_edit"
    provider_approval = "provider_approval"
    system_import = "system_import"
    admin_import = "admin_import"


class CuratorAction(str, Enum):
    """Actions emitted by the curation engine for ingestion / candidate review."""
    AUTO_CURATE = "AUTO_CURATE"
    PROPOSAL = "PROPOSAL"
    EVIDENCE = "EVIDENCE"
    WEAK_REINFORCEMENT = "WEAK_REINFORCEMENT"
    REJECT_DYNAMIC = "REJECT_DYNAMIC"
    SUPERSEDE = "SUPERSEDE"
    QUARANTINE = "QUARANTINE"


class KnowledgeScope(BaseModel):
    """Scope definition enforcing strict multi-tenant and provider boundaries.

    Spec 34: Scopes resolve to group IDs formatted as:
      - Tenant-shared: tenant:{tenant_id}:shared
      - Provider-specific: tenant:{tenant_id}:provider:{provider_id}
    """
    tenant_id: int = Field(..., gt=0, description="Tenant ID owning the knowledge partition")
    provider_id: Optional[int] = Field(None, gt=0, description="Optional provider ID for provider-isolated knowledge")
    is_tenant_shared: bool = Field(False, description="Whether this knowledge applies to all providers in the tenant")

    @property
    def group_id(self) -> str:
        """Derive the Graphiti group_id partition key."""
        if self.is_tenant_shared or self.provider_id is None:
            return f"tenant:{self.tenant_id}:shared"
        return f"tenant:{self.tenant_id}:provider:{self.provider_id}"

    def to_group_ids(self) -> List[str]:
        """Return the group_ids to query for retrieval.

        If a provider_id is specified, queries BOTH the provider-specific partition
        and the tenant-shared partition (with provider facts taking precedence).
        If no provider_id is specified, queries only the tenant-shared partition.
        """
        shared_group = f"tenant:{self.tenant_id}:shared"
        if self.provider_id is not None and not self.is_tenant_shared:
            return [f"tenant:{self.tenant_id}:provider:{self.provider_id}", shared_group]
        return [shared_group]


class KnowledgeItem(BaseModel):
    """Represents a discrete piece of curated knowledge."""
    id: Optional[str] = Field(None, description="Unique identifier or node ID")
    scope: KnowledgeScope = Field(..., description="Tenant and provider boundary scope")
    kind: KnowledgeKind = Field(KnowledgeKind.durable_fact, description="Knowledge category")
    text: str = Field(..., description="The knowledge fact or instruction content")
    authority: Authority = Field(Authority.explicit_provider_instruction, description="Authoritative source level")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary provenance and scoring metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of item creation")

    def __str__(self) -> str:
        return self.text


class RetrievalQuery(BaseModel):
    """Query object for retrieving relevant knowledge for a given scope."""
    tenant_id: int = Field(..., gt=0, description="Tenant identifier")
    provider_id: Optional[int] = Field(None, gt=0, description="Optional provider identifier")
    query: str = Field(..., description="Search query or customer utterance")
    kinds: Optional[List[KnowledgeKind]] = Field(None, description="Filter for specific kinds of knowledge")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of items to retrieve")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional query metadata")


class RetrievalResult(BaseModel):
    """Structured knowledge retrieved for prompt generation or query evaluation."""
    facts: List[str] = Field(default_factory=list, description="Durable facts")
    behavioural_rules: List[str] = Field(default_factory=list, description="Instructional behaviour rules and guidelines")
    examples: List[str] = Field(default_factory=list, description="Few-shot style examples")
    items: List[KnowledgeItem] = Field(default_factory=list, description="Complete retrieved KnowledgeItem objects")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Cache hit status, latency, and audit metadata")
