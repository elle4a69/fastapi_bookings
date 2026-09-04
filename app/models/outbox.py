"""Domain event and outbox models.

Domain events capture meaningful changes in the system, such as a
booking being created or a payment being processed.  The outbox
pattern stores events in the database so that they can be reliably
dispatched to external systems like email/SMS services or
third‑party integrations.  This module defines a generic
``OutboxEvent`` and a ``BookingEvent`` specialised for booking
lifecycles.
"""

from datetime import datetime, timezone
import json
import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship

from ..db.database import Base
from ..core.state_machine import BookingStatus


class OutboxEvent(Base):
    """Stores events awaiting dispatch to external systems.

    Attributes:
        id: Primary key.
        tenant_id: Subdomain or identifier of the tenant.
        type: A short string describing the event type (e.g.
            ``booking.created`` or ``payment.received``).
        payload: JSON‑serialised payload containing event data.
        status: Controlled delivery lifecycle state.
        retry_count: Number of delivery attempts made.
        error_code: Privacy-safe structural failure code.
        processed: Legacy boolean for processed status.
        created_at: When the event was enqueued.
        processed_at: When the event was processed (if processed).
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency_key"),
        UniqueConstraint("lease_token", name="uq_outbox_events_lease_token"),
        CheckConstraint(
            "status IN ('PENDING','PROCESSING','RETRY','SUCCEEDED','DEAD_LETTER','QUARANTINED')",
            name="ck_outbox_events_status",
        ),
        CheckConstraint(
            "retry_count >= 0 AND attempt_count >= 0 AND max_attempts BETWEEN 1 AND 100 AND attempt_count <= max_attempts",
            name="ck_outbox_events_attempts",
        ),
        CheckConstraint(
            "(status = 'PROCESSING' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'PROCESSING' AND lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_outbox_events_lease_state",
        ),
        CheckConstraint(
            "(status IN ('SUCCEEDED','QUARANTINED','DEAD_LETTER') AND processed AND terminal_at IS NOT NULL) "
            "OR (status NOT IN ('SUCCEEDED','QUARANTINED','DEAD_LETTER') AND NOT processed AND terminal_at IS NULL)",
            name="ck_outbox_events_terminal_state",
        ),
        CheckConstraint(
            "(status IN ('PENDING','RETRY') AND next_attempt_at IS NOT NULL) "
            "OR (status NOT IN ('PENDING','RETRY') AND next_attempt_at IS NULL)",
            name="ck_outbox_events_next_attempt_state",
        ),
        CheckConstraint(
            "error_code IS NULL OR (length(error_code) BETWEEN 1 AND 64 AND error_code = upper(error_code) AND error_code NOT LIKE '% %')",
            name="ck_outbox_events_error_code",
        ),
        Index(
            "ix_outbox_events_dispatch_due",
            "next_attempt_at",
            "created_at",
            "id",
            postgresql_where=text("status IN ('PENDING','RETRY')"),
        ),
        Index(
            "ix_outbox_events_expired_lease",
            "lease_expires_at",
            "id",
            postgresql_where=text("status = 'PROCESSING'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String, default="PENDING", nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    attempt_count = Column(Integer, default=0, server_default="0", nullable=False)
    max_attempts = Column(Integer, default=5, server_default="5", nullable=False)
    error_code = Column(String(64), nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    webhook_snapshot_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(
        String(128),
        default=lambda: f"outbox:{uuid.uuid4()}",
        nullable=False,
    )
    lease_owner = Column(String(128), nullable=True)
    lease_token = Column(String(36), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
    dispatch_started_at = Column(DateTime(timezone=True), nullable=True)
    provider_delivery_id = Column(String(128), nullable=True)
    terminal_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<OutboxEvent id={self.id} type={self.type} status={self.status}>"

    def data(self):
        """Return the payload deserialised as a Python object."""
        try:
            return json.loads(self.payload)
        except Exception:
            return None


class BookingEventType(str, PyEnum):
    """Supported booking event types."""

    CREATED = "booking.created"
    UPDATED = "booking.updated"
    STATUS_CHANGED = "booking.status_changed"
    RESOURCE_ALLOCATED = "booking.resource_allocated"
    CANCELLED = "booking.cancelled"
    COMPLETED = "booking.completed"
    NOSHOW = "booking.no_show"


class BookingEvent(Base):
    """Stores immutable booking lifecycle events for auditability.

    Each time a booking changes state or key attributes the system
    records a ``BookingEvent``.  The ``data`` field contains JSON
    describing the change.
    """

    __tablename__ = "booking_events"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    type = Column(Enum(BookingEventType), nullable=False)
    data = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship to booking is defined via backref on Booking model for convenience

    def __repr__(self) -> str:
        return f"<BookingEvent id={self.id} booking_id={self.booking_id} type={self.type}>"
