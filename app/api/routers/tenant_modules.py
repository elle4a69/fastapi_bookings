"""Tenant Modules and Entitlements router.

Exposes endpoints for viewing, toggling, and managing active tenant modules,
subscription tiers, and add-on quotas.
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_tenant, get_current_admin
from ...models.tenant import Tenant, CORE_MODULE_KEYS, ADDON_MODULE_KEYS
from ...models.user import User
from ...models.platform_billing import (
    SubscriptionProjection,
    EntitlementSnapshot,
    PlatformEntitlementGrant,
)
from ...schemas.tenant_modules import (
    EntitlementSnapshotInfo,
    TenantModuleInfo,
    TenantModulesResponse,
    ToggleModuleRequest,
    ToggleModuleResponse,
    UpdateTenantTierRequest,
    UpdateTenantModulesRequest,
)
from ...services.platform_billing.entitlement_guard import EntitlementGuardService, _as_utc
from ...services.platform_billing.projection_service import PLAN_ENTITLEMENT_CATALOG

router = APIRouter(tags=["tenant-modules"])

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
    # 5 Core Module Controls
    {
        "key": "multiple_providers",
        "name": "Multiple Service Providers",
        "description": "Support multi-provider staff scheduling and assignment controls. When disabled, the business runs as a solo practice with a single default provider, simplifying workflows everywhere.",
        "category": "Operations",
        "is_core": False,
        "icon": "UserRoundCog",
    },
    {
        "key": "providers",
        "name": "Staff & Service Providers",
        "description": "Legacy alias for Multiple Service Providers.",
        "category": "Operations",
        "is_core": False,
        "icon": "UserRoundCog",
    },
    {
        "key": "locations",
        "name": "Locations",
        "description": "Manage multiple physical branches, locations, rooms, and location-specific resources. When disabled, the business operates from a single default location.",
        "category": "Operations",
        "is_core": False,
        "icon": "MapPin",
    },
    {
        "key": "relationship_matrix",
        "name": "Relationship Matrix",
        "description": "Interactive visual matrix mapping connected dependencies between providers, locations, services, add-ons, and categories.",
        "category": "Operations",
        "is_core": False,
        "icon": "GitBranch",
    },
    {
        "key": "relationships_matrix",
        "name": "Relationship Matrix",
        "description": "Legacy alias for Relationship Matrix.",
        "category": "Operations",
        "is_core": False,
        "icon": "GitBranch",
    },
    {
        "key": "categories",
        "name": "Categories",
        "description": "Group services into categorized sections and tabs. When disabled, services are presented in a streamlined flat list without category management.",
        "category": "Catalog",
        "is_core": False,
        "icon": "Tags",
    },
    {
        "key": "products",
        "name": "Products",
        "description": "Retail and digital product catalog with inventory. When disabled, product options, tabs, and navigation are removed.",
        "category": "Catalog",
        "is_core": False,
        "icon": "ShoppingBag",
    },
    {
        "key": "addons",
        "name": "Add-ons",
        "description": "Optional service extras and upsells selectable during booking. When disabled, services book directly without add-on steps.",
        "category": "Catalog",
        "is_core": False,
        "icon": "Sparkles",
    },
    {
        "key": "packages",
        "name": "Packages & Service Bundles",
        "description": "Sell and manage prepaid bundles, multi-session packages, and promotional deals.",
        "category": "Catalog",
        "is_core": False,
        "icon": "Gift",
    },
    # Other Add-ons
    {
        "key": "sms_assistant",
        "name": "SMS Assistant & AI Triage",
        "description": "Two-way automated SMS customer conversations, appointment triage, and staff handoff.",
        "category": "Communication",
        "is_core": False,
        "icon": "MessageSquareText",
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


def _build_modules_response(tenant: Tenant, db: Optional[Session] = None) -> TenantModulesResponse:
    """Build response model from tenant model, local projection, and active entitlements."""
    enabled_keys = set(tenant.get_enabled_modules())
    effective_tier = tenant.subscription_tier or "starter"
    entitlements_dict: dict[str, EntitlementSnapshotInfo] = {}

    if db is not None:
        # Check authoritative subscription projection
        proj = (
            db.query(SubscriptionProjection)
            .filter(
                SubscriptionProjection.tenant_id == tenant.id,
                SubscriptionProjection.status.in_(["active", "trialing"]),
            )
            .order_by(SubscriptionProjection.id.desc())
            .first()
        )
        if proj:
            effective_tier = proj.plan_id

        # Collect snapshot records
        snapshots = (
            db.query(EntitlementSnapshot)
            .filter(EntitlementSnapshot.tenant_id == tenant.id)
            .all()
        )
        for s in snapshots:
            expires_iso = s.expires_at.isoformat() if s.expires_at else None
            entitlements_dict[s.entitlement_key] = EntitlementSnapshotInfo(
                key=s.entitlement_key,
                value_type=s.value_type,
                value=s.value,
                is_active=s.is_active,
                expires_at=expires_iso,
            )

        # Collect active platform grants (take precedence)
        now = datetime.now(timezone.utc)
        grants = (
            db.query(PlatformEntitlementGrant)
            .filter(
                PlatformEntitlementGrant.tenant_id == tenant.id,
                PlatformEntitlementGrant.is_revoked == False,
            )
            .all()
        )
        for g in grants:
            g_exp = _as_utc(g.expires_at) if g.expires_at else None
            if g_exp is None or g_exp > now:
                expires_iso = g.expires_at.isoformat() if g.expires_at else None
                entitlements_dict[g.entitlement_key] = EntitlementSnapshotInfo(
                    key=g.entitlement_key,
                    value_type=g.value_type,
                    value=g.granted_value,
                    is_active=True,
                    expires_at=expires_iso,
                )

    if not entitlements_dict:
        catalog = PLAN_ENTITLEMENT_CATALOG.get(
            effective_tier.lower(),
            PLAN_ENTITLEMENT_CATALOG.get("starter", {}),
        )
        for k, (vtype, vval) in catalog.items():
            entitlements_dict[k] = EntitlementSnapshotInfo(
                key=k,
                value_type=vtype,
                value=str(vval),
                is_active=True,
                expires_at=None,
            )

    # Count unique functional addons so aliased keys don't consume extra quota
    unique_addon_keys = set()
    for k in enabled_keys:
        if k in CORE_MODULE_KEYS:
            continue
        canon_key = (
            "multiple_providers"
            if k in ("multiple_providers", "providers")
            else (
                "addons"
                if k in ("addons", "packages")
                else (
                    "relationship_matrix"
                    if k in ("relationship_matrix", "relationships_matrix")
                    else k
                )
            )
        )
        unique_addon_keys.add(canon_key)
    used_addons = len(unique_addon_keys)

    addon_quota = tenant.addon_quota if tenant.addon_quota is not None else 0
    if effective_tier in ("unlimited", "enterprise"):
        available_addons = 999
    else:
        available_addons = max(0, addon_quota - used_addons)

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
        tier=effective_tier,
        addon_quota=addon_quota,
        used_addons=used_addons,
        available_addons=available_addons,
        modules=module_infos,
        entitlements=entitlements_dict,
    )


@router.get("/api/admin/tenant/modules", response_model=TenantModulesResponse)
@router.get("/api/admin/tenant-modules", response_model=TenantModulesResponse)
def get_tenant_modules(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TenantModulesResponse:
    """Return current tenant subscription tier, quota, and module catalog with status."""
    return _build_modules_response(tenant, db=db)


def _check_module_entitlement_prerequisites(db: Session, tenant_id: int, module_key: str) -> None:
    """Validate that tenant satisfies required entitlements before enabling a module."""
    canon = (
        "multiple_providers"
        if module_key in ("multiple_providers", "providers")
        else (
            "locations"
            if module_key == "locations"
            else (
                "sms_assistant"
                if module_key == "sms_assistant"
                else module_key
            )
        )
    )
    if canon == "multiple_providers":
        eff = EntitlementGuardService.get_effective_entitlement(db, tenant_id, "providers.max")
        if eff is not None and eff[1] <= 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Entitlement 'providers.max > 1' required to enable Multiple Service Providers. Please upgrade your plan.",
            )
    elif canon == "locations":
        eff = EntitlementGuardService.get_effective_entitlement(db, tenant_id, "locations.max")
        if eff is not None and eff[1] <= 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Entitlement 'locations.max > 1' required to enable Locations module. Please upgrade your plan.",
            )
    elif canon == "sms_assistant":
        if not EntitlementGuardService.has_entitlement(db, tenant_id, "sms.enabled", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Entitlement 'sms.enabled' required to enable SMS Assistant. Please upgrade your plan.",
            )


@router.post("/api/admin/tenant/modules/toggle", response_model=ToggleModuleResponse)
@router.post("/api/admin/tenant-modules/toggle", response_model=ToggleModuleResponse)
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

    current_enabled = set(tenant.get_enabled_modules())

    # Map aliases
    target_keys = {payload.module_key}
    if payload.module_key in ("multiple_providers", "providers"):
        target_keys = {"multiple_providers", "providers"}
    elif payload.module_key in ("addons", "packages"):
        target_keys = {"addons", "packages"}
    elif payload.module_key in ("relationship_matrix", "relationships_matrix"):
        target_keys = {"relationship_matrix", "relationships_matrix"}

    # Count unique active addons
    current_addons = {
        (
            "multiple_providers"
            if k in ("multiple_providers", "providers")
            else (
                "addons"
                if k in ("addons", "packages")
                else (
                    "relationship_matrix"
                    if k in ("relationship_matrix", "relationships_matrix")
                    else k
                )
            )
        )
        for k in current_enabled
        if k not in CORE_MODULE_KEYS
    }

    canon_target = (
        "multiple_providers"
        if payload.module_key in ("multiple_providers", "providers")
        else (
            "addons"
            if payload.module_key in ("addons", "packages")
            else (
                "relationship_matrix"
                if payload.module_key in ("relationship_matrix", "relationships_matrix")
                else payload.module_key
            )
        )
    )

    # Validate that relationship_matrix strictly requires multiple_providers to be active
    if payload.enabled and canon_target == "relationship_matrix":
        has_multi = any(k in current_enabled for k in ("multiple_providers", "providers"))
        if not has_multi:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Relationship Matrix requires Multiple Service Providers to be enabled.",
            )

    # Validate prerequisite entitlement when enabling
    if payload.enabled:
        _check_module_entitlement_prerequisites(db, tenant.id, payload.module_key)

    # Validate against quota when enabling an add-on
    if payload.enabled and canon_target not in current_addons:
        if tenant.subscription_tier != "unlimited" and len(current_addons) >= tenant.addon_quota:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Add-on quota reached. Your {tenant.subscription_tier.title()} plan allows "
                    f"{tenant.addon_quota} active add-on(s). Please upgrade to enable more."
                ),
            )

    # Compute new list of enabled modules
    new_set = set(current_enabled)
    if payload.enabled:
        new_set.update(target_keys)
    else:
        new_set.difference_update(target_keys)

    tenant.enabled_modules = list(new_set)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return ToggleModuleResponse(
        ok=True,
        message=f"Module '{catalog_entry['name']}' {'enabled' if payload.enabled else 'disabled'} successfully.",
        enabled_modules=tenant.get_enabled_modules(),
    )


@router.put("/api/admin/tenant/modules/tier", response_model=TenantModulesResponse)
@router.put("/api/admin/tenant-modules/tier", response_model=TenantModulesResponse)
def update_tenant_tier(
    payload: UpdateTenantTierRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TenantModulesResponse:
    """Update subscription tier and quota (restricted to platform owner)."""
    is_platform = (
        bool(getattr(current_user, "is_platform_owner", False))
        or bool(getattr(current_user, "is_superuser", False))
        or (getattr(current_user, "role", "") or "").lower() == "platform_owner"
    )
    if not is_platform:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Platform owner privilege required to manage subscription tiers.",
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

    return _build_modules_response(tenant, db=db)


@router.put("/api/admin/tenant/modules", response_model=TenantModulesResponse)
@router.put("/api/admin/tenant-modules", response_model=TenantModulesResponse)
def put_tenant_modules(
    payload: UpdateTenantModulesRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> TenantModulesResponse:
    """Update enabled modules or tier in bulk via PUT."""
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners have permission to manage tenant modules.",
        )

    if payload.tier or payload.addon_quota is not None:
        is_platform = (
            bool(getattr(current_user, "is_platform_owner", False))
            or bool(getattr(current_user, "is_superuser", False))
            or (getattr(current_user, "role", "") or "").lower() == "platform_owner"
        )
        if not is_platform:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Platform owner privilege required to modify subscription tiers or quotas.",
            )
        if payload.tier:
            tier = payload.tier.lower()
            if tier not in {"starter", "growth", "unlimited"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid subscription tier '{payload.tier}'.",
                )
            tenant.subscription_tier = tier
            if payload.addon_quota is not None:
                tenant.addon_quota = payload.addon_quota
            else:
                default_quotas = {"starter": 0, "growth": 3, "unlimited": 999}
                tenant.addon_quota = default_quotas[tier]

    current_enabled = set(tenant.get_enabled_modules())

    if payload.enabled_modules is not None:
        target_keys = set(payload.enabled_modules)
        # Ensure core modules cannot be turned off
        target_keys.update(CORE_MODULE_KEYS)
        # Validate prerequisite entitlements for any non-core modules being enabled
        for mod in target_keys:
            if mod not in CORE_MODULE_KEYS and mod not in current_enabled:
                _check_module_entitlement_prerequisites(db, tenant.id, mod)
        # Synchronize aliases
        if "multiple_providers" in target_keys or "providers" in target_keys:
            target_keys.update(["multiple_providers", "providers"])
        if "addons" in target_keys or "packages" in target_keys:
            target_keys.update(["addons", "packages"])
        if "relationship_matrix" in target_keys or "relationships_matrix" in target_keys:
            target_keys.update(["relationship_matrix", "relationships_matrix"])
        tenant.enabled_modules = list(target_keys)

    elif payload.modules is not None:
        for k, enabled in payload.modules.items():
            if enabled and k not in current_enabled:
                _check_module_entitlement_prerequisites(db, tenant.id, k)
            aliases = {k}
            if k in ("multiple_providers", "providers"):
                aliases = {"multiple_providers", "providers"}
            elif k in ("addons", "packages"):
                aliases = {"addons", "packages"}
            elif k in ("relationship_matrix", "relationships_matrix"):
                aliases = {"relationship_matrix", "relationships_matrix"}
            if enabled:
                current_enabled.update(aliases)
            else:
                current_enabled.difference_update(aliases)
        current_enabled.update(CORE_MODULE_KEYS)
        tenant.enabled_modules = list(current_enabled)

    elif payload.module_key is not None:
        enabled = payload.enabled if payload.enabled is not None else True
        if enabled and payload.module_key not in current_enabled:
            _check_module_entitlement_prerequisites(db, tenant.id, payload.module_key)
        aliases = {payload.module_key}
        if payload.module_key in ("multiple_providers", "providers"):
            aliases = {"multiple_providers", "providers"}
        elif payload.module_key in ("addons", "packages"):
            aliases = {"addons", "packages"}
        elif payload.module_key in ("relationship_matrix", "relationships_matrix"):
            aliases = {"relationship_matrix", "relationships_matrix"}
        if enabled:
            current_enabled.update(aliases)
        else:
            current_enabled.difference_update(aliases)
        current_enabled.update(CORE_MODULE_KEYS)
        tenant.enabled_modules = list(current_enabled)

    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return _build_modules_response(tenant, db=db)

