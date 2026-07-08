"""Hold model.

Holds reserve a time slot temporarily while a client fills out a booking
form.  They help prevent double‑booking when multiple clients are
attempting to book the same slot.  A hold expires automatically if
not confirmed before ``expires_at``.  When a hold is confirmed it
becomes a booking.
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Index, text
from sqlalchemy.orm import relationship

from ..db.database import Base


class HoldStatus(str, PyEnum):
    """Enumeration of hold states."""

    PENDING = "pending"
    EXPIRED = "expired"
    CONFIRMED = "confirmed"


class Hold(Base):
    """Represents a temporary hold on a booking slot."""

    __tablename__ = "holds"

    __table_args__ = (
        Index(
            "uq_pending_holds",
            "provider_id",
            "start_time",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(HoldStatus), default=HoldStatus.PENDING, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    client = relationship("Client")
    service = relationship("Service")
    provider = relationship("Provider")
    location = relationship("Location")

    def __repr__(self) -> str:
        return (
            f"<Hold id={self.id} service_id={self.service_id} start_time={self.start_time} "
            f"status={self.status}>"
        )