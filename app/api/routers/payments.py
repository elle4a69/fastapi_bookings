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


@router.post("/payments/{payment_id}/refund", response_model=PaymentResponse, tags=["payments"])
def refund_payment(
    payment_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Refund a payment."""
    payment = db.query(PaymentModel).filter(
        PaymentModel.id == payment_id,
        PaymentModel.tenant_id == tenant.id
    ).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    payment.status = "refunded"
    db.commit()
    db.refresh(payment)
    return {"ok": True, "data": payment}


from pydantic import BaseModel
from typing import Dict, Any, Optional

class ProcessorConfigSchema(BaseModel):
    enabled: bool
    public_key: Optional[str] = None
    secret_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    instructions: Optional[str] = None

class ProcessorsDataSchema(BaseModel):
    currency: str
    processors: Dict[str, ProcessorConfigSchema]


@router.get("/finance/processors", response_model=ProcessorsDataSchema, tags=["payments"])
def get_finance_processors(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    from ...models.checkout import PaymentProcessorConfig
    import json

    configs = db.query(PaymentProcessorConfig).filter(PaymentProcessorConfig.tenant_id == tenant.id).all()
    config_map = {c.provider: c for c in configs}

    stripe_cfg = config_map.get("stripe")
    paypal_cfg = config_map.get("paypal")
    offline_cfg = config_map.get("offline")

    stripe_data = {"enabled": False, "public_key": "", "secret_key": ""}
    paypal_data = {"enabled": False, "client_id": "", "client_secret": ""}
    offline_data = {"enabled": True, "instructions": ""}

    if stripe_cfg:
        stripe_data["enabled"] = stripe_cfg.enabled
        stripe_data["public_key"] = stripe_cfg.public_key or ""
        try:
            cj = json.loads(stripe_cfg.config_json or "{}")
            stripe_data["secret_key"] = cj.get("secret_key", "")
        except Exception:
            pass

    if paypal_cfg:
        paypal_data["enabled"] = paypal_cfg.enabled
        try:
            cj = json.loads(paypal_cfg.config_json or "{}")
            paypal_data["client_id"] = cj.get("client_id", "")
            paypal_data["client_secret"] = cj.get("client_secret", "")
        except Exception:
            pass

    if offline_cfg:
        offline_data["enabled"] = offline_cfg.enabled
        try:
            cj = json.loads(offline_cfg.config_json or "{}")
            offline_data["instructions"] = cj.get("instructions", "")
        except Exception:
            pass

    return {
        "currency": "USD",
        "processors": {
            "stripe": stripe_data,
            "paypal": paypal_data,
            "offline": offline_data
        }
    }


@router.put("/finance/processors", response_model=ProcessorsDataSchema, tags=["payments"])
def save_finance_processors(
    payload: ProcessorsDataSchema,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    from ...models.checkout import PaymentProcessorConfig
    import json

    for provider, data in payload.processors.items():
        config = db.query(PaymentProcessorConfig).filter(
            PaymentProcessorConfig.tenant_id == tenant.id,
            PaymentProcessorConfig.provider == provider
        ).first()

        if not config:
            config = PaymentProcessorConfig(
                tenant_id=tenant.id,
                provider=provider
            )
            db.add(config)

        config.enabled = data.enabled
        
        cj = {}
        if provider == "stripe":
            config.public_key = data.public_key
            cj["secret_key"] = data.secret_key or ""
        elif provider == "paypal":
            cj["client_id"] = data.client_id or ""
            cj["client_secret"] = data.client_secret or ""
        elif provider == "offline":
            cj["instructions"] = data.instructions or ""

        config.config_json = json.dumps(cj)
        
    db.commit()
    return get_finance_processors(tenant=tenant, db=db, current_user=current_user)