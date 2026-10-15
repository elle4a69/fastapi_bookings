"""Pydantic schemas for Platform Billing, Subscriptions, and Entitlements (WP2)."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BillingAccountRead(BaseModel):
    """Public read schema for a tenant's billing account."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    flexprice_customer_id: Optional[str] = None
    billing_state: str
    created_at: datetime
    updated_at: datetime


class SubscriptionProjectionRead(BaseModel):
    """Public read schema for a tenant's active subscription projection."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    external_subscription_id: str
    plan_id: str
    plan_version: int
    status: str
    trial_end: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at: Optional[datetime] = None
    last_event_timestamp: datetime
    last_event_sequence: int
    created_at: datetime
    updated_at: datetime


class EntitlementSnapshotRead(BaseModel):
    """Read schema for individual active entitlements."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    entitlement_key: str
    value_type: str
    value: str
    effective_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    source_subscription_id: Optional[str] = None
    is_active: bool


class TenantSubscriptionOverview(BaseModel):
    """Combined view of a tenant's billing status, active subscription, and entitlements."""
    model_config = ConfigDict(from_attributes=True)

    billing_account: Optional[BillingAccountRead] = None
    subscription: Optional[SubscriptionProjectionRead] = None
    entitlements: List[EntitlementSnapshotRead] = Field(default_factory=list)


class PortalSessionCreateRequest(BaseModel):
    """Request schema for creating a hosted billing portal session."""
    return_url: Optional[str] = Field(
        None,
        description="Optional redirect URL after customer exits the hosted billing portal",
    )


class PortalSessionResponse(BaseModel):
    """Response containing the secure, short-lived hosted portal session URL."""
    portal_url: str
    expires_at: Optional[datetime] = None


class UsageRecordRequest(BaseModel):
    """Request schema for recording metered consumption."""
    meter_key: str = Field(..., description="Canonical meter key (e.g. 'sms_outbound', 'ai_tokens')")
    quantity: int = Field(1, ge=1, description="Quantity consumed")
    idempotency_key: Optional[str] = Field(None, description="Optional caller-specified idempotency key")
    occurred_at: Optional[datetime] = Field(None, description="Timestamp of occurrence, defaults to now")


class UsageRecordResponse(BaseModel):
    """Response schema for recorded usage event."""
    model_config = ConfigDict(from_attributes=True)

    idempotency_key: str
    tenant_id: int
    meter_key: str
    quantity: int
    delivery_state: str
    occurred_at: datetime


class ReconciliationReport(BaseModel):
    """Report comparing local projection with remote provider state."""
    tenant_id: int
    external_subscription_id: Optional[str] = None
    local_status: Optional[str] = None
    remote_status: Optional[str] = None
    is_synchronized: bool
    discrepancy_details: Optional[str] = None


class WebhookIngestResponse(BaseModel):
    """Acknowledgement response for incoming webhook payloads."""
    status: str
    event_id: str
    message: str
    action_taken: str
