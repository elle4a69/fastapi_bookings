"""Support Ticket domain models.

Provides tenant-scoped support tickets, threaded messages, and append-only audit events.
Used for customer and tenant support inquiries, triaged priority tracking, error context attachment,
and external Codex coordination.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
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


class SupportTicket(Base):
    """A tenant-scoped support ticket with triage status, error context, and external codex thread link."""

    __tablename__ = "support_tickets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_support_tickets_tenant_idempotency"),
        Index("ix_support_tickets_tenant_status", "tenant_id", "status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(40), nullable=False, default="general", index=True)
    status = Column(String(32), nullable=False, default="received", index=True)
    triage_priority = Column(String(20), nullable=False, default="normal", index=True)
    error_context = Column(JSON, nullable=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    codex_thread_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    messages = relationship(
        "app.models.support_ticket.SupportTicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="app.models.support_ticket.SupportTicketMessage.created_at",
    )
    audit_events = relationship(
        "app.models.support_ticket.SupportTicketAuditEvent",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="app.models.support_ticket.SupportTicketAuditEvent.created_at",
    )

    @property
    def tenant_status(self) -> str:
        tenant_status_map = {
            "received": "Received",
            "under_review": "Under Review",
            "queued_for_codex": "Under Review",
            "in_progress": "Under Review",
            "waiting_on_tenant": "Needs Information",
            "resolved": "Resolved",
            "closed": "Resolved",
        }
        return tenant_status_map.get(self.status, (self.status or "").replace("_", " ").title())


class SupportTicketMessage(Base):
    """Threaded message turn within a support ticket."""

    __tablename__ = "support_ticket_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(
        String(36),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sender_type = Column(String(20), nullable=False)  # 'tenant_user', 'platform_owner', 'system'
    visibility = Column(String(20), nullable=False, default="tenant_visible")  # 'tenant_visible', 'internal_only'
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    ticket = relationship("app.models.support_ticket.SupportTicket", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_user_id])


class SupportTicketAuditEvent(Base):
    """Append-only audit trail event recording lifecycle and state mutations on a support ticket."""

    __tablename__ = "support_ticket_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(
        String(36),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(40), nullable=False)
    event_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    ticket = relationship("app.models.support_ticket.SupportTicket", back_populates="audit_events")
    actor = relationship("User", foreign_keys=[actor_user_id])
