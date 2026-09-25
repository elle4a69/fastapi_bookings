"""Knowledge Graph Projection ledger model.

Spec references: Sections 28, 29, 32.
Canonical ledger recording projections destined for Graphiti/Neo4j graph representation.
Operates as a durable outbox ensuring zero data loss and idempotent projection.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
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
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class KnowledgeGraphProjection(Base):
    """Outbox and projection ledger record for asynchronous Graphiti synchronization.

    Guarantees:
    - Atomicity: Created in the same DB transaction as CuratedMemory.
    - Idempotency: UniqueConstraint on (learning_event_id, projection_type).
    - Multi-tenant isolation: Explicit tenant_id and partitioned graph_group_id.
    - Leased claims: Worker processes claim projections with lease timeouts.
    """

    __tablename__ = "knowledge_graph_projections"
    __table_args__ = (
        Index("ix_kgp_claim", "status", "next_attempt_at", "tenant_id"),
        UniqueConstraint("learning_event_id", "projection_type", name="uq_kgp_event_type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id = Column(
        Integer, ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    learning_event_id = Column(
        String(36), ForeignKey("learning_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    curated_memory_id = Column(
        Integer, ForeignKey("curated_memories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    projection_type = Column(String(50), nullable=False)
    graph_group_id = Column(String(100), nullable=False, index=True)
    graph_episode_uuid = Column(String(100), nullable=True)
    status = Column(String(30), nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    lease_owner = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    projection_version = Column(String(20), default="1.0", nullable=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    projected_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant")
    provider = relationship("Provider")
    learning_event = relationship("LearningEvent")
    curated_memory = relationship("CuratedMemory")

    def __repr__(self) -> str:
        return (
            f"<KnowledgeGraphProjection id={self.id} tenant_id={self.tenant_id} "
            f"type='{self.projection_type}' status='{self.status}'>"
        )
