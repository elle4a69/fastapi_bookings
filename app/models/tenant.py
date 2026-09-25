"""Tenant model.

This module defines the ``Tenant`` model used to support a multi‑tenant
architecture. Each tenant represents a separate business or account
within the system. Most domain models reference a ``tenant_id``
to ensure data isolation between tenants.
"""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import Column, DateTime, Integer, String, Float, JSON
from ..db.database import Base

CORE_MODULE_KEYS: list[str] = ["dashboard", "calendar", "bookings", "website"]

ADDON_MODULE_KEYS: list[str] = [
    "sms_assistant",
    "locations",
    "providers",
    "packages",
    "finance_invoicing",
    "media",
    "booking_forms",
    "reviews",
    "calcom_scheduling",
]

ALL_MODULE_KEYS: list[str] = CORE_MODULE_KEYS + ADDON_MODULE_KEYS


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
        subscription_tier: Subscription tier ('starter', 'growth', 'unlimited').
        addon_quota: Maximum number of active add-on modules allowed (Starter=0, Growth=3, Unlimited=999).
        enabled_modules: List of active module keys.
    """

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    subdomain = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Entitlements & Subscription Tiers
    subscription_tier = Column(String, default="starter", nullable=False)
    addon_quota = Column(Integer, default=0, nullable=False)
    enabled_modules = Column(JSON, nullable=True)

    # Business Profile & Settings
    timezone = Column(String, default="UTC", nullable=False)
    country = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    public_address_visibility = Column(String, default="visible", nullable=False)
    max_advance_days = Column(Integer, default=60, nullable=False)
    
    # Discovery & Location Details
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    logo_url = Column(String, nullable=True)

    def get_enabled_modules(self) -> list[str]:
        """Return list of enabled modules for this tenant.

        Safe defaults:
        - For tenant 'simplydemo' or when enabled_modules is None, default to enabling
          all core modules (and for 'simplydemo' all modules) so existing tests/demo flows
          are never broken!
        - Core modules (dashboard, calendar, bookings, website) are always enabled.
        """
        if self.subdomain == "simplydemo" and self.enabled_modules is None:
            return list(ALL_MODULE_KEYS)

        if self.enabled_modules is None:
            return list(CORE_MODULE_KEYS)

        active = set(self.enabled_modules)
        active.update(CORE_MODULE_KEYS)

        # Preserve standard order followed by any custom keys
        ordered = [k for k in ALL_MODULE_KEYS if k in active]
        for k in active:
            if k not in ordered:
                ordered.append(k)
        return ordered

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} name={self.name} subdomain={self.subdomain} tier={self.subscription_tier}>"