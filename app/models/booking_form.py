"""Persisted tenant-scoped configurable booking forms."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.database import Base


class BookingForm(Base):
    __tablename__ = "booking_forms"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_booking_forms_tenant_slug"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    module_order = Column(JSON, nullable=False)
    enabled_modules = Column(JSON, nullable=False)
    predefined_values = Column(JSON, nullable=False, default=dict)
    provider_selection_mode = Column(String, nullable=False, default="required")
    clear_session_on_start = Column(Boolean, default=False, nullable=False)
    allow_switch_to_ada = Column(Boolean, default=False, nullable=False)
    widget_type = Column(String, nullable=False, default="inline")
    appearance = Column(JSON, nullable=False, default=dict)
    settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant")
