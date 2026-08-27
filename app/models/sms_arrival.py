from datetime import datetime, timezone
import secrets
from sqlalchemy import Column, DateTime, Integer, ForeignKey, String
from sqlalchemy.orm import relationship
from ..db.database import Base

class SmsArrivalSession(Base):
    __tablename__ = "sms_arrival_sessions"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    conversation_id = Column(Integer, ForeignKey("sms_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String, unique=True, index=True, default=lambda: secrets.token_urlsafe(32), nullable=False)
    arrived_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    booking = relationship("Booking")
    conversation = relationship("SmsConversation")

    def __repr__(self) -> str:
        return f"<SmsArrivalSession id={self.id} booking_id={self.booking_id} arrived_at={self.arrived_at}>"
