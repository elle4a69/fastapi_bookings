"""Webhook registration model.

Stores outbound webhook subscriptions.  When a booking event fires,
the outbox worker dispatches an HTTP POST to each active webhook
matching that event type.  The optional secret is used to sign the
payload via HMAC-SHA256 so the receiver can verify authenticity.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.database import Base


class WebhookRegistration(Base):
    """Registered outbound webhook endpoint."""

    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    event = Column(String, nullable=False, index=True)   # e.g. "booking.created"
    target_url = Column(String, nullable=False)
    secret = Column(String, nullable=True)               # HMAC-SHA256 signing secret
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<WebhookRegistration id={self.id} event={self.event}>"
