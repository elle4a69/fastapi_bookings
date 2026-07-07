"""Schedule and work calendar models.

These models add a scheduling layer for provider working hours, special
day overrides, blocked intervals and temporary reservations.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..db.database import Base


class ProviderWorkDay(Base):
    """Weekly working-hours rule.

    A rule may be scoped to a provider and/or location. If provider_id
    is null, the rule acts as a company default. Weekday uses Python's
    convention: Monday=0, Sunday=6. start_time and end_time are HH:MM
    strings representing the daily working window. If both are null the
    day is treated as a full working day.
    """

    __tablename__ = "provider_workdays"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    weekday = Column(Integer, nullable=False)
    start_time = Column(String, nullable=True)  # HH:MM
    end_time = Column(String, nullable=True)    # HH:MM
    is_working = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")
    provider = relationship("Provider")
    location = relationship("Location")


class ProviderSpecialDay(Base):
    """One-off special-day override for holidays, days off or changed hours.

    When a special day is defined for a provider on a given date, it
    overrides the weekly workday rule. If provider_id is null the
    special day acts as a company-wide override. If is_working is
    False the day is completely unavailable. Otherwise start_time and
    end_time define the working window for that date.
    """

    __tablename__ = "provider_special_days"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    date = Column(Date, nullable=False)
    is_working = Column(Boolean, default=False, nullable=False)
    start_time = Column(String, nullable=True)  # HH:MM
    end_time = Column(String, nullable=True)    # HH:MM
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")
    provider = relationship("Provider")
    location = relationship("Location")


class BlockedTime(Base):
    """Explicit unavailable interval such as a break, leave or manual block.

    A blocked time marks a period where no bookings should be allowed.
    Blocks can be scoped to a specific provider or apply to all
    providers. Only active blocks are considered when computing
    availability.
    """

    __tablename__ = "blocked_times"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")
    provider = relationship("Provider")
    location = relationship("Location")


class ReservedTime(Base):
    """Temporary reserved interval not yet represented by a booking."""

    __tablename__ = "reserved_times"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="reserved", nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")
    provider = relationship("Provider")
    service = relationship("Service")
    client = relationship("Client")
    location = relationship("Location")
