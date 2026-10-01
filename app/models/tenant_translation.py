"""Tenant Translation and Terminology model.

Stores tenant-specific dynamic terminology, industry wording presets,
and locale configurations for both public portals and admin dashboards.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..db.database import Base


class TenantTranslation(Base):
    """Represents the custom wording and translation configuration for a tenant.

    Attributes:
        id: Primary key.
        tenant_id: Foreign key referencing the Tenant (1-to-1 unique mapping).
        locale: Language / locale code (default: 'en').
        terminology: JSON dictionary mapping standardized system keys
                     (e.g., 'client', 'clients', 'provider', 'providers',
                      'booking', 'bookings', 'service', 'services', 'location', 'locations')
                     to industry-specific terms.
        created_at: Record creation timestamp.
        updated_at: Record last update timestamp.
    """

    __tablename__ = "tenant_translations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    locale = Column(String(10), default="en", nullable=False)
    terminology = Column(JSON, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant", back_populates="translation")

    def __repr__(self) -> str:
        return f"<TenantTranslation id={self.id} tenant_id={self.tenant_id} locale={self.locale}>"
