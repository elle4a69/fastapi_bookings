"""Tenant model.

This module defines the ``Tenant`` model used to support a multi‑tenant
architecture. Each tenant represents a separate business or account
within the system. Most domain models reference a ``tenant_id``
to ensure data isolation between tenants.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String
from ..db.database import Base


class Tenant(Base):
    """Represents a business account (tenant).

    Tenants allow multiple independent businesses to use the same
    application without interfering with one another. Each tenant
    contains its own configuration, modules, subdomain and data.

    Attributes:
        id: Primary key.
        name: Human‑readable name of the tenant (e.g. company name).
        subdomain: Lowercase URL slug used to identify the tenant.
        created_at: Timezone-aware timestamp when the tenant was created.
    """

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    subdomain = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} name={self.name} subdomain={self.subdomain}>"