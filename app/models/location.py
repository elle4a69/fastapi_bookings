"""Location model.

Represents a physical location where services are provided. Locations can
have their own working hours and time zone. They are linked to
bookings.
"""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from ..db.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    timezone = Column(String, nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    bookings = relationship("Booking", back_populates="location")

    # New: resources associated with this location (rooms, equipment, etc.)
    resources = relationship(
        "Resource", back_populates="location", cascade="all, delete-orphan", lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<Location id={self.id} name={self.name}>"