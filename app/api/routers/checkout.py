"""Commercial checkout routes.

Provides a local checkout shell for quotes, invoices, promotion codes,
taxes, tips and payment processor configuration.  This is not an
external payment gateway integration — it provides the database and API
contract for the front end and later gateway integrations such as
Stripe, Square or manual payment.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models import (
    AddOn,
    Booking,
    Invoice,
    InvoiceLine,
    PaymentProcessorConfig,
    Product,
    PromotionCode,
    ServicePackage,
    TaxRate,
    Tip,
)
from ...schemas.checkout import (
    InvoiceCreate,
    InvoiceListResponse,
    InvoiceOut,
    InvoiceResponse,
    InvoiceStatusUpdate,
    PaymentProcessorConfigCreate,
    PaymentProcessorConfigOut,
    PaymentProcessorConfigUpdate,
    PromotionCodeCreate,
    PromotionCodeOut,
    PromotionCodeUpdate,
    PromotionValidationResponse,
    QuoteRequest,
    QuoteResponse,
    TaxRateCreate,
    TaxRateOut,
    TaxRateUpdate,
    TipCreate,
    TipOut,
)
from ...models.service import Service

router = APIRouter(tags=["checkout"])


def now_utc() -> datetime:
    return datetime.utcnow()


def validate_promotion(db: Session, code: Optional[str], subtotal: float) -> dict:
    if not code:
        return {"valid": False, "discount": 0.0, "reason": "No promotion code supplied"}
    promo = db.query(PromotionCode).filter(PromotionCode.code == code).first()
    if not promo:
        return {"valid": False, "discount": 0.0, "reason": "Promotion code not found"}
    if not promo.active:
        return {"valid": False, "discount": 0.0, "reason": "Promotion code is inactive"}
    now = now_utc()
    if promo.starts_at and promo.starts_at > now:
        return {"valid": False, "discount": 0.0, "reason": "Promotion code is not active yet"}
    if promo.expires_at and promo.expires_at < now:
        return {"valid": False, "discount": 0.0, "reason": "Promotion code has expired"}
    if promo.max_redemptions is not None and promo.times_redeemed >= promo.max_redemptions:
        return {"valid": False, "discount": 0.0, "reason": "Promotion code has reached its redemption limit"}
    discount = (subtotal * promo.discount_value / 100.0) if promo.discount_type == "percent" else promo.discount_value
    discount = max(0.0, min(float(discount), float(subtotal)))
    return {"valid": True, "discount": round(discount, 2), "reason": None, "promotion": PromotionCodeOut.from_orm(promo)}


def build_quote(db: Session, payload: QuoteRequest) -> dict:
    lines: list[dict] = []
    subtotal = 0.0

    service = None
    if payload.booking_id:
        booking = db.query(Booking).filter(Booking.id == payload.booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        service = booking.service
        if payload.client_id is None:
            payload.client_id = booking.client_id
    elif payload.service_id:
        service = db.query(Service).filter(Service.id == payload.service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")

    if service:
        amount = float(service.price or 0.0)
        lines.append({"line_type": "service", "item_id": service.id, "description": service.name, "quantity": 1, "unit_price": amount, "amount": amount})
        subtotal += amount

    for add_on_id in payload.add_on_ids:
        add_on = db.query(AddOn).filter(AddOn.id == add_on_id, AddOn.active.is_(True)).first()
        if not add_on:
            raise HTTPException(status_code=404, detail=f"Add-on {add_on_id} not found")
        amount = float(add_on.price or 0.0)
        lines.append({"line_type": "add_on", "item_id": add_on.id, "description": add_on.name, "quantity": 1, "unit_price": amount, "amount": amount})
        subtotal += amount

    for product_id in payload.product_ids:
        product = db.query(Product).filter(Product.id == product_id, Product.active.is_(True)).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        amount = float(product.price or 0.0)
        lines.append({"line_type": "product", "item_id": product.id, "description": product.name, "quantity": 1, "unit_price": amount, "amount": amount})
        subtotal += amount

    if payload.package_id:
        package = db.query(ServicePackage).filter(ServicePackage.id == payload.package_id, ServicePackage.active.is_(True)).first()
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")
        amount = float(package.price) if package.price is not None else sum(float(step.price or 0.0) for step in package.steps if step.active)
        lines.append({"line_type": "package", "item_id": package.id, "description": package.name, "quantity": 1, "unit_price": amount, "amount": amount})
        subtotal += amount

    promo_result = validate_promotion(db, payload.promotion_code, subtotal)
    discount = float(promo_result.get("discount") or 0.0)
    if promo_result.get("valid") and discount:
        lines.append({"line_type": "discount", "item_id": None, "description": f"Promotion {payload.promotion_code}", "quantity": 1, "unit_price": -discount, "amount": -discount})

    taxable = max(0.0, subtotal - discount)
    tax_total = 0.0
    for tax in db.query(TaxRate).filter(TaxRate.active.is_(True)).all():
        tax_amount = round(taxable * float(tax.rate_percent or 0.0) / 100.0, 2)
        if tax_amount:
            lines.append({"line_type": "tax", "item_id": tax.id, "description": tax.name, "quantity": 1, "unit_price": tax_amount, "amount": tax_amount})
            tax_total += tax_amount

    tip_total = round(max(0.0, float(payload.tip_amount or 0.0)), 2)
    if tip_total:
        lines.append({"line_type": "tip", "item_id": None, "description": "Tip", "quantity": 1, "unit_price": tip_total, "amount": tip_total})

    return {
        "currency": payload.currency,
        "booking_id": payload.booking_id,
        "client_id": payload.client_id,
        "lines": lines,
        "subtotal": round(subtotal, 2),
        "discount_total": round(discount, 2),
        "tax_total": round(tax_total, 2),
        "tip_total": tip_total,
        "total": round(max(0.0, taxable + tax_total + tip_total), 2),
        "promotion": promo_result,
    }


@router.post("/api/public/quote", response_model=QuoteResponse)
def create_quote(payload: QuoteRequest, db: Session = Depends(get_db)) -> dict:
    """Calculate a quote before creating an invoice."""
    return {"ok": True, "data": build_quote(db, payload)}


@router.get("/api/public/payment-processor/config")
def public_payment_processor_config(db: Session = Depends(get_db)) -> dict:
    configs = db.query(PaymentProcessorConfig).filter(PaymentProcessorConfig.enabled.is_(True)).all()
    return {"ok": True, "data": [{"provider": c.provider, "display_name": c.display_name, "public_key": c.public_key} for c in configs]}


@router.get("/api/public/payment-methods")
def public_payment_methods(db: Session = Depends(get_db)) -> dict:
    configs = db.query(PaymentProcessorConfig).filter(PaymentProcessorConfig.enabled.is_(True)).all()
    return {"ok": True, "data": [{"provider": c.provider, "display_name": c.display_name or c.provider} for c in configs]}


@router.get("/api/public/promotions/{code}/validate", response_model=PromotionValidationResponse)
def public_validate_promotion(code: str, subtotal: float = 0.0, db: Session = Depends(get_db)) -> dict:
    return {"ok": True, "data": validate_promotion(db, code, subtotal)}


@router.post("/api/public/invoices", response_model=InvoiceResponse)
def create_public_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)) -> dict:
    quote = build_quote(db, payload.quote)
    invoice = Invoice(
        booking_id=payload.booking_id or quote.get("booking_id"),
        client_id=payload.client_id or quote.get("client_id"),
        currency=quote["currency"],
        subtotal=quote["subtotal"],
        discount_total=quote["discount_total"],
        tax_total=quote["tax_total"],
        tip_total=quote["tip_total"],
        total=quote["total"],
        amount_paid=0.0,
        status=payload.status,
        promotion_code=payload.quote.promotion_code,
        notes=payload.notes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    for line in quote["lines"]:
        db.add(InvoiceLine(invoice_id=invoice.id, line_type=line["line_type"], item_id=line.get("item_id"), description=line["description"], quantity=line["quantity"], unit_price=line["unit_price"], amount=line["amount"]))
    if payload.quote.promotion_code and quote["promotion"].get("valid"):
        promo = db.query(PromotionCode).filter(PromotionCode.code == payload.quote.promotion_code).first()
        if promo:
            promo.times_redeemed += 1
    db.commit()
    db.refresh(invoice)
    return {"ok": True, "data": invoice}


@router.get("/api/public/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_public_invoice(invoice_id: int, db: Session = Depends(get_db)) -> dict:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"ok": True, "data": invoice}


@router.post("/api/public/invoices/{invoice_id}/tips", response_model=TipOut)
def add_public_tip(invoice_id: int, payload: TipCreate, db: Session = Depends(get_db)) -> Tip:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    tip = Tip(invoice_id=invoice.id, amount=payload.amount, note=payload.note)
    invoice.tip_total += float(payload.amount)
    invoice.total += float(payload.amount)
    invoice.updated_at = now_utc()
    db.add(tip)
    db.commit()
    db.refresh(tip)
    return tip


@router.get("/api/admin/invoices", response_model=InvoiceListResponse)
def list_admin_invoices(db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> dict:
    invoices = db.query(Invoice).all()
    return {"ok": True, "data": invoices, "meta": {"count": len(invoices)}}


@router.get("/api/admin/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_admin_invoice(invoice_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> dict:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"ok": True, "data": invoice}


@router.put("/api/admin/invoices/{invoice_id}/status", response_model=InvoiceResponse)
def update_invoice_status(invoice_id: int, payload: InvoiceStatusUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> dict:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = payload.status
    if payload.amount_paid is not None:
        invoice.amount_paid = payload.amount_paid
    invoice.updated_at = now_utc()
    db.commit()
    db.refresh(invoice)
    return {"ok": True, "data": invoice}


@router.get("/api/admin/promotions", response_model=list[PromotionCodeOut])
def list_promotions(db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> list:
    return db.query(PromotionCode).all()


@router.post("/api/admin/promotions", response_model=PromotionCodeOut, status_code=status.HTTP_201_CREATED)
def create_promotion(payload: PromotionCodeCreate, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> PromotionCode:
    if db.query(PromotionCode).filter(PromotionCode.code == payload.code).first():
        raise HTTPException(status_code=409, detail="Promotion code already exists")
    promo = PromotionCode(**payload.dict())
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo


@router.put("/api/admin/promotions/{promotion_id}", response_model=PromotionCodeOut)
def update_promotion(promotion_id: int, payload: PromotionCodeUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> PromotionCode:
    promo = db.query(PromotionCode).filter(PromotionCode.id == promotion_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(promo, field, value)
    db.commit()
    db.refresh(promo)
    return promo


@router.delete("/api/admin/promotions/{promotion_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_promotion(promotion_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> None:
    promo = db.query(PromotionCode).filter(PromotionCode.id == promotion_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    db.delete(promo)
    db.commit()


@router.get("/api/admin/tax-rates", response_model=list[TaxRateOut])
def list_tax_rates(db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> list:
    return db.query(TaxRate).all()


@router.post("/api/admin/tax-rates", response_model=TaxRateOut, status_code=status.HTTP_201_CREATED)
def create_tax_rate(payload: TaxRateCreate, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> TaxRate:
    tax = TaxRate(**payload.dict())
    db.add(tax)
    db.commit()
    db.refresh(tax)
    return tax


@router.put("/api/admin/tax-rates/{tax_rate_id}", response_model=TaxRateOut)
def update_tax_rate(tax_rate_id: int, payload: TaxRateUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> TaxRate:
    tax = db.query(TaxRate).filter(TaxRate.id == tax_rate_id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax rate not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(tax, field, value)
    db.commit()
    db.refresh(tax)
    return tax


@router.delete("/api/admin/tax-rates/{tax_rate_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_tax_rate(tax_rate_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> None:
    tax = db.query(TaxRate).filter(TaxRate.id == tax_rate_id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax rate not found")
    db.delete(tax)
    db.commit()


@router.get("/api/admin/payment-processor/configs", response_model=list[PaymentProcessorConfigOut])
def list_payment_processor_configs(db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> list:
    return db.query(PaymentProcessorConfig).all()


@router.post("/api/admin/payment-processor/configs", response_model=PaymentProcessorConfigOut, status_code=status.HTTP_201_CREATED)
def create_payment_processor_config(payload: PaymentProcessorConfigCreate, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> PaymentProcessorConfig:
    config = PaymentProcessorConfig(**payload.dict())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.put("/api/admin/payment-processor/configs/{config_id}", response_model=PaymentProcessorConfigOut)
def update_payment_processor_config(config_id: int, payload: PaymentProcessorConfigUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> PaymentProcessorConfig:
    config = db.query(PaymentProcessorConfig).filter(PaymentProcessorConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Payment processor config not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(config, field, value)
    config.updated_at = now_utc()
    db.commit()
    db.refresh(config)
    return config
