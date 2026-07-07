"""Waitlist model.

Waitlist entries capture client requests for appointments when no
immediately available slot exists.  When a slot becomes free the
system can notify or automatically book the first eligible waitlist
entry.  Waitlists can be scoped by service, provider, location and
time range.
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.database import Base


class WaitlistStatus(str, PyEnum):
    """States for a waitlist entry."""

    REQUESTED = "requested"
    NOTIFIED = "notified"
    BOOKED = "booked"
    CANCELLED = "cancelled"


class WaitlistEntry(Base):
    """Represents a client's desire for an appointment if slots become available."""

    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    desired_date_from = Column(DateTime(timezone=True), nullable=True)
    desired_date_to = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(WaitlistStatus), default=WaitlistStatus.REQUESTED, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    client = relationship("Client")
    service = relationship("Service")
    provider = relationship("Provider")
    location = relationship("Location")

    def __repr__(self) -> str:
        return (
            f"<WaitlistEntry id={self.id} service_id={self.service_id} "
            f"status={self.status}>"
        )