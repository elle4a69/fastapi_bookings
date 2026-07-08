"""Commercial checkout models.

Provides a local commercial checkout shell: invoices, invoice lines,
promotion codes, tax rates, tips and payment processor configuration.

These models are intentionally local and provider-neutral.  They do not
integrate with external gateways yet; they give the front end and later
gateway integrations a stable database contract.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Numeric, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.database import Base


class Invoice(Base):
    """Invoice header.

    An invoice can be attached to a booking and/or client.
    """

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)

    currency = Column(String, default="USD", nullable=False)
    subtotal = Column(Numeric(10, 2), default=0.0, nullable=False)
    discount_total = Column(Numeric(10, 2), default=0.0, nullable=False)
    tax_total = Column(Numeric(10, 2), default=0.0, nullable=False)
    tip_total = Column(Numeric(10, 2), default=0.0, nullable=False)
    total = Column(Numeric(10, 2), default=0.0, nullable=False)
    amount_paid = Column(Numeric(10, 2), default=0.0, nullable=False)

    status = Column(String, default="draft", nullable=False)
    promotion_code = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    booking = relationship("Booking")
    client = relationship("Client")
    tenant = relationship("Tenant")
    lines = relationship(
        "InvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    tips = relationship(
        "Tip",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )


class InvoiceLine(Base):
    """Line item for services, add-ons, products, packages, discounts or taxes."""

    __tablename__ = "invoice_lines"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    line_type = Column(String, nullable=False)
    item_id = Column(Integer, nullable=True)
    description = Column(String, nullable=False)

    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Numeric(10, 2), default=0.0, nullable=False)
    amount = Column(Numeric(10, 2), default=0.0, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    invoice = relationship("Invoice", back_populates="lines")
    tenant = relationship("Tenant")


class PromotionCode(Base):
    """Promotion/coupon code.

    discount_type supports:
    - fixed: subtract discount_value from the subtotal
    - percent: subtract subtotal * discount_value / 100
    """

    __tablename__ = "promotion_codes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    discount_type = Column(String, default="fixed", nullable=False)
    discount_value = Column(Numeric(10, 2), default=0.0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    max_redemptions = Column(Integer, nullable=True)
    times_redeemed = Column(Integer, default=0, nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_promotion_codes_tenant_code"),
    )


class TaxRate(Base):
    """Tax rate applied to invoice subtotals."""

    __tablename__ = "tax_rates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    rate_percent = Column(Numeric(10, 2), default=0.0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")


class Tip(Base):
    """Tip/gratuity attached to an invoice."""

    __tablename__ = "tips"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    invoice = relationship("Invoice", back_populates="tips")
    tenant = relationship("Tenant")


class PaymentProcessorConfig(Base):
    """Local payment processor configuration shell.

    Stores public/non-secret processor configuration only.  Do not store
    private gateway secrets here without a proper secret manager.
    """

    __tablename__ = "payment_processor_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String, nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    display_name = Column(String, nullable=True)
    public_key = Column(String, nullable=True)
    config_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")
