"""Platform Billing & Subscription Projection Models for Flexprice Integration (WP2).

Defines persistence for tenant billing accounts, external subscription projections,
entitlement snapshots, provider event inbox (for raw-payload verification and idempotency),
and usage event outbox (for metered billing delivery).

IMPORTANT SECURITY CONSTRAINT:
NO payment credentials (such as credit card numbers, CVVs, banking details) are stored
in this application or database. All checkout and payment instrument management is delegated
to the hosted Flexprice customer portal.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, backref

from ..db.database import Base


class BillingAccount(Base):
    """Maps an internal Tenant to an external Flexprice billing customer.

    Attributes:
        id: Primary key.
        tenant_id: Internal tenant ID (one billing account per tenant).
        flexprice_customer_id: External customer ID in Flexprice.
        billing_state: Lifecycle state ('unconfigured', 'active', 'past_due', 'suspended', 'cancelled').
        created_at: Account creation timestamp.
        updated_at: Account update timestamp.
    """

    __tablename__ = "billing_accounts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    flexprice_customer_id = Column(String(128), nullable=True, index=True)
    billing_state = Column(String(32), default="unconfigured", nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant", backref=backref("billing_account", uselist=False))

    def __repr__(self) -> str:
        return f"<BillingAccount id={self.id} tenant_id={self.tenant_id} flexprice_customer_id={self.flexprice_customer_id} state={self.billing_state}>"


class SubscriptionProjection(Base):
    """Authoritative local projection of a tenant's external Flexprice subscription.

    Records the current state, active plan version, billing periods, and event ordering
    metadata to guarantee out-of-order event resilience.

    Attributes:
        id: Primary key.
        tenant_id: Internal tenant ID.
        external_subscription_id: Unique subscription ID from Flexprice.
        plan_id: Plan identifier (e.g. 'starter', 'pro', 'enterprise').
        plan_version: Plan revision or version number.
        status: Projection status ('active', 'trialing', 'past_due', 'cancelled', 'paused').
        trial_end: End of trial period (if applicable).
        current_period_start: Start of current billing cycle.
        current_period_end: End of current billing cycle.
        cancel_at: Scheduled cancellation timestamp.
        last_event_timestamp: Provider timestamp of the last processed event.
        last_event_sequence: Monotonic sequence number of the last processed event.
        created_at: Projection creation timestamp.
        updated_at: Projection update timestamp.
    """

    __tablename__ = "subscription_projections"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_subscription_id = Column(String(128), nullable=False, unique=True, index=True)
    plan_id = Column(String(64), nullable=False, index=True)
    plan_version = Column(Integer, default=1, nullable=False)
    status = Column(String(32), default="active", nullable=False, index=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at = Column(DateTime(timezone=True), nullable=True)
    last_event_timestamp = Column(DateTime(timezone=True), nullable=False)
    last_event_sequence = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant", backref="subscription_projections")

    def __repr__(self) -> str:
        return f"<SubscriptionProjection id={self.id} tenant_id={self.tenant_id} plan={self.plan_id} status={self.status}>"


class EntitlementSnapshot(Base):
    """Calculated active entitlements and quotas derived from current subscription projections.

    Attributes:
        id: Primary key.
        tenant_id: Internal tenant ID.
        entitlement_key: Canonical entitlement key (e.g. 'max_locations', 'ai_voice_enabled').
        value_type: Type descriptor ('boolean', 'numeric', 'string').
        value: String representation of the entitlement limit/feature flag.
        effective_from: Activation timestamp.
        expires_at: Expiration timestamp.
        source_subscription_id: External subscription ID originating this entitlement.
        is_active: Whether this entitlement is currently active and enforceable.
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.
    """

    __tablename__ = "entitlement_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entitlement_key", name="uq_tenant_entitlement_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entitlement_key = Column(String(128), nullable=False, index=True)
    value_type = Column(String(32), nullable=False)
    value = Column(String(255), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    source_subscription_id = Column(String(128), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant", backref="entitlement_snapshots")

    def __repr__(self) -> str:
        return f"<EntitlementSnapshot tenant_id={self.tenant_id} key={self.entitlement_key} value={self.value} active={self.is_active}>"


class ProviderEventInbox(Base):
    """Inbox for external provider events to guarantee idempotency and auditability.

    Stores the SHA-256 digest of the raw payload (protecting privacy and secrets),
    verifies signatures, and protects against duplicate or out-of-order processing.

    Attributes:
        id: Primary key.
        provider: Provider identifier ('flexprice').
        external_event_id: Provider's event identifier.
        event_type: Provider event type ('subscription.created', 'subscription.updated', etc.).
        payload_digest: Hex-encoded SHA-256 digest of the verified raw payload.
        verified_at: Signature verification timestamp.
        processing_status: Processing lifecycle ('pending', 'processed', 'failed', 'ignored').
        retry_count: Processing attempts made.
        error_message: Privacy-safe processing failure message.
        processed_at: Processing completion timestamp.
        created_at: Record receipt timestamp.
    """

    __tablename__ = "provider_event_inbox"
    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", name="uq_provider_event_inbox_provider_event"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), default="flexprice", nullable=False, index=True)
    external_event_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload_digest = Column(String(64), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    processing_status = Column(String(32), default="pending", nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProviderEventInbox id={self.id} provider={self.provider} event_id={self.external_event_id} status={self.processing_status}>"


class UsageEventOutbox(Base):
    """Outbox for metering events dispatched to the external billing provider.

    Enforces stable idempotency keys and retry semantics so consumption events
    (SMS messages, AI tokens, appointments booked) are reliably delivered exactly once.

    Attributes:
        id: Primary key.
        tenant_id: Internal tenant ID incurring the usage.
        idempotency_key: Globally unique idempotency key for this usage record.
        meter_key: External meter identifier (e.g. 'sms_outbound', 'ai_tokens').
        quantity: Metered units consumed.
        occurred_at: Timestamp when usage occurred.
        delivery_state: Lifecycle state ('pending', 'delivered', 'failed').
        retry_count: Delivery attempts made.
        created_at: Record creation timestamp.
        delivered_at: Delivery confirmation timestamp.
    """

    __tablename__ = "usage_event_outbox"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_usage_event_outbox_idempotency_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    meter_key = Column(String(64), nullable=False, index=True)
    quantity = Column(Integer, default=1, nullable=False)
    occurred_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    delivery_state = Column(String(32), default="pending", nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", backref="usage_events")

    def __repr__(self) -> str:
        return f"<UsageEventOutbox id={self.id} tenant_id={self.tenant_id} meter={self.meter_key} qty={self.quantity} state={self.delivery_state}>"
