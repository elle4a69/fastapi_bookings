"""Service‑provider assignment model.

This module defines a many‑to‑many relationship between services and
providers.  In many businesses not all providers can perform every
service.  The ``ServiceProvider`` association table captures which
provider is eligible to deliver which services.  When computing
availability or creating bookings the scheduling engine should only
consider providers that are assigned to the requested service.
"""

from sqlalchemy import Column, ForeignKey, Integer
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

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)

    # Relationships
    service = relationship("Service", back_populates="providers")
    provider = relationship("Provider", back_populates="services")

    def __repr__(self) -> str:
        return (
            f"<ServiceProvider service_id={self.service_id} provider_id={self.provider_id}>"
        )