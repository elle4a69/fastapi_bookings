"""Tenant-scoped durable knowledge and curator proposal models.

Only accepted, non-dynamic business guidance belongs in ``CuratedMemory``.
Conversation-derived suggestions are kept separately in ``KnowledgeProposal``
until an authorised operator makes an explicit, audited decision.
"""

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..db.database import Base


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(timezone.utc)


class CuratedMemory(Base):
    """Reviewed, reusable business knowledge.

    Dynamic facts (availability, prices, dates/times, booking state, links,
    customer information and payment details) must never be inserted here.
    They are always resolved from the authoritative live domain services.
    """

    __tablename__ = "curated_memories"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'quarantined', 'superseded')",
            name="ck_curated_memories_status",
        ),
        CheckConstraint(
            "knowledge_kind IN ('durable_fact', 'response_guidance', 'style_example')",
            name="ck_curated_memories_kind",
        ),
        CheckConstraint(
            "conflict_state IN ('clear', 'needs_review')",
            name="ck_curated_memories_conflict_state",
        ),
        Index(
            "ix_curated_memory_retrieval_scope",
            "tenant_id",
            "provider_id",
            "status",
            "effective_from",
            "effective_until",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id = Column(
        Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category = Column(String(64), nullable=False)
    user_query = Column(Text, nullable=False)
    ideal_response = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    confidence_score = Column(Float, default=1.0, nullable=False)

    knowledge_kind = Column(String(32), default="durable_fact", nullable=False)
    authority = Column(String(32), default="owner_verified", nullable=False)
    status = Column(String(24), default="active", nullable=False, index=True)
    conflict_state = Column(String(24), default="clear", nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)
    source_reference = Column(String(128), nullable=True)
    effective_from = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    effective_until = Column(DateTime(timezone=True), nullable=True)
    supersedes_id = Column(
        Integer,
        ForeignKey("curated_memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_verified_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    tenant = relationship("Tenant")
    provider = relationship("Provider")
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])
    supersedes = relationship("CuratedMemory", remote_side=[id], foreign_keys=[supersedes_id])

    def __repr__(self) -> str:
        return (
            f"<CuratedMemory id={self.id} tenant_id={self.tenant_id} "
            f"category='{self.category}' status='{self.status}'>"
        )


class KnowledgeProposal(Base):
    """Reviewable curator output; never used as responder ground truth."""

    __tablename__ = "knowledge_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'dismissed', 'resolved')",
            name="ck_knowledge_proposals_status",
        ),
        CheckConstraint(
            "proposal_type IN ('add', 'duplicate', 'conflict', 'stale', 'supersede', 'gap', 'quarantine')",
            name="ck_knowledge_proposals_type",
        ),
        UniqueConstraint(
            "tenant_id",
            "fingerprint",
            "status",
            name="uq_knowledge_proposal_tenant_fingerprint_status",
        ),
        Index(
            "ix_knowledge_proposals_review_queue",
            "tenant_id",
            "status",
            "proposal_type",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id = Column(
        Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    proposal_type = Column(String(24), nullable=False)
    status = Column(String(24), default="pending", nullable=False, index=True)
    category = Column(String(64), default="faq", nullable=False)
    knowledge_kind = Column(String(32), default="durable_fact", nullable=False)
    authority = Column(String(32), default="conversation_candidate", nullable=False)
    user_query = Column(Text, nullable=True)
    proposed_response = Column(Text, nullable=True)
    target_memory_id = Column(
        Integer,
        ForeignKey("curated_memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    fingerprint = Column(String(64), nullable=False)
    reason_code = Column(String(64), nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    contains_dynamic_fact = Column(Boolean, default=False, nullable=False)
    requires_review = Column(Boolean, default=True, nullable=False)
    evidence_count = Column(Integer, default=1, nullable=False)
    reviewed_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_code = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant")
    provider = relationship("Provider")
    target_memory = relationship("CuratedMemory", foreign_keys=[target_memory_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])

    def __repr__(self) -> str:
        return (
            f"<KnowledgeProposal id={self.id} tenant_id={self.tenant_id} "
            f"type='{self.proposal_type}' status='{self.status}'>"
        )
