"""Service‑provider assignment model.

This module defines a many‑to‑many relationship between services and
providers.  In many businesses not all providers can perform every
service.  The ``ServiceProvider`` association table captures which
provider is eligible to deliver which services.  When computing
availability or creating bookings the scheduling engine should only
consider providers that are assigned to the requested service.
"""

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.database import Base


class ServiceProvider(Base):
    """Association table linking services and providers.

    Attributes:
        id: Primary key.
        service_id: Foreign key to the service.
        provider_id: Foreign key to the provider.
    """

    __tablename__ = "service_providers"

    __table_args__ = (UniqueConstraint("tenant_id", "service_id", "provider_id", name="uq_service_providers_pair"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    service = relationship("Service", back_populates="providers")
    provider = relationship("Provider", back_populates="services")
    tenant = relationship("Tenant")

    def __repr__(self) -> str:
        return (
            f"<ServiceProvider service_id={self.service_id} provider_id={self.provider_id}>"
        )
