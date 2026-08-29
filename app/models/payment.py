"""Payment model.

Represents a payment associated with a booking. The payment status
tracks whether a payment is pending, completed, failed, or refunded.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, nullable=False, default="USD")
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    booking = relationship("Booking")
    tenant = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<Payment id={self.id} amount={self.amount} status={self.status}>"