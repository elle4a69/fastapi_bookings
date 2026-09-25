"""Provider model.

Represents a person who provides services. Providers can have
working hours, breaks and are linked to bookings.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text
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
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    is_visible = Column(Boolean, default=True, nullable=False)
    capacity = Column(Integer, default=1, nullable=False)
    color = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    ignore_company_hours = Column(Boolean, default=False, nullable=False)
    image = Column(Text, nullable=True)
    weekly_schedule = Column(JSON, nullable=True)

    # In-call and Out-call routing & scheduling attributes
    in_call_address = Column(String, nullable=True)
    out_call_radius_km = Column(Float, default=25.0, nullable=False)
    base_outcall_surcharge = Column(Numeric(10, 2), default=0.00, nullable=False)
    per_km_fee = Column(Numeric(10, 2), default=0.00, nullable=False)
    turnaround_buffer_mins = Column(Integer, default=15, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    bookings = relationship("Booking", back_populates="provider")

    # Services this provider is eligible to deliver
    services = relationship(
        "ServiceProvider",
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    @property
    def service_ids(self) -> list[int]:
        return [s.service_id for s in self.services]

    @property
    def thumbnail(self) -> str | None:
        """Return only images safe to include in provider collection views."""
        if self.image and len(self.image) <= 150 * 1024:
            return self.image
        return None

    def __repr__(self) -> str:
        return f"<Provider id={self.id} name={self.name}>"
