"""Service relation management routes.

CRUD endpoints for managing many-to-many relationships between services
and providers, and services and categories.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models import (
    Category as CategoryModel,
    Provider as ProviderModel,
    Service as ServiceModel,
    ServiceCategory,
    ServiceProvider,
)
from ...schemas.category import CategoryOut
from ...schemas.provider import Provider as ProviderSchema

router = APIRouter(prefix="/services", tags=["service-relations"])


def get_service_or_404(db: Session, service_id: int) -> ServiceModel:
    service = db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


@router.get("/{service_id}/providers", response_model=list[ProviderSchema])
def list_service_providers(service_id: int, db: Session = Depends(get_db)) -> list[ProviderSchema]:
    """List all providers assigned to a service."""
    service = get_service_or_404(db, service_id)
    return [sp.provider for sp in service.providers]


@router.post("/{service_id}/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def assign_provider_to_service(
    service_id: int,
    provider_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> None:
    """Assign a provider to a service."""
    service = get_service_or_404(db, service_id)
    provider = db.query(ProviderModel).filter(ProviderModel.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    existing = db.query(ServiceProvider).filter(
        ServiceProvider.service_id == service.id,
        ServiceProvider.provider_id == provider.id,
    ).first()
    if not existing:
        db.add(ServiceProvider(service_id=service.id, provider_id=provider.id))
        db.commit()


@router.delete("/{service_id}/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def unassign_provider_from_service(
    service_id: int,
    provider_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> None:
    """Remove a provider assignment from a service."""
    assignment = db.query(ServiceProvider).filter(
        ServiceProvider.service_id == service_id,
        ServiceProvider.provider_id == provider_id,
    ).first()
    if assignment:
        db.delete(assignment)
        db.commit()


@router.get("/{service_id}/categories", response_model=list[CategoryOut])
def list_service_categories(service_id: int, db: Session = Depends(get_db)) -> list[CategoryOut]:
    """List all categories assigned to a service."""
    service = get_service_or_404(db, service_id)
    return [sc.category for sc in service.categories]


@router.post("/{service_id}/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def assign_category_to_service(
    service_id: int,
    category_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> None:
    """Assign a category to a service."""
    service = get_service_or_404(db, service_id)
    category = db.query(CategoryModel).filter(CategoryModel.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    existing = db.query(ServiceCategory).filter(
        ServiceCategory.service_id == service.id,
        ServiceCategory.category_id == category.id,
    ).first()
    if not existing:
        db.add(ServiceCategory(service_id=service.id, category_id=category.id))
        db.commit()


@router.delete("/{service_id}/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def unassign_category_from_service(
    service_id: int,
    category_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> None:
    """Remove a category assignment from a service."""
    assignment = db.query(ServiceCategory).filter(
        ServiceCategory.service_id == service_id,
        ServiceCategory.category_id == category_id,
    ).first()
    if assignment:
        db.delete(assignment)
        db.commit()
