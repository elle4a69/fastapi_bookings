"""Service add‑on model.

Add‑ons are optional extras that can be attached to a service when
booking.  For example, a hairdresser appointment might offer an
add‑on for deep conditioning.  Each add‑on belongs to a service and
can have its own price and duration.  Clients can select one or more
add‑ons when booking a service.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Numeric
from sqlalchemy.orm import relationship

from ..db.database import Base


class AddOn(Base):
    """Represents an add‑on that can be attached to a booking.

    Attributes:
        id: Primary key.
        service_id: Foreign key to the service this add‑on belongs to.
        name: Human‑readable name of the add‑on.
        description: Optional description.
        price: Price for the add‑on; if ``None`` the add‑on is free.
        duration: Additional duration in minutes; can be zero.
        active: Whether the add‑on is available to clients.
        created_at: Timestamp when the add‑on was created.
    """

    __tablename__ = "add_ons"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    duration = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    service = relationship("Service", back_populates="add_ons")

    def __repr__(self) -> str:
        return f"<AddOn id={self.id} name={self.name} service_id={self.service_id}>"