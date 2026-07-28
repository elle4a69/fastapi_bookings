"""Tenant-scoped provider/category restrictions."""

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.database import Base


class ProviderCategory(Base):
    __tablename__ = "provider_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "provider_id", "category_id", name="uq_provider_categories_pair"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)

    tenant = relationship("Tenant")
    provider = relationship("Provider")
    category = relationship("Category")
