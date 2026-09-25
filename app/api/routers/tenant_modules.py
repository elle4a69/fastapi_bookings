"""Tenant Modules and Entitlements router.

Exposes endpoints for viewing, toggling, and managing active tenant modules,
subscription tiers, and add-on quotas.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_tenant, get_current_admin
from ...models.tenant import Tenant, CORE_MODULE_KEYS, ADDON_MODULE_KEYS
from ...models.user import User
from ...schemas.tenant_modules import (
    TenantModuleInfo,
    TenantModulesResponse,
    ToggleModuleRequest,
    ToggleModuleResponse,
    UpdateTenantTierRequest,
)

router = APIRouter(prefix="/api/admin/tenant/modules", tags=["tenant-modules"])

MODULE_CATALOG = [
    # Core Modules (Always enabled, cannot be toggled off)
    {
        "key": "dashboard",
        "name": "Dashboard",
        "description": "Executive overview with real-time appointment metrics, alerts, and quick actions.",
        "category": "Core",
        "is_core": True,
        "icon": "LayoutDashboard",
    },
    {
        "key": "calendar",
        "name": "Calendar",
        "description": "Interactive schedule view with day, week, month, and agenda timelines.",
        "category": "Core",
        "is_core": True,
        "icon": "Calendar",
    },
    {
        "key": "bookings",
        "name": "Bookings Management",
        "description": "Comprehensive appointment booking lifecycle, cancellations, and status tracking.",
        "category": "Core",
        "is_core": True,
        "icon": "ClipboardList",
    },
    {
        "key": "website",
        "name": "Website Builder",
        "description": "Customizable customer-facing booking portal, landing page, and business branding.",
        "category": "Core",
        "is_core": True,
        "icon": "Globe",
    },
    # Add-on Modules (Switchable based on subscription tier & quota)
    {
        "key": "sms_assistant",
        "name": "SMS Assistant & AI Triage",
        "description": "Two-way automated SMS customer conversations, appointment triage, and staff handoff.",
        "category": "Communication",
        "is_core": False,
        "icon": "MessageSquareText",
    },
    {
        "key": "locations",
        "name": "Multi-Location Support",
        "description": "Manage multiple physical branches, locations, rooms, and location-specific resources.",
        "category": "Operations",
        "is_core": False,
        "icon": "MapPin",
    },
    {
        "key": "providers",
        "name": "Staff & Service Providers",
        "description": "Support multi-provider staff scheduling, individual working hours, and commissions.",
        "category": "Operations",
        "is_core": False,
        "icon": "UserRoundCog",
    },
    {
        "key": "packages",
        "name": "Packages & Service Bundles",
        "description": "Sell and manage prepaid bundles, multi-session packages, and promotional deals.",
        "category": "Sales",
        "is_core": False,
        "icon": "Gift",
    },
    {
        "key": "finance_invoicing",
        "name": "Finance & Invoicing",
        "description": "Automated invoice generation, payment processing, tax rates, and sales reports.",
        "category": "Finance",
        "is_core": False,
        "icon": "Landmark",
    },
    {
        "key": "media",
        "name": "Media & Asset Gallery",
        "description": "Manage image uploads, service photos, gallery showcases, and banner assets.",
        "category": "Marketing",
        "is_core": False,
        "icon": "Images",
    },
    {
        "key": "booking_forms",
        "name": "Custom Intake Forms",
        "description": "Configurable booking questionnaires, health intakes, and custom field builders.",
        "category": "Bookings",
        "is_core": False,
        "icon": "FileInput",
    },
    {
        "key": "reviews",
        "name": "Customer Feedback & Reviews",
        "description": "Automated post-service review collection, customer feedback scores, and testimonials.",
        "category": "Marketing",
        "is_core": False,
        "icon": "Star",
    },
    {
        "key": "calcom_scheduling",
        "name": "Cal.com Calendar Sync",
        "description": "Seamless bidirectional calendar sync and schedule federation via Cal.com.",
        "category": "Integrations",
        "is_core": False,
        "icon": "CalendarClock",
    },
]


def _build_modules_response(tenant: Tenant) -> TenantModulesResponse:
    """Build response model from tenant model and catalog."""
    enabled_keys = set(tenant.get_enabled_modules())
    used_addons = len([k for k in enabled_keys if k not in CORE_MODULE_KEYS])

    if tenant.subscription_tier == "unlimited":
        available_addons = 999
    else:
        available_addons = max(0, tenant.addon_quota - used_addons)

    module_infos = [
        TenantModuleInfo(
            key=mod["key"],
            name=mod["name"],
            description=mod["description"],
            category=mod["category"],
            is_core=mod["is_core"],
            icon=mod["icon"],
            enabled=(mod["key"] in enabled_keys),
        )
        for mod in MODULE_CATALOG
    ]

    return TenantModulesResponse(
        tier=tenant.subscription_tier,
        addon_quota=tenant.addon_quota,
        used_addons=used_addons,
        available_addons=available_addons,
        modules=module_infos,
    )


@router.get("", response_model=TenantModulesResponse)
def get_tenant_modules(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
) -> TenantModulesResponse:
    """Return current tenant subscription tier, quota, and module catalog with status."""
    return _build_modules_response(tenant)


@router.post("/toggle", response_model=ToggleModuleResponse)
def toggle_tenant_module(
    payload: ToggleModuleRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ToggleModuleResponse:
    """Toggle a tenant module on or off with owner permission and quota checks."""
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners have permission to manage tenant modules.",
        )

    # Validate module exists in catalog
    catalog_entry = next((m for m in MODULE_CATALOG if m["key"] == payload.module_key), None)
    if not catalog_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown module '{payload.module_key}'.",
        )

    # Prevent disabling core modules
    if catalog_entry["is_core"] and not payload.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Core module '{catalog_entry['name']}' ({payload.module_key}) cannot be disabled.",
        )

    current_enabled = tenant.get_enabled_modules()
    current_addons = [m for m in current_enabled if m not in CORE_MODULE_KEYS]

    # Validate against quota when enabling an add-on
    if payload.enabled and payload.module_key not in current_enabled:
        if tenant.subscription_tier != "unlimited" and len(current_addons) >= tenant.addon_quota:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Add-on quota reached. Your {tenant.subscription_tier.title()} plan allows "
                    f"{tenant.addon_quota} active add-on(s). Please upgrade to enable more."
                ),
            )

    # Compute new list of enabled modules
    if payload.enabled:
        if payload.module_key not in current_enabled:
            new_modules = list(current_enabled) + [payload.module_key]
        else:
            new_modules = list(current_enabled)
    else:
        new_modules = [m for m in current_enabled if m != payload.module_key]

    tenant.enabled_modules = new_modules
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return ToggleModuleResponse(
        ok=True,
        message=f"Module '{catalog_entry['name']}' {'enabled' if payload.enabled else 'disabled'} successfully.",
        enabled_modules=tenant.get_enabled_modules(),
    )


@router.put("/tier", response_model=TenantModulesResponse)
def update_tenant_tier(
    payload: UpdateTenantTierRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TenantModulesResponse:
    """Update subscription tier and quota (for owner / testing)."""
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners have permission to manage subscription tiers.",
        )

    tier = payload.tier.lower()
    if tier not in {"starter", "growth", "unlimited"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription tier '{payload.tier}'. Must be 'starter', 'growth', or 'unlimited'.",
        )

    default_quotas = {"starter": 0, "growth": 3, "unlimited": 999}
    quota = payload.addon_quota if payload.addon_quota is not None else default_quotas[tier]

    tenant.subscription_tier = tier
    tenant.addon_quota = quota
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return _build_modules_response(tenant)
