"""Business Profile API router.

Exposes endpoints for admins to read and update the business profile,
and a public endpoint for the portal bootstrap.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_public_tenant, get_current_tenant, get_current_admin
from ...models.tenant import Tenant
from ...models.user import User
from ...schemas.business_profile import (
    BusinessProfileUpdate,
    BusinessProfileResponse,
    PublicBusinessProfileResponse,
)
from ...services.geocoding import geocode_tenant_address

router = APIRouter()


@router.get("/api/admin/business-profile", response_model=BusinessProfileResponse, tags=["business-profile"])
def get_business_profile(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Retrieve details of the active tenant business profile (admin endpoint)."""
    return {"ok": True, "data": tenant}


@router.put("/api/admin/business-profile", response_model=BusinessProfileResponse, tags=["business-profile"])
async def update_business_profile(
    payload: BusinessProfileUpdate,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Update details of the active tenant business profile (admin endpoint)."""
    update_data = payload.dict(exclude_unset=True)
    for required_field in ("name", "timezone", "public_address_visibility", "max_advance_days"):
        if update_data.get(required_field) is None:
            update_data.pop(required_field, None)

    if "name" in update_data:
        # Prevent name collisions
        existing = db.query(Tenant).filter(Tenant.name == update_data["name"], Tenant.id != tenant.id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A tenant with this name already exists.")
        tenant.name = update_data["name"]

    # Track whether the address has changed so we can re-geocode it
    new_address = update_data.get("address")
    address_changed = new_address is not None and new_address != tenant.address

    for field, value in update_data.items():
        if field != "name":
            setattr(tenant, field, value)

    db.commit()
    db.refresh(tenant)

    # Trigger geocoding in background if address was updated
    if address_changed and new_address:
        background_tasks.add_task(geocode_tenant_address, tenant.id, new_address)

    return {"ok": True, "data": tenant}


@router.get("/api/public/business-profile", response_model=PublicBusinessProfileResponse, tags=["business-profile"])
def get_public_business_profile(
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Retrieve public subset of the business profile for the portal."""
    return {"ok": True, "data": tenant}
