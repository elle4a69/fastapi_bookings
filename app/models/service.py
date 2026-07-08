"""Service model.

Represents a service that can be booked. Services are associated
with providers and determine the duration and cost of an appointment.
"""

from sqlalchemy import Boolean, Column, Float, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from ..db.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    duration = Column(Integer, nullable=False, comment="Duration in minutes")
    price = Column(Float, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    
    # Prep and Cleanup buffers (in minutes)
    buffer_before = Column(Integer, default=0, nullable=False)
    buffer_after = Column(Integer, default=0, nullable=False)
    
    # Optional comma-separated list of fixed start times (HH:MM), e.g., "09:00,12:00,15:00"
    fixed_start_times = Column(String, nullable=True)

    is_visible = Column(Boolean, default=True, nullable=False)
    deposit_amount = Column(Float, default=0.0, nullable=False)
    tax_rate_id = Column(Integer, ForeignKey("tax_rates.id", ondelete="SET NULL"), nullable=True)
    min_group_size = Column(Integer, default=1, nullable=False)
    max_group_size = Column(Integer, nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    bookings = relationship("Booking", back_populates="service")

    # Resource requirements for this service
    resource_requirements = relationship(
        "ServiceResourceRequirement",
        back_populates="service",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    # Categories to which this service belongs
    categories = relationship(
        "ServiceCategory",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    # Providers eligible to perform this service
    providers = relationship(
        "ServiceProvider",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    # Add‑ons available for this service
    add_ons = relationship(
        "AddOn",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    # Products associated with this service (upsells)
    products = relationship(
        "ServiceProduct",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Service id={self.id} name={self.name}>"