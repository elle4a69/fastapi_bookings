"""Booking model.

Represents an appointment between a client and a provider for a given
service at a specific time. The status of a booking follows the
finite state machine defined in :mod:`..core.state_machine`.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db.database import Base
from ..core.state_machine import BookingStatus


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    series_id = Column(Integer, ForeignKey("booking_series.id"), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    client = relationship("Client", back_populates="bookings")
    provider = relationship("Provider", back_populates="bookings")
    service = relationship("Service", back_populates="bookings")
    location = relationship("Location", back_populates="bookings")
    series = relationship("BookingSeries", back_populates="bookings")

    # Resources allocated to this booking
    resource_allocations = relationship(
        "BookingResourceAllocation",
        back_populates="booking",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Booking id={self.id} status={self.status}>"