"""Provider CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, get_current_tenant
from ...core.pagination import paginate_query, pagination_params
from ...models.provider import Provider as ProviderModel
from ...models.tenant import Tenant
from ...schemas.provider import (
    ProviderCreate,
    ProviderListResponse,
    ProviderResponse,
    ProviderUpdate,
)


router = APIRouter()


@router.get("/providers", response_model=ProviderListResponse, tags=["providers"])
def list_providers(
    params: dict = Depends(pagination_params),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """Return a paginated list of providers."""
    query = db.query(ProviderModel).filter(ProviderModel.tenant_id == tenant.id)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/providers", response_model=ProviderResponse, tags=["providers"])
def create_provider(
    provider_in: ProviderCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new provider."""
    provider_dict = provider_in.dict()
    provider_dict["tenant_id"] = tenant.id
    provider = ProviderModel(**provider_dict)
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return {"ok": True, "data": provider}


@router.get("/providers/{provider_id}", response_model=ProviderResponse, tags=["providers"])
def get_provider(
    provider_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> dict:
    """Retrieve a single provider by ID."""
    provider = db.query(ProviderModel).filter(
        ProviderModel.id == provider_id,
        ProviderModel.tenant_id == tenant.id
    ).first()
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return {"ok": True, "data": provider}


@router.put("/providers/{provider_id}", response_model=ProviderResponse, tags=["providers"])
def update_provider(
    provider_id: int,
    provider_in: ProviderUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update an existing provider."""
    provider = db.query(ProviderModel).filter(
        ProviderModel.id == provider_id,
        ProviderModel.tenant_id == tenant.id
    ).first()
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    for field, value in provider_in.dict(exclude_unset=True).items():
        setattr(provider, field, value)
    db.commit()
    db.refresh(provider)
    return {"ok": True, "data": provider}


@router.delete("/providers/{provider_id}", response_model=ProviderResponse, tags=["providers"])
def delete_provider(
    provider_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a provider."""
    provider = db.query(ProviderModel).filter(
        ProviderModel.id == provider_id,
        ProviderModel.tenant_id == tenant.id
    ).first()
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    db.delete(provider)
    db.commit()
    return {"ok": True, "data": provider}