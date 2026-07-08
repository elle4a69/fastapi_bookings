"""Provider model.

Represents a person who provides services. Providers can have
working hours, breaks and are linked to bookings.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship

from ..db.database import Base


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    is_visible = Column(Boolean, default=True, nullable=False)
    capacity = Column(Integer, default=1, nullable=False)
    color = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    bookings = relationship("Booking", back_populates="provider")

    # Services this provider is eligible to deliver
    services = relationship(
        "ServiceProvider",
        back_populates="provider",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Provider id={self.id} name={self.name}>"