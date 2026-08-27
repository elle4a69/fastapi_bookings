"""Mock payment routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, get_current_tenant
from ...core.pagination import paginate_query, pagination_params
from ...models.payment import Payment as PaymentModel
from ...models.tenant import Tenant
from ...schemas.payment import (
    Payment,
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentUpdate,
)


router = APIRouter()


@router.get("/payments", response_model=PaymentListResponse, tags=["payments"])
def list_payments(
    params: dict = Depends(pagination_params),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of payments."""
    query = db.query(PaymentModel).filter(PaymentModel.tenant_id == tenant.id)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/payments", response_model=PaymentResponse, tags=["payments"])
def create_payment(
    payment_in: PaymentCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a payment record."""
    if payment_in.amount < 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount must be at least 0.01"
        )
    payment_dict = payment_in.dict()
    payment_dict["tenant_id"] = tenant.id
    payment = PaymentModel(**payment_dict)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {"ok": True, "data": payment}


@router.put("/payments/{payment_id}", response_model=PaymentResponse, tags=["payments"])
def update_payment(
    payment_id: int,
    payment_in: PaymentUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update a payment's status."""
    payment = db.query(PaymentModel).filter(
        PaymentModel.id == payment_id,
        PaymentModel.tenant_id == tenant.id
    ).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    for field, value in payment_in.dict(exclude_unset=True).items():
        setattr(payment, field, value)
    db.commit()
    db.refresh(payment)
    return {"ok": True, "data": payment}