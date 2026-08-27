from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, ForeignKey, Text, String
from sqlalchemy.orm import relationship
from ..db.database import Base

class SmsInboundReceipt(Base):
    __tablename__ = "sms_inbound_receipts"

    id = Column(Integer, primary_key=True, index=True)
    sms_account_id = Column(Integer, ForeignKey("sms_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    event_key = Column(String, unique=True, index=True, nullable=False)  # Provider message ID or generated hash
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    sms_account = relationship("SmsAccount")

    def __repr__(self) -> str:
        return f"<SmsInboundReceipt id={self.id} event_key={self.event_key}>"


class SmsDeliveryReceipt(Base):
    __tablename__ = "sms_delivery_receipts"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("sms_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    message = relationship("SmsMessage")

    def __repr__(self) -> str:
        return f"<SmsDeliveryReceipt id={self.id} message_id={self.message_id} status={self.status}>"
