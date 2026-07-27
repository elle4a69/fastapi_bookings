"""Location model.

Represents a physical location where services are provided. Locations can
have their own working hours and time zone. They are linked to
bookings.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
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

    # Relationships
    tenant = relationship("Tenant")
    bookings = relationship("Booking", back_populates="location")

    # New: resources associated with this location (rooms, equipment, etc.)
    resources = relationship(
        "Resource", back_populates="location", cascade="all, delete-orphan", lazy="joined"
    )

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
    location = relationship("Location")
    provider = relationship("Provider")


class LocationService(Base):
    __tablename__ = "location_services"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "service_id", name="uq_location_services_pair"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)

    tenant = relationship("Tenant")
    location = relationship("Location")
    service = relationship("Service")


class LocationCategory(Base):
    __tablename__ = "location_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "category_id", name="uq_location_categories_pair"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)

    tenant = relationship("Tenant")
    location = relationship("Location")
    category = relationship("Category")


class LocationProduct(Base):
    __tablename__ = "location_products"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "product_id", name="uq_location_products_pair"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    tenant = relationship("Tenant")
    location = relationship("Location")
    product = relationship("Product")

