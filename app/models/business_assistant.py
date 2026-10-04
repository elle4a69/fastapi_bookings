"""Tenant-scoped persistence for the internal Business Assistant.

These records are intentionally separate from customer messaging tables.  They
hold authenticated staff conversations and structural audit information only;
tool arguments, tool results, credentials, and worker logs do not belong here.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..db.database import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persisted records."""
    return datetime.now(timezone.utc)


class BusinessAssistantConversation(Base):
    """An internal staff conversation owned by one tenant and one user."""

    __tablename__ = "business_assistant_conversations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "creation_request_key",
            name="uq_business_assistant_conversation_creation_key",
        ),
        Index(
            "ix_business_assistant_conversations_scope_updated",
            "tenant_id",
            "user_id",
            "updated_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(160), nullable=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    creation_request_key = Column(String(128), nullable=True)
    creation_payload_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    tenant = relationship("Tenant")
    user = relationship("User")
    messages = relationship(
        "BusinessAssistantMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="BusinessAssistantMessage.created_at",
    )


class BusinessAssistantMessage(Base):
    """A persisted turn within an internal staff conversation."""

    __tablename__ = "business_assistant_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'business_assistant', 'system')", name="ck_business_assistant_message_role"),
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "conversation_id",
            "request_key",
            name="uq_business_assistant_message_request_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "conversation_id",
            "realtime_session_id",
            "realtime_item_id",
            name="uq_business_assistant_message_realtime_item",
        ),
        Index("ix_business_assistant_messages_scope_conversation", "tenant_id", "conversation_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("business_assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    request_key = Column(String(128), nullable=True)
    request_payload_hash = Column(String(64), nullable=True)
    channel = Column(String(32), nullable=False, default="text", index=True)
    realtime_session_id = Column(String(36), nullable=True)
    realtime_item_id = Column(String(200), nullable=True)
    generation_status = Column(String(32), nullable=True, index=True)
    generation_started_at = Column(DateTime(timezone=True), nullable=True)
    in_reply_to_message_id = Column(
        Integer,
        ForeignKey("business_assistant_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    conversation = relationship("BusinessAssistantConversation", back_populates="messages")
    tenant = relationship("Tenant")
    user = relationship("User")
    in_reply_to_message = relationship("BusinessAssistantMessage", remote_side=[id])


class BusinessAssistantToolRun(Base):
    """Append-only structural record for a future bounded tool invocation."""

    __tablename__ = "business_assistant_tool_runs"
    __table_args__ = (
        Index("ix_business_assistant_tool_runs_scope_created", "tenant_id", "user_id", "created_at"),
        Index("ix_business_assistant_tool_runs_conversation_created", "conversation_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("business_assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id = Column(
        Integer,
        ForeignKey("business_assistant_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_name = Column(String(96), nullable=False)
    status = Column(String(32), nullable=False)
    request_id = Column(String(128), nullable=True, index=True)
    duration_ms = Column(Integer, nullable=True)
    safe_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    tenant = relationship("Tenant")
    user = relationship("User")
    conversation = relationship("BusinessAssistantConversation")
    message = relationship("BusinessAssistantMessage")


class BusinessAssistantMemory(Base):
    """Approved, scoped memory reserved for policy-controlled business knowledge."""

    __tablename__ = "business_assistant_memories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "memory_key", name="uq_business_assistant_memory_scope_key"),
        Index("ix_business_assistant_memories_scope_status", "tenant_id", "user_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_key = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    interpretation = Column(Text, nullable=True)
    category = Column(String(64), nullable=False, default="policy")
    version = Column(Integer, nullable=False, default=1)
    payload_hash = Column(String(64), nullable=True)
    provenance = Column(JSON, nullable=False, default=dict)
    curator_item_id = Column(
        Integer,
        ForeignKey("knowledge_proposals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String(32), nullable=False, default="draft", index=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    activated_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    tenant = relationship("Tenant")
    user = relationship("User", foreign_keys=[user_id])
    activated_by = relationship("User", foreign_keys=[activated_by_user_id])
    curator_proposal = relationship("KnowledgeProposal", foreign_keys=[curator_item_id])


class BusinessAssistantOnboardingProgress(Base):
    """Durable, personal onboarding state that never changes tenant settings."""

    __tablename__ = "business_assistant_onboarding_progress"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'completed')",
            name="ck_business_assistant_onboarding_status",
        ),
        UniqueConstraint(
            "tenant_id",
            "user_id",
            name="uq_business_assistant_onboarding_scope",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="not_started", index=True)
    completed_steps = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    tenant = relationship("Tenant")
    user = relationship("User")


class SupportTicket(Base):
    """A sanitised support or engineering ticket with no worker dispatch path."""

    __tablename__ = "business_assistant_support_tickets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('support', 'bug', 'feature', 'access', 'security', 'upgrade')",
            name="ck_business_assistant_ticket_category",
        ),
        CheckConstraint(
            "severity IN ('low', 'normal', 'high', 'critical')",
            name="ck_business_assistant_ticket_severity",
        ),
        Index("ix_business_assistant_support_tickets_scope_status", "tenant_id", "status", "created_at"),
        Index("ix_business_assistant_support_tickets_scope_request", "tenant_id", "request_key"),
        Index(
            "ix_business_assistant_support_tickets_scope_deduplication",
            "tenant_id",
            "user_id",
            "deduplication_key",
        ),
        UniqueConstraint("tenant_id", "user_id", "request_key", name="uq_business_assistant_ticket_request_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("business_assistant_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category = Column(String(48), nullable=False, index=True)
    severity = Column(String(24), nullable=False, default="normal", index=True)
    status = Column(String(32), nullable=False, default="awaiting_engineering", index=True)
    title = Column(String(240), nullable=False)
    description = Column(Text, nullable=False)
    request_key = Column(String(128), nullable=True)
    request_payload_hash = Column(String(64), nullable=True)
    deduplication_key = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    tenant = relationship("Tenant")
    user = relationship("User")
    conversation = relationship("BusinessAssistantConversation")
    events = relationship(
        "SupportTicketEvent",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportTicketEvent.created_at",
    )


class SupportTicketDeduplicationClaim(Base):
    """Unique active-ticket claim released only by a future transactional close workflow."""

    __tablename__ = "business_assistant_active_ticket_claims"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "deduplication_key",
            name="uq_business_assistant_active_ticket_claim",
        ),
        UniqueConstraint("ticket_id", name="uq_business_assistant_active_ticket_claim_ticket"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(
        Integer,
        ForeignKey("business_assistant_support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    deduplication_key = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    ticket = relationship("SupportTicket")
    tenant = relationship("Tenant")
    user = relationship("User")


class SupportTicketEvent(Base):
    """Append-only, user-safe lifecycle event for a support ticket."""

    __tablename__ = "business_assistant_support_ticket_events"
    __table_args__ = (Index("ix_business_assistant_ticket_events_ticket_created", "ticket_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(
        Integer,
        ForeignKey("business_assistant_support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    safe_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    ticket = relationship("SupportTicket", back_populates="events")
    tenant = relationship("Tenant")
    actor_user = relationship("User")
