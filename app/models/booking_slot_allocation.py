"""Booking slot allocation model.

Represents a durable 15-minute slot allocation committed for an active confirmed
booking. Enforces a database-level unique constraint on (provider_id, slot_start)
across SQLite and PostgreSQL to guarantee atomic first-submit-wins concurrency
without relying on application-level locks or holds.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.database import Base


class BookingSlotAllocation(Base):
    __tablename__ = "booking_slot_allocations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_start = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider_id", "slot_start", name="uq_provider_slot_allocation"),
        Index("ix_slot_alloc_tenant_prov_start", "tenant_id", "provider_id", "slot_start"),
    )

    # Relationships
    tenant = relationship("Tenant")
    booking = relationship("Booking", back_populates="slot_allocations")
    provider = relationship("Provider")

    def __repr__(self) -> str:
        return f"<BookingSlotAllocation booking_id={self.booking_id} provider_id={self.provider_id} slot_start={self.slot_start}>"
