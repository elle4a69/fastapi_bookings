"""Webhook registration model.

Stores outbound webhook subscriptions.  When a booking event fires,
the outbox worker dispatches an HTTP POST to each active webhook
matching that event type.  The optional secret is used to sign the
payload via HMAC-SHA256 so the receiver can verify authenticity.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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

    @property
    def has_secret(self) -> bool:
        return bool(self.secret)

    @property
    def secret_last4(self) -> str | None:
        if not self.secret:
            return None
        return self.secret[-4:] if len(self.secret) >= 4 else self.secret

    def __repr__(self) -> str:
        return f"<WebhookRegistration id={self.id} event={self.event}>"


class WebhookDelivery(Base):
    """Tracks delivery status of an outbox event to a specific webhook endpoint.

    Ensures idempotency across retries: successful destinations are never resent
    when retrying a failed multi-destination fan-out.
    """

    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    outbox_event_id = Column(Integer, ForeignKey("outbox_events.id", ondelete="CASCADE"), nullable=False, index=True)
    webhook_id = Column(Integer, ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, default="PENDING", nullable=False, index=True)  # SUCCESS, FAILED, PENDING
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=1, nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")
    outbox_event = relationship("OutboxEvent")
    webhook = relationship("WebhookRegistration")

    __table_args__ = (
        UniqueConstraint("outbox_event_id", "webhook_id", name="uq_outbox_event_webhook"),
    )

    def __repr__(self) -> str:
        return f"<WebhookDelivery id={self.id} outbox_event_id={self.outbox_event_id} webhook_id={self.webhook_id} status={self.status}>"

