"""Location model.

Represents a physical location where services are provided. Locations can
have their own working hours and time zone. They are linked to
bookings.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship

from ..db.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    timezone = Column(String, nullable=True)
    image = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    is_visible = Column(Boolean, default=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    bookings = relationship("Booking", back_populates="location")

    # New: resources associated with this location (rooms, equipment, etc.)
    resources = relationship(
        "Resource", back_populates="location", cascade="all, delete-orphan", lazy="joined"
    )

    # Join table relationships
    location_providers = relationship(
        "LocationProvider", back_populates="location", cascade="all, delete-orphan", lazy="joined"
    )
    location_services = relationship(
        "LocationService", back_populates="location", cascade="all, delete-orphan", lazy="joined"
    )
    location_categories = relationship(
        "LocationCategory", back_populates="location", cascade="all, delete-orphan", lazy="joined"
    )
    location_products = relationship(
        "LocationProduct", back_populates="location", cascade="all, delete-orphan", lazy="joined"
    )

    @property
    def provider_ids(self) -> list[int]:
        return [lp.provider_id for lp in self.location_providers]

    @property
    def service_ids(self) -> list[int]:
        return [ls.service_id for ls in self.location_services]

    @property
    def category_ids(self) -> list[int]:
        return [lc.category_id for lc in self.location_categories]

    @property
    def product_ids(self) -> list[int]:
        return [lp.product_id for lp in self.location_products]

    def __repr__(self) -> str:
        return f"<Location id={self.id} name={self.name}>"


class LocationProvider(Base):
    __tablename__ = "location_providers"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "provider_id", name="uq_location_providers_pair"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    tenant = relationship("Tenant")
    location = relationship("Location", back_populates="location_providers")
    provider = relationship("Provider")


class LocationService(Base):
    __tablename__ = "location_services"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "service_id", name="uq_location_services_pair"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)

    tenant = relationship("Tenant")
    location = relationship("Location", back_populates="location_services")
    service = relationship("Service")


class LocationCategory(Base):
    __tablename__ = "location_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "category_id", name="uq_location_categories_pair"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)

    tenant = relationship("Tenant")
    location = relationship("Location", back_populates="location_categories")
    category = relationship("Category")


class LocationProduct(Base):
    __tablename__ = "location_products"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "product_id", name="uq_location_products_pair"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    tenant = relationship("Tenant")
    location = relationship("Location", back_populates="location_products")
    product = relationship("Product")

