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
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
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
        status: Delivery status (PENDING, PROCESSING, PROCESSED, FAILED, QUARANTINED).
        retry_count: Legacy retry count.
        attempt_count: Number of delivery attempts made.
        leased_by: Identifier of the worker process holding the active lease.
        lease_expires_at: When the current worker lease expires.
        next_attempt_at: When the event is eligible for its next retry attempt.
        error_code: Structured privacy-safe error code.
        error_detail: Sanitized error description.
        error_log: Legacy error details field.
        processed: Legacy boolean for processed status.
        created_at: When the event was enqueued.
        processed_at: When the event was processed (if processed).
    """

    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String, default="PENDING", nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    attempt_count = Column(Integer, default=0, nullable=False)
    leased_by = Column(String, nullable=True, index=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    error_code = Column(String, nullable=True)
    error_detail = Column(Text, nullable=True)
    error_log = Column(Text, nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

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