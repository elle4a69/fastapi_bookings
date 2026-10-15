"""Platform billing, subscription projection, and customer portal router (WP2)."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_current_tenant,
    get_current_user,
    get_current_platform_owner,
    require_role,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.models.platform_billing import (
    BillingAccount,
    SubscriptionProjection,
    EntitlementSnapshot,
)
from app.schemas.platform_billing import (
    TenantSubscriptionOverview,
    BillingAccountRead,
    SubscriptionProjectionRead,
    EntitlementSnapshotRead,
    PortalSessionCreateRequest,
    PortalSessionResponse,
    UsageRecordRequest,
    UsageRecordResponse,
    ReconciliationReport,
)
from app.services.platform_billing.flexprice_client import (
    FlexpriceClientError,
    FlexpriceOutageError,
    flexprice_client,
)
from app.services.platform_billing.metering_service import usage_metering_service
from app.services.platform_billing.reconciliation_service import reconciliation_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["platform-billing"])


# ---------------------------------------------------------------------------
# Tenant-Scoped Billing Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/billing/subscription",
    response_model=TenantSubscriptionOverview,
    status_code=status.HTTP_200_OK,
)
def get_tenant_subscription(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
) -> TenantSubscriptionOverview:
    """Return the authenticated tenant's current subscription projection and entitlement snapshot.

    Enforces strict tenant isolation: users can only inspect billing details for their active tenant.
    """
    billing_acct = (
        db.query(BillingAccount)
        .filter(BillingAccount.tenant_id == tenant.id)
        .first()
    )
    sub_proj = (
        db.query(SubscriptionProjection)
        .filter(SubscriptionProjection.tenant_id == tenant.id)
        .order_by(SubscriptionProjection.id.desc())
        .first()
    )
    entitlements = (
        db.query(EntitlementSnapshot)
        .filter(EntitlementSnapshot.tenant_id == tenant.id)
        .all()
    )

    return TenantSubscriptionOverview(
        billing_account=BillingAccountRead.model_validate(billing_acct) if billing_acct else None,
        subscription=SubscriptionProjectionRead.model_validate(sub_proj) if sub_proj else None,
        entitlements=[EntitlementSnapshotRead.model_validate(e) for e in entitlements],
    )


@router.post(
    "/api/billing/portal-session",
    response_model=PortalSessionResponse,
    status_code=status.HTTP_200_OK,
)
def create_billing_portal_session(
    body: PortalSessionCreateRequest = PortalSessionCreateRequest(),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(require_role(["owner"])),
) -> PortalSessionResponse:
    """Generate a secure, short-lived hosted portal session for tenant self-service billing management.

    Strictly requires tenant owner role. Fails closed with 503 if provider is unreachable.
    NO payment credentials ever enter our system; all billing management is hosted by Flexprice.
    """
    billing_acct = (
        db.query(BillingAccount)
        .filter(BillingAccount.tenant_id == tenant.id)
        .first()
    )

    try:
        # Create external customer if missing
        if not billing_acct or not billing_acct.flexprice_customer_id:
            customer_resp = flexprice_client.create_customer(
                tenant_id=tenant.id,
                name=tenant.name,
                email=current_user.email,
            )
            customer_id = customer_resp.get("id") or customer_resp.get("customer_id")
            if not billing_acct:
                billing_acct = BillingAccount(
                    tenant_id=tenant.id,
                    flexprice_customer_id=customer_id,
                    billing_state="active",
                )
                db.add(billing_acct)
            else:
                billing_acct.flexprice_customer_id = customer_id
            db.commit()
            db.refresh(billing_acct)
        else:
            customer_id = billing_acct.flexprice_customer_id

        session_resp = flexprice_client.create_portal_session(
            customer_id=customer_id,
            return_url=body.return_url,
        )
        portal_url = session_resp.get("url") or session_resp.get("portal_url")
        if not portal_url:
            raise FlexpriceClientError("Provider returned empty portal session URL")

        return PortalSessionResponse(
            portal_url=portal_url,
            expires_at=session_resp.get("expires_at"),
        )

    except FlexpriceOutageError as exc:
        logger.error("Flexprice billing portal outage: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing portal service is temporarily unavailable. Please try again later.",
        )
    except FlexpriceClientError as exc:
        logger.error("Flexprice client error creating portal session: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to initiate billing portal session with provider.",
        )


@router.post(
    "/api/billing/usage",
    response_model=UsageRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_usage(
    body: UsageRecordRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
) -> UsageRecordResponse:
    """Record metered consumption for the active tenant into the outbox with idempotency."""
    record = usage_metering_service.record_usage(
        db=db,
        tenant_id=tenant.id,
        meter_key=body.meter_key,
        quantity=body.quantity,
        idempotency_key=body.idempotency_key,
        occurred_at=body.occurred_at,
    )
    return UsageRecordResponse.model_validate(record)


# ---------------------------------------------------------------------------
# Platform Owner Admin Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/admin/platform/billing/reconcile",
    response_model=List[ReconciliationReport],
    status_code=status.HTTP_200_OK,
)
def reconcile_platform_billing(
    tenant_id: Optional[int] = Query(None, description="Optional tenant ID to reconcile"),
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> List[ReconciliationReport]:
    """Reconcile local subscription projections against remote provider state.

    Strictly reserved for authenticated platform owners.
    """
    if tenant_id:
        report = reconciliation_service.reconcile_tenant_subscription(
            db=db,
            tenant_id=tenant_id,
        )
        return [report]

    # Reconcile all tenants with active projections
    projections = db.query(SubscriptionProjection).all()
    results: List[ReconciliationReport] = []
    seen_tenants = set()
    for proj in projections:
        if proj.tenant_id in seen_tenants:
            continue
        seen_tenants.add(proj.tenant_id)
        results.append(
            reconciliation_service.reconcile_tenant_subscription(
                db=db,
                tenant_id=proj.tenant_id,
            )
        )
    return results
