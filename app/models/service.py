"""Service model.

Represents a service that can be booked. Services are associated
with providers and determine the duration and cost of an appointment.
"""

from sqlalchemy import Boolean, Column, Float, Integer, String, ForeignKey, Numeric, DateTime, event
from sqlalchemy.orm import relationship

from ..db.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    duration = Column(Integer, nullable=False, comment="Duration in minutes")
    price = Column(Numeric(10, 2), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Prep and Cleanup buffers (in minutes)
    buffer_before = Column(Integer, default=0, nullable=False)
    buffer_after = Column(Integer, default=0, nullable=False)
    
    # Optional comma-separated list of fixed start times (HH:MM), e.g., "09:00,12:00,15:00"
    fixed_start_times = Column(String, nullable=True)

    is_visible = Column(Boolean, default=True, nullable=False)
    allow_in_call = Column(Boolean, default=True, nullable=False)
    allow_out_call = Column(Boolean, default=True, nullable=False)
    outcall_price = Column(Numeric(10, 2), nullable=True)
    outcall_buffer_before = Column(Integer, default=0, nullable=False)
    outcall_buffer_after = Column(Integer, default=0, nullable=False)
    deposit_amount = Column(Numeric(10, 2), default=0.0, nullable=False)
    max_advance_days = Column(Integer, nullable=True)
    tax_rate_id = Column(Integer, ForeignKey("tax_rates.id", ondelete="SET NULL"), nullable=True)
    min_group_size = Column(Integer, default=1, nullable=False)
    max_group_size = Column(Integer, nullable=True)
    image = Column(String, nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    bookings = relationship("Booking", back_populates="service")

    # Resource requirements for this service
    resource_requirements = relationship(
        "ServiceResourceRequirement",
        back_populates="service",
        cascade="all, delete-orphan",
        lazy="selectin",
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
        "ServiceAddOn",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    # Products associated with this service (upsells)
    products = relationship(
        "ServiceProduct",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    @property
    def category_ids(self) -> list[int]:
        return [sc.category_id for sc in self.categories]

    @property
    def provider_ids(self) -> list[int]:
        return [sp.provider_id for sp in self.providers]

    @property
    def addon_ids(self) -> list[int]:
        return [sa.add_on_id for sa in self.add_ons]

    @property
    def product_ids(self) -> list[int]:
        return [sp.product_id for sp in self.products]

    @property
    def requirements(self):
        return self.resource_requirements

    @property
    def effective_outcall_price(self):
        """Return explicit outcall_price, falling back to price if outcall is allowed."""
        if self.outcall_price is not None:
            return self.outcall_price
        if self.allow_out_call:
            return self.price
        return None

    def __repr__(self) -> str:
        return f"<Service id={self.id} name={self.name}>"


@event.listens_for(Service, "before_insert")
def _default_service_outcall_price(mapper, connection, target):
    """Default outcall_price to price if outcall is enabled and outcall_price not explicitly given."""
    if target.allow_out_call and target.outcall_price is None and target.price is not None:
        target.outcall_price = target.price
