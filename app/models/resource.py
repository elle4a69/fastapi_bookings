"""Resource model.

Resources represent physical or logical assets that may be required
during a booking.  Examples include rooms, pieces of equipment,
workstations or other capacity‑limited entities.  A service can be
configured to require one or more resources via the
``ServiceResourceRequirement`` model.  When a booking is created, the
scheduling engine allocates available resources according to the
service requirements.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.database import Base


class Resource(Base):
    """Represents a capacity‑limited resource.

    Attributes:
        id: Primary key.
        tenant_id: Tenant owner.
        name: Name of the resource (e.g. "Room A" or "Massage Table 1").
        type: Arbitrary string describing the type of resource.  You can
            group resources by type to express substitutable resources
            (e.g. any "room" resource can fulfil a requirement).
        location_id: Optional foreign key to the location where this
            resource resides.  Use this to restrict resource usage to
            specific locations.
        capacity: Number of simultaneous bookings this resource can
            accommodate.  For exclusive resources set capacity to 1.
        active: Whether the resource can be allocated.
        created_at: Timestamp when the resource was created.
    """

    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    capacity = Column(Integer, default=1, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    location = relationship("Location", back_populates="resources")
    allocations = relationship(
        "BookingResourceAllocation", back_populates="resource", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Resource id={self.id} name={self.name} type={self.type}>"


class ServiceResourceRequirement(Base):
    """Association table linking services to required resources."""

    __tablename__ = "service_resource_requirements"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    resource_type = Column(String, nullable=False)
    quantity = Column(Integer, default=1, nullable=False)

    # Relationships
    service = relationship("Service", back_populates="resource_requirements")

    def __repr__(self) -> str:
        return (
            f"<ServiceResourceRequirement service_id={self.service_id} "
            f"type={self.resource_type} quantity={self.quantity}>"
        )


class BookingResourceAllocation(Base):
    """Links a booking to the resources allocated for that booking."""

    __tablename__ = "booking_resource_allocations"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)

    # Relationships
    booking = relationship("Booking", back_populates="resource_allocations")
    resource = relationship("Resource", back_populates="allocations")

    def __repr__(self) -> str:
        return (
            f"<BookingResourceAllocation booking_id={self.booking_id} "
            f"resource_id={self.resource_id} quantity={self.quantity}>"
        )