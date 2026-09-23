"""Internal replay authority for idempotent booking commands."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..db.database import Base


class BookingCommandReceipt(Base):
    """Bind one tenant-scoped idempotency key to one exact booking command."""

    __tablename__ = "booking_command_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "booking_id"],
            ["bookings.tenant_id", "bookings.id"],
            name="fk_booking_command_receipts_tenant_booking",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_booking_command_receipts_tenant_key",
        ),
        UniqueConstraint(
            "booking_id",
            name="uq_booking_command_receipts_booking_id",
        ),
        CheckConstraint(
            "fingerprint_version >= 1",
            name="ck_booking_command_receipts_version",
        ),
        CheckConstraint(
            "length(request_hmac) = 64",
            name="ck_booking_command_receipts_hmac_length",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    booking_id = Column(Integer, nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    fingerprint_version = Column(Integer, nullable=False)
    request_hmac = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    booking = relationship("Booking", back_populates="command_receipt")

    def __repr__(self) -> str:
        return f"<BookingCommandReceipt id={self.id} booking_id={self.booking_id}>"
