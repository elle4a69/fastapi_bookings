"""Tenant Modules and Entitlements Schemas.

Defines request and response schemas for tenant modules, tier quotas,
and active feature flags.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class TenantModuleInfo(BaseModel):
    """Details for a single system or add-on module."""

    key: str = Field(..., description="Unique machine key for the module")
    name: str = Field(..., description="Human-readable module name")
    description: str = Field(..., description="Short explanation of module features")
    category: str = Field(..., description="Grouping category (e.g. core, operations, finance)")
    is_core: bool = Field(..., description="Whether this is a non-disableable core module")
    enabled: bool = Field(..., description="Whether this module is active for the current tenant")
    icon: str = Field(..., description="Lucide icon name identifier")


class TenantModulesResponse(BaseModel):
    """Full entitlements and modules payload for the tenant."""

    tier: str = Field(..., description="Current subscription tier (starter, growth, unlimited)")
    addon_quota: int = Field(..., description="Maximum allowed active add-on modules")
    used_addons: int = Field(..., description="Number of currently enabled add-on modules")
    available_addons: int = Field(..., description="Remaining available add-on slots")
    modules: List[TenantModuleInfo] = Field(..., description="Catalog of all modules and their status")


class ToggleModuleRequest(BaseModel):
    """Request payload to toggle a module on or off."""

    module_key: str = Field(..., description="Key of the module to toggle")
    enabled: bool = Field(..., description="Target enabled state")


class ToggleModuleResponse(BaseModel):
    """Response returned after a module toggle operation."""

    ok: bool = True
    message: str
    enabled_modules: List[str]


class UpdateTenantTierRequest(BaseModel):
    """Request to update a tenant's subscription tier and quota."""

    tier: str = Field(..., description="Target tier: 'starter', 'growth', or 'unlimited'")
    addon_quota: Optional[int] = Field(None, description="Optional custom quota override")
