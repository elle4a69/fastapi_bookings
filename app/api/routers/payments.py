"""Mock payment routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...core.pagination import paginate_query, pagination_params
from ...models.payment import Payment as PaymentModel
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
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of payments."""
    query = db.query(PaymentModel)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/payments", response_model=PaymentResponse, tags=["payments"])
def create_payment(
    payment_in: PaymentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a payment record."""
    payment = PaymentModel(**payment_in.dict())
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {"ok": True, "data": payment}


@router.put("/payments/{payment_id}", response_model=PaymentResponse, tags=["payments"])
def update_payment(
    payment_id: int,
    payment_in: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update a payment's status."""
    payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    for field, value in payment_in.dict(exclude_unset=True).items():
        setattr(payment, field, value)
    db.commit()
    db.refresh(payment)
    return {"ok": True, "data": payment}