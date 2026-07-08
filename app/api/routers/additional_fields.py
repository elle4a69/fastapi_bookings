"""Additional/intake field routes.

Configurable fields that appear on the public booking form, client
registration form, or admin-only forms.  Supports SimplyBook-style
per-service intake forms without hard-coding questions in the front end.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, get_public_tenant
from ...models import AdditionalField, AdditionalFieldResponse, Service, Tenant
from ...schemas.additional_field import (
    AdditionalFieldCreate,
    AdditionalFieldOut,
    AdditionalFieldResponseCreate,
    AdditionalFieldResponseOut,
    AdditionalFieldSubmitRequest,
    AdditionalFieldUpdate,
)

router = APIRouter(tags=["additional-fields"])


def field_query(
    db: Session,
    tenant_id: int,
    *,
    scope: Optional[str] = None,
    service_id: Optional[int] = None,
    active_only: bool = True,
):
    query = db.query(AdditionalField).filter(AdditionalField.tenant_id == tenant_id)
    if scope:
        query = query.filter(AdditionalField.scope == scope)
    if service_id is not None:
        query = query.filter(
            (AdditionalField.service_id == service_id) | (AdditionalField.service_id.is_(None))
        )
    if active_only:
        query = query.filter(AdditionalField.active.is_(True))
    return query.order_by(AdditionalField.position.asc(), AdditionalField.id.asc())


@router.get("/api/public/additional-fields", response_model=list[AdditionalFieldOut])
def list_public_additional_fields(
    scope: Optional[str] = Query(None),
    service_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> list:
    """Return active fields for public forms."""
    if service_id is not None:
        if not db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant.id).first():
            raise HTTPException(status_code=404, detail="Service not found")
    return field_query(db, tenant_id=tenant.id, scope=scope, service_id=service_id, active_only=True).all()


@router.get("/api/public/services/{service_id}/intake-form", response_model=list[AdditionalFieldOut])
def get_public_service_intake_form(
    service_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> list:
    """Return booking + service-specific intake fields for a service."""
    if not db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant.id).first():
        raise HTTPException(status_code=404, detail="Service not found")
    generic = field_query(db, tenant_id=tenant.id, scope="booking", service_id=None, active_only=True).all()
    service_fields = field_query(db, tenant_id=tenant.id, scope="service", service_id=service_id, active_only=True).all()
    return generic + service_fields


@router.post("/api/public/additional-field-responses", response_model=list[AdditionalFieldResponseOut])
def submit_public_additional_field_responses(
    payload: AdditionalFieldSubmitRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> list:
    """Submit additional/intake field responses."""
    saved = []
    for response in payload.responses:
        field = db.query(AdditionalField).filter(
            AdditionalField.id == response.field_id,
            AdditionalField.tenant_id == tenant.id,
            AdditionalField.active.is_(True),
        ).first()
        if not field:
            raise HTTPException(status_code=404, detail=f"Additional field {response.field_id} not found")
        row = AdditionalFieldResponse(
            field_id=response.field_id,
            client_id=response.client_id or payload.client_id,
            booking_id=response.booking_id or payload.booking_id,
            value=response.value,
        )
        db.add(row)
        saved.append(row)
    db.commit()
    for row in saved:
        db.refresh(row)
    return saved


@router.get("/api/admin/additional-fields", response_model=list[AdditionalFieldOut])
def list_admin_additional_fields(
    scope: Optional[str] = Query(None),
    service_id: Optional[int] = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> list:
    return field_query(db, tenant_id=current_user.tenant_id, scope=scope, service_id=service_id, active_only=active_only).all()


@router.post("/api/admin/additional-fields", response_model=AdditionalFieldOut, status_code=status.HTTP_201_CREATED)
def create_additional_field(
    field_in: AdditionalFieldCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> AdditionalField:
    field = AdditionalField(**field_in.dict(), tenant_id=current_user.tenant_id)
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


@router.put("/api/admin/additional-fields/{field_id}", response_model=AdditionalFieldOut)
def update_additional_field(
    field_id: int,
    field_in: AdditionalFieldUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> AdditionalField:
    field = db.query(AdditionalField).filter(AdditionalField.id == field_id, AdditionalField.tenant_id == current_user.tenant_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Additional field not found")
    for k, v in field_in.dict(exclude_unset=True).items():
        setattr(field, k, v)
    db.commit()
    db.refresh(field)
    return field


@router.delete("/api/admin/additional-fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_additional_field(
    field_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> None:
    field = db.query(AdditionalField).filter(AdditionalField.id == field_id, AdditionalField.tenant_id == current_user.tenant_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Additional field not found")
    db.delete(field)
    db.commit()


@router.get("/api/admin/additional-field-responses", response_model=list[AdditionalFieldResponseOut])
def list_admin_field_responses(
    booking_id: Optional[int] = Query(None),
    client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> list:
    q = db.query(AdditionalFieldResponse).join(AdditionalField)
    q = q.filter(AdditionalField.tenant_id == current_user.tenant_id)
    if booking_id is not None:
        q = q.filter(AdditionalFieldResponse.booking_id == booking_id)
    if client_id is not None:
        q = q.filter(AdditionalFieldResponse.client_id == client_id)
    return q.all()
