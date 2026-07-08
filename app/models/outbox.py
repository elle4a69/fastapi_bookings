"""Domain event and outbox models.

Domain events capture meaningful changes in the system, such as a
booking being created or a payment being processed.  The outbox
pattern stores events in the database so that they can be reliably
dispatched to external systems like email/SMS services or
third‑party integrations.  This module defines a generic
``OutboxEvent`` and a ``BookingEvent`` specialised for booking
lifecycles.
"""

from datetime import datetime
import json
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, ForeignKey
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
        status: Delivery status (PENDING, PROCESSED, FAILED).
        retry_count: Number of delivery attempts made.
        error_log: Traceback or error details if delivery failed.
        processed: Legacy boolean for processed status.
        created_at: When the event was enqueued.
        processed_at: When the event was processed (if processed).
    """

    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, nullable=True, index=True)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String, default="PENDING", nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    error_log = Column(Text, nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to booking is defined via backref on Booking model for convenience

    def __repr__(self) -> str:
        return f"<BookingEvent id={self.id} booking_id={self.booking_id} type={self.type}>"