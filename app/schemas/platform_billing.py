"""Pydantic schemas for Platform Billing, Subscriptions, and Entitlements (WP2)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
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
    plan_name: Optional[str] = None
    status: Optional[str] = "active"
    billing_cycle: Optional[str] = "monthly"
    is_past_due: bool = False
    usage_quotas: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    capabilities: Dict[str, bool] = Field(default_factory=dict)


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


class ProviderEventInboxRead(BaseModel):
    """Public read schema for provider webhook event inbox records."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    external_event_id: str
    event_type: str
    payload_digest: str
    verified_at: Optional[datetime] = None
    processing_status: str
    retry_count: int
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime


class PlatformEntitlementGrantRead(BaseModel):
    """Public read schema for platform-authorized entitlement overrides."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    tenant_name: Optional[str] = None
    entitlement_key: str
    value_type: str
    granted_value: str
    expires_at: Optional[datetime] = None
    reason: str
    granted_by_user_id: Optional[int] = None
    is_revoked: bool
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class PlatformEntitlementGrantCreate(BaseModel):
    """Payload to issue an explicit, expiring, audited platform grant."""
    tenant_id: int = Field(..., description="Target tenant ID")
    entitlement_key: str = Field(..., description="Canonical entitlement key")
    value_type: str = Field("boolean", description="Type: boolean, numeric, string")
    granted_value: str = Field(..., description="Value to grant (e.g. 'true' or '50')")
    expires_at: Optional[datetime] = Field(None, description="Optional expiry timestamp")
    reason: str = Field(..., min_length=3, description="Mandatory operational audit reason")


class PlatformGrantRevokeResponse(BaseModel):
    """Response returned upon revoking a platform grant."""
    status: str
    grant_id: int
    revoked_at: datetime


class PlatformTenantBillingSummary(BaseModel):
    """High-level summary of a tenant's billing health and plan for platform operators."""
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    tenant_name: str
    subdomain: str
    plan_id: str
    plan_name: str
    status: str
    health: str  # 'healthy', 'warning', 'critical'
    billing_state: str
    current_period_end: Optional[datetime] = None
    is_past_due: bool = False
    created_at: datetime


class PlatformTenantDiagnostics(BaseModel):
    """Detailed diagnostics for a specific tenant in the platform console."""
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    tenant_name: str
    subdomain: str
    billing_account: Optional[BillingAccountRead] = None
    subscription: Optional[SubscriptionProjectionRead] = None
    entitlements: List[EntitlementSnapshotRead] = Field(default_factory=list)
    active_grants: List[PlatformEntitlementGrantRead] = Field(default_factory=list)
    recent_events: List[ProviderEventInboxRead] = Field(default_factory=list)
    usage_summary: Dict[str, Any] = Field(default_factory=dict)


class ReconciliationTriggerRequest(BaseModel):
    """Payload for triggering reconciliation."""
    tenant_id: Optional[int] = Field(None, description="Optional tenant ID to reconcile")
