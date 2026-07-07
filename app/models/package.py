"""Service package models.

Packages allow bundling multiple services into a single product that
clients can purchase.  Each package consists of one or more steps
(``PackageStep``) that reference individual services.  Packages
support complex flows like "Initial Consultation + 5 follow‑up
appointments" where each step can have its own duration and offset
relative to the initial booking.  Packages can be sold with a single
price or allow step‑level pricing.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.database import Base


class ServicePackage(Base):
    """Represents a package of services sold as a unit.

    Attributes:
        id: Primary key.
        name: Human‑readable name.
        description: Optional description.
        price: Package price (sum of step prices if ``None``).
        active: Whether the package is available.
        created_at: Timestamp when the package was created.
    """

    __tablename__ = "service_packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    steps = relationship(
        "PackageStep",
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="PackageStep.order",
    )

    def __repr__(self) -> str:
        return f"<ServicePackage id={self.id} name={self.name}>"


class PackageStep(Base):
    """A step within a service package.

    Each step references a service and defines its position in the
    package.  The ``offset_days`` field allows scheduling follow‑up
    appointments relative to the initial booking date (e.g. follow up
    14 days after the first appointment).
    """

    __tablename__ = "package_steps"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("service_packages.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    order = Column(Integer, nullable=False)
    offset_days = Column(Integer, default=0, nullable=False)
    price = Column(Float, nullable=True)
    active = Column(Boolean, default=True, nullable=False)

    # Relationships
    package = relationship("ServicePackage", back_populates="steps")
    service = relationship("Service")

    def __repr__(self) -> str:
        return (
            f"<PackageStep package_id={self.package_id} service_id={self.service_id} "
            f"order={self.order}>"
        )