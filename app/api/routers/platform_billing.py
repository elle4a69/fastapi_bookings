"""Platform billing, subscription projection, and customer portal router (WP2 & WP4)."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
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
    PlatformEntitlementGrant,
    ProviderEventInbox,
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
    PlatformTenantBillingSummary,
    PlatformTenantDiagnostics,
    ProviderEventInboxRead,
    PlatformEntitlementGrantRead,
    PlatformEntitlementGrantCreate,
    PlatformGrantRevokeResponse,
    ReconciliationTriggerRequest,
)
from app.services.platform_billing.entitlement_guard import (
    EntitlementGuardService,
    _as_utc,
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
    """Return the authenticated tenant's current subscription projection, plan details, status,
    billing cycle, past_due status, active entitlement snapshots, and current consumption quotas.

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

    plan_id = sub_proj.plan_id if sub_proj else (tenant.subscription_tier or "starter")
    plan_name = plan_id.title()
    sub_status = sub_proj.status if sub_proj else (billing_acct.billing_state if billing_acct and billing_acct.billing_state != "unconfigured" else "active")
    is_past_due = (sub_status == "past_due")
    billing_cycle = "monthly"
    if sub_proj and sub_proj.current_period_start and sub_proj.current_period_end:
        days = (sub_proj.current_period_end - sub_proj.current_period_start).days
        if days > 60:
            billing_cycle = "annual"

    quotas_to_check = [
        ("locations.max", "locations", "Locations"),
        ("providers.max", "providers", "Providers"),
        ("sms.monthly_outbound_messages", "messages", "SMS Outbound Messages"),
        ("assistant.monthly_runs", "runs", "Assistant Runs"),
    ]
    usage_quotas: Dict[str, Dict[str, Any]] = {}
    for q_key, unit, label in quotas_to_check:
        eff = EntitlementGuardService.get_effective_entitlement(db, tenant.id, q_key)
        limit_val = eff[1] if eff else None
        current_used = EntitlementGuardService.get_current_usage(db, tenant.id, q_key)
        usage_quotas[q_key] = {
            "key": q_key,
            "label": label,
            "limit": limit_val,
            "current_usage": current_used,
            "unit": unit,
        }

    capabilities: Dict[str, bool] = {
        "assistant.enabled": EntitlementGuardService.has_entitlement(db, tenant.id, "assistant.enabled"),
        "sms.enabled": EntitlementGuardService.has_entitlement(db, tenant.id, "sms.enabled"),
        "api.enabled": EntitlementGuardService.has_entitlement(db, tenant.id, "api.enabled"),
    }

    return TenantSubscriptionOverview(
        billing_account=BillingAccountRead.model_validate(billing_acct) if billing_acct else None,
        subscription=SubscriptionProjectionRead.model_validate(sub_proj) if sub_proj else None,
        entitlements=[EntitlementSnapshotRead.model_validate(e) for e in entitlements],
        plan_name=plan_name,
        status=sub_status,
        billing_cycle=billing_cycle,
        is_past_due=is_past_due,
        usage_quotas=usage_quotas,
        capabilities=capabilities,
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
    "/api/admin/platform/billing/tenants",
    response_model=List[PlatformTenantBillingSummary],
    status_code=status.HTTP_200_OK,
)
def list_platform_tenants_billing(
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> List[PlatformTenantBillingSummary]:
    """List all tenants with their subscription projection, plan, status, and health.

    Strictly reserved for authenticated platform owners.
    """
    tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()
    results: List[PlatformTenantBillingSummary] = []
    for t in tenants:
        sub_proj = (
            db.query(SubscriptionProjection)
            .filter(SubscriptionProjection.tenant_id == t.id)
            .order_by(SubscriptionProjection.id.desc())
            .first()
        )
        billing_acct = (
            db.query(BillingAccount)
            .filter(BillingAccount.tenant_id == t.id)
            .first()
        )
        plan_id = sub_proj.plan_id if sub_proj else (t.subscription_tier or "starter")
        sub_status = sub_proj.status if sub_proj else (billing_acct.billing_state if billing_acct and billing_acct.billing_state != "unconfigured" else "active")
        is_past_due = (sub_status == "past_due")
        if is_past_due or sub_status == "cancelled":
            health = "critical"
        elif sub_status in ("trialing", "unconfigured"):
            health = "warning"
        else:
            health = "healthy"

        results.append(
            PlatformTenantBillingSummary(
                tenant_id=t.id,
                tenant_name=t.name,
                subdomain=t.subdomain,
                plan_id=plan_id,
                plan_name=plan_id.title(),
                status=sub_status,
                health=health,
                billing_state=billing_acct.billing_state if billing_acct else "unconfigured",
                current_period_end=sub_proj.current_period_end if sub_proj else None,
                is_past_due=is_past_due,
                created_at=t.created_at or datetime.now(timezone.utc),
            )
        )
    return results


@router.get(
    "/api/admin/platform/billing/tenants/{tenant_id}/diagnostics",
    response_model=PlatformTenantDiagnostics,
    status_code=status.HTTP_200_OK,
)
def get_tenant_billing_diagnostics(
    tenant_id: int,
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> PlatformTenantDiagnostics:
    """Detailed diagnostics for a specific tenant (projections, entitlements, active grants, recent events)."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )

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
    grants = (
        db.query(PlatformEntitlementGrant)
        .filter(PlatformEntitlementGrant.tenant_id == tenant.id)
        .order_by(PlatformEntitlementGrant.id.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    grant_reads: List[PlatformEntitlementGrantRead] = []
    for g in grants:
        g_exp = _as_utc(g.expires_at) if g.expires_at else None
        active = (not g.is_revoked) and (g_exp is None or g_exp > now)
        grant_reads.append(
            PlatformEntitlementGrantRead(
                id=g.id,
                tenant_id=g.tenant_id,
                tenant_name=tenant.name,
                entitlement_key=g.entitlement_key,
                value_type=g.value_type,
                granted_value=g.granted_value,
                expires_at=g.expires_at,
                reason=g.reason,
                granted_by_user_id=g.granted_by_user_id,
                is_revoked=g.is_revoked,
                is_active=active,
                created_at=g.created_at,
                updated_at=g.updated_at,
            )
        )

    recent_events = (
        db.query(ProviderEventInbox)
        .order_by(ProviderEventInbox.id.desc())
        .limit(10)
        .all()
    )

    quotas_to_check = [
        "locations.max",
        "providers.max",
        "sms.monthly_outbound_messages",
        "assistant.monthly_runs",
    ]
    usage_summary: Dict[str, Any] = {}
    for q_key in quotas_to_check:
        eff = EntitlementGuardService.get_effective_entitlement(db, tenant.id, q_key)
        limit_val = eff[1] if eff else None
        used = EntitlementGuardService.get_current_usage(db, tenant.id, q_key)
        usage_summary[q_key] = {"limit": limit_val, "current_usage": used}

    return PlatformTenantDiagnostics(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        subdomain=tenant.subdomain,
        billing_account=BillingAccountRead.model_validate(billing_acct) if billing_acct else None,
        subscription=SubscriptionProjectionRead.model_validate(sub_proj) if sub_proj else None,
        entitlements=[EntitlementSnapshotRead.model_validate(e) for e in entitlements],
        active_grants=grant_reads,
        recent_events=[ProviderEventInboxRead.model_validate(e) for e in recent_events],
        usage_summary=usage_summary,
    )


@router.get(
    "/api/admin/platform/billing/inbox",
    response_model=List[ProviderEventInboxRead],
    status_code=status.HTTP_200_OK,
)
def list_platform_inbox_events(
    status_filter: Optional[str] = Query(None, description="Filter by processing status (e.g. 'failed', 'pending')"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> List[ProviderEventInboxRead]:
    """List recent provider event inbox records, highlighting failures/dead letters."""
    query = db.query(ProviderEventInbox)
    if status_filter:
        query = query.filter(ProviderEventInbox.processing_status == status_filter)
    events = query.order_by(ProviderEventInbox.id.desc()).limit(limit).all()
    return [ProviderEventInboxRead.model_validate(e) for e in events]


@router.post(
    "/api/admin/platform/billing/inbox/{event_id}/retry",
    response_model=ProviderEventInboxRead,
    status_code=status.HTTP_200_OK,
)
def retry_platform_inbox_event(
    event_id: str,
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> ProviderEventInboxRead:
    """Retry a failed event inbox item."""
    query = db.query(ProviderEventInbox)
    if event_id.isdigit():
        event = query.filter(
            (ProviderEventInbox.id == int(event_id))
            | (ProviderEventInbox.external_event_id == event_id)
        ).first()
    else:
        event = query.filter(ProviderEventInbox.external_event_id == event_id).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbox event '{event_id}' not found",
        )

    event.retry_count += 1
    event.processing_status = "pending"
    event.error_message = None
    db.commit()
    db.refresh(event)
    return ProviderEventInboxRead.model_validate(event)


@router.get(
    "/api/admin/platform/billing/grants",
    response_model=List[PlatformEntitlementGrantRead],
    status_code=status.HTTP_200_OK,
)
def list_platform_grants(
    tenant_id: Optional[int] = Query(None, description="Optional tenant ID to filter grants"),
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> List[PlatformEntitlementGrantRead]:
    """List active/historical platform operator grants across tenants."""
    query = db.query(PlatformEntitlementGrant)
    if tenant_id:
        query = query.filter(PlatformEntitlementGrant.tenant_id == tenant_id)
    grants = query.order_by(PlatformEntitlementGrant.id.desc()).all()

    now = datetime.now(timezone.utc)
    results: List[PlatformEntitlementGrantRead] = []
    tenant_ids = {g.tenant_id for g in grants}
    tenants_map = {t.id: t.name for t in db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()} if tenant_ids else {}

    for g in grants:
        g_exp = _as_utc(g.expires_at) if g.expires_at else None
        active = (not g.is_revoked) and (g_exp is None or g_exp > now)
        results.append(
            PlatformEntitlementGrantRead(
                id=g.id,
                tenant_id=g.tenant_id,
                tenant_name=tenants_map.get(g.tenant_id),
                entitlement_key=g.entitlement_key,
                value_type=g.value_type,
                granted_value=g.granted_value,
                expires_at=g.expires_at,
                reason=g.reason,
                granted_by_user_id=g.granted_by_user_id,
                is_revoked=g.is_revoked,
                is_active=active,
                created_at=g.created_at,
                updated_at=g.updated_at,
            )
        )
    return results


@router.post(
    "/api/admin/platform/billing/grants",
    response_model=PlatformEntitlementGrantRead,
    status_code=status.HTTP_201_CREATED,
)
def create_platform_grant(
    body: PlatformEntitlementGrantCreate,
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> PlatformEntitlementGrantRead:
    """Create an explicit, expiring, audited platform grant."""
    tenant = db.query(Tenant).filter(Tenant.id == body.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target tenant {body.tenant_id} not found",
        )

    if not body.reason or len(body.reason.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A non-empty operational reason is required for platform grants.",
        )

    grant = PlatformEntitlementGrant(
        tenant_id=body.tenant_id,
        entitlement_key=body.entitlement_key,
        value_type=body.value_type,
        granted_value=body.granted_value,
        expires_at=body.expires_at,
        reason=body.reason.strip(),
        granted_by_user_id=platform_owner.id,
        is_revoked=False,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)

    now = datetime.now(timezone.utc)
    g_exp = _as_utc(grant.expires_at) if grant.expires_at else None
    active = (not grant.is_revoked) and (g_exp is None or g_exp > now)

    return PlatformEntitlementGrantRead(
        id=grant.id,
        tenant_id=grant.tenant_id,
        tenant_name=tenant.name,
        entitlement_key=grant.entitlement_key,
        value_type=grant.value_type,
        granted_value=grant.granted_value,
        expires_at=grant.expires_at,
        reason=grant.reason,
        granted_by_user_id=grant.granted_by_user_id,
        is_revoked=grant.is_revoked,
        is_active=active,
        created_at=grant.created_at,
        updated_at=grant.updated_at,
    )


@router.delete(
    "/api/admin/platform/billing/grants/{grant_id}",
    response_model=PlatformGrantRevokeResponse,
    status_code=status.HTTP_200_OK,
)
def revoke_platform_grant(
    grant_id: int,
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> PlatformGrantRevokeResponse:
    """Revoke an active platform grant."""
    grant = db.query(PlatformEntitlementGrant).filter(PlatformEntitlementGrant.id == grant_id).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform grant {grant_id} not found",
        )

    now = datetime.now(timezone.utc)
    grant.is_revoked = True
    grant.updated_at = now
    db.commit()

    return PlatformGrantRevokeResponse(
        status="revoked",
        grant_id=grant_id,
        revoked_at=now,
    )


@router.get(
    "/api/admin/platform/billing/reconcile",
    response_model=List[ReconciliationReport],
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/api/admin/platform/billing/reconcile",
    response_model=List[ReconciliationReport],
    status_code=status.HTTP_200_OK,
)
def reconcile_platform_billing(
    tenant_id: Optional[int] = Query(None, description="Optional tenant ID to reconcile"),
    body: Optional[ReconciliationTriggerRequest] = None,
    db: Session = Depends(get_db),
    platform_owner: User = Depends(get_current_platform_owner),
) -> List[ReconciliationReport]:
    """Reconcile local subscription projections against remote provider state.

    Strictly reserved for authenticated platform owners.
    """
    effective_tenant_id = body.tenant_id if (body and body.tenant_id) else tenant_id

    if effective_tenant_id:
        report = reconciliation_service.reconcile_tenant_subscription(
            db=db,
            tenant_id=effective_tenant_id,
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
