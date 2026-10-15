"""Platform billing services package for Flexprice integration and subscription projection."""

from .flexprice_client import (
    FlexpriceClient,
    FlexpriceClientError,
    FlexpriceOutageError,
    flexprice_client,
)
from .webhook_verifier import (
    WebhookVerificationService,
    WebhookVerificationError,
    webhook_verifier,
)
from .projection_service import (
    SubscriptionProjectionService,
    projection_service,
    PLAN_ENTITLEMENT_CATALOG,
)
from .metering_service import (
    UsageMeteringService,
    usage_metering_service,
)
from .reconciliation_service import (
    ReconciliationService,
    reconciliation_service,
)
from .entitlement_guard import (
    EntitlementGuardService,
    entitlement_guard,
    require_entitlement,
    require_quota,
    EntitlementRequiredError,
    QuotaExceededError,
    ENTITLEMENT_ASSISTANT_ENABLED,
    ENTITLEMENT_ASSISTANT_MONTHLY_RUNS,
    ENTITLEMENT_SMS_ENABLED,
    ENTITLEMENT_SMS_MONTHLY_MESSAGES,
    ENTITLEMENT_PROVIDERS_MAX,
    ENTITLEMENT_LOCATIONS_MAX,
    ENTITLEMENT_API_ENABLED,
)

__all__ = [
    "FlexpriceClient",
    "FlexpriceClientError",
    "FlexpriceOutageError",
    "flexprice_client",
    "WebhookVerificationService",
    "WebhookVerificationError",
    "webhook_verifier",
    "SubscriptionProjectionService",
    "projection_service",
    "PLAN_ENTITLEMENT_CATALOG",
    "UsageMeteringService",
    "usage_metering_service",
    "ReconciliationService",
    "reconciliation_service",
    "EntitlementGuardService",
    "entitlement_guard",
    "require_entitlement",
    "require_quota",
    "EntitlementRequiredError",
    "QuotaExceededError",
    "ENTITLEMENT_ASSISTANT_ENABLED",
    "ENTITLEMENT_ASSISTANT_MONTHLY_RUNS",
    "ENTITLEMENT_SMS_ENABLED",
    "ENTITLEMENT_SMS_MONTHLY_MESSAGES",
    "ENTITLEMENT_PROVIDERS_MAX",
    "ENTITLEMENT_LOCATIONS_MAX",
    "ENTITLEMENT_API_ENABLED",
]
