"""Tenants API Router.

Provides endpoints for creating, managing, and retrieving Tenants,
with lifecycle hooks including automated Chatwoot multi-tenant provisioning.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_admin
from ...core.config import settings
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.tenant import TenantCreate, TenantResponse, TenantOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
):
    """Create a new tenant and optionally auto-provision Chatwoot infrastructure."""
    # Enforce subdomain uniqueness
    existing_subdomain = db.query(Tenant).filter(
        Tenant.subdomain == payload.subdomain.lower().strip()
    ).first()
    if existing_subdomain:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant subdomain '{payload.subdomain}' is already taken.",
        )

    existing_name = db.query(Tenant).filter(
        Tenant.name == payload.name.strip()
    ).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant name '{payload.name}' already exists.",
        )

    tenant_data = payload.model_dump()
    tenant = Tenant(
        name=tenant_data["name"].strip(),
        subdomain=tenant_data["subdomain"].lower().strip(),
        timezone=tenant_data.get("timezone", "UTC"),
        country=tenant_data.get("country"),
        email=tenant_data.get("email"),
        phone=tenant_data.get("phone"),
        website=tenant_data.get("website"),
        public_address_visibility=tenant_data.get("public_address_visibility", "visible"),
        max_advance_days=tenant_data.get("max_advance_days", 60),
        address=tenant_data.get("address"),
        latitude=tenant_data.get("latitude"),
        longitude=tenant_data.get("longitude"),
        logo_url=tenant_data.get("logo_url"),
        allow_in_call=tenant_data.get("allow_in_call", True),
        allow_out_call=tenant_data.get("allow_out_call", True),
        travel_charge_origin=(
            tenant_data["travel_charge_origin"].value
            if hasattr(tenant_data.get("travel_charge_origin"), "value")
            else str(tenant_data.get("travel_charge_origin", "ALWAYS_FROM_BASE"))
        ),
        subscription_tier=tenant_data.get("subscription_tier", "starter"),
        chatwoot_account_id=tenant_data.get("chatwoot_account_id"),
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    # Lifecycle Hook: Auto-provision Chatwoot if configured
    if getattr(settings, "CHATWOOT_AUTO_PROVISION", False):
        try:
            from ...services.sms.chatwoot_provisioning_service import provision_tenant_chatwoot

            provision_result = provision_tenant_chatwoot(db=db, tenant_id=tenant.id)
            if not provision_result.success:
                logger.warning(
                    f"Chatwoot auto-provisioning pending/failed for tenant {tenant.id} ({tenant.subdomain}): {provision_result.error_message}"
                )
            else:
                logger.info(
                    f"Chatwoot successfully auto-provisioned for tenant {tenant.id}: account_id={provision_result.chatwoot_account_id}"
                )
        except Exception as e:
            logger.warning(
                f"Fail-safe: Chatwoot auto-provisioning encountered an exception for tenant {tenant.id}: {e}"
            )

    return TenantResponse(ok=True, data=tenant)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve tenant details by ID."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return TenantResponse(ok=True, data=tenant)
