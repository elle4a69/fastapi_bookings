"""Client Dispute model for the Client Self-Service Portal & Dispute Center.

Allows clients to lodge quality, service, or billing disputes against bookings,
request specific resolutions (redo, refund, credit), and upload photo evidence.
Tenant admins can review, update, and resolve disputes.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..db.database import Base


class ClientDispute(Base):
    __tablename__ = "client_disputes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        Integer,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    booking_id = Column(
        Integer,
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Dispute status: submitted, under_review, resolved, rejected
    status = Column(String, default="submitted", nullable=False)

    # Dispute reason: incomplete_work, late_arrival, quality_concern, billing_dispute, other
    reason = Column(String, nullable=False)

    # Detailed customer description
    description = Column(Text, nullable=False)

    # Desired resolution: redo_service, partial_refund, full_refund, credit_note
    preferred_resolution = Column(String, default="redo_service", nullable=False)

    # Internal / resolution notes from admin
    resolution_notes = Column(Text, nullable=True)

    # Optional list of photo URLs or media items
    photos = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    client = relationship("Client")
    booking = relationship("Booking")

    def __repr__(self) -> str:
        return f"<ClientDispute id={self.id} status={self.status} client_id={self.client_id} booking_id={self.booking_id}>"


def init_dispute_tables(bind=None) -> None:
    """Helper to ensure the client_disputes table exists."""
    ClientDispute.__table__.create(bind=bind, checkfirst=True)
