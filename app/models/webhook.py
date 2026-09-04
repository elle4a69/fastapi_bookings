"""Webhook registration model.

Stores outbound webhook subscriptions.  When a booking event fires,
the outbox worker dispatches an HTTP POST to each active webhook
matching that event type.  The optional secret is used to sign the
payload via HMAC-SHA256 so the receiver can verify authenticity.
"""

from datetime import datetime, timezone
import base64
import hashlib
import hmac

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import relationship

from ..db.database import Base
from ..core.config import settings


_WEBHOOK_DELIVERY_CIPHER_CONTEXT = b"fastapi-bookings:webhook-delivery-snapshot:v1"


def _webhook_delivery_cipher():
    """Return a domain-separated cipher for immutable delivery snapshots.

    Production must never derive this from the development default or a
    missing key.  The context-specific HMAC derivation prevents reusing a
    Fernet key produced for any other application secret field.
    """
    secret = settings.SECRET_KEY
    if settings.APP_ENV == "production" and (not secret or secret == "changeme" or len(secret) < 32):
        raise RuntimeError("A non-default SECRET_KEY is required for webhook delivery snapshots in production")
    key_material = hmac.new(secret.encode("utf-8"), _WEBHOOK_DELIVERY_CIPHER_CONTEXT, hashlib.sha256).digest()
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(key_material))


def encrypt_webhook_secret(value: str) -> str:
    """Encrypt an immutable delivery snapshot with its dedicated cipher."""
    return _webhook_delivery_cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_webhook_secret(value: str) -> str:
    """Decrypt a delivery snapshot only immediately before signing a request."""
    return _webhook_delivery_cipher().decrypt(value.encode("utf-8")).decode("utf-8")


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


class WebhookDelivery(Base):
    """A durable, per-destination delivery record for an outbox event.

    The database uniqueness constraint is the concurrency boundary: one
    worker can own a given event/registration pair at a time, even when
    multiple outbox workers are running.
    """

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("outbox_event_id", "webhook_id", name="uq_webhook_delivery_event_hook"),
        UniqueConstraint("idempotency_key", name="uq_webhook_deliveries_idempotency_key"),
        CheckConstraint(
            "status IN ('PENDING','PROCESSING','RETRY','SUCCEEDED','DEAD_LETTER','QUARANTINED')",
            name="ck_webhook_deliveries_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 100 AND attempt_count <= max_attempts",
            name="ck_webhook_deliveries_attempts",
        ),
        CheckConstraint(
            "(status = 'PROCESSING' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'PROCESSING' AND lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_webhook_deliveries_lease_state",
        ),
        CheckConstraint(
            "(status IN ('SUCCEEDED','DEAD_LETTER','QUARANTINED') AND terminal_at IS NOT NULL) "
            "OR (status NOT IN ('SUCCEEDED','DEAD_LETTER','QUARANTINED') AND terminal_at IS NULL)",
            name="ck_webhook_deliveries_terminal_state",
        ),
        CheckConstraint(
            "(status IN ('PENDING','RETRY') AND next_attempt_at IS NOT NULL) "
            "OR (status NOT IN ('PENDING','RETRY') AND next_attempt_at IS NULL)",
            name="ck_webhook_deliveries_next_attempt_state",
        ),
        CheckConstraint(
            "error_code IS NULL OR (length(error_code) BETWEEN 1 AND 64 AND error_code = upper(error_code) AND error_code NOT LIKE '% %')",
            name="ck_webhook_deliveries_error_code",
        ),
        Index(
            "ix_webhook_deliveries_dispatch_due",
            "next_attempt_at",
            "id",
            postgresql_where=text("status IN ('PENDING','RETRY')"),
        ),
        Index(
            "ix_webhook_deliveries_expired_lease",
            "lease_expires_at",
            "id",
            postgresql_where=text("status = 'PROCESSING'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    outbox_event_id = Column(Integer, ForeignKey("outbox_events.id", ondelete="CASCADE"), nullable=False, index=True)
    webhook_id = Column(Integer, ForeignKey("webhooks.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    target_url = Column(String, nullable=False)
    encrypted_signing_secret = Column(String, nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String, nullable=False, default="PENDING", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5, server_default="5")
    lease_owner = Column(String(128), nullable=True)
    lease_token = Column(String, nullable=True, index=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    terminal_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String, nullable=True)

    outbox_event = relationship("OutboxEvent")
    webhook = relationship("WebhookRegistration")
