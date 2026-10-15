"""Reconciliation service for comparing local subscription projections with provider state."""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.platform_billing import (
    BillingAccount,
    SubscriptionProjection,
    ProviderEventInbox,
)
from app.schemas.platform_billing import ReconciliationReport
from app.services.platform_billing.flexprice_client import (
    FlexpriceClient,
    FlexpriceClientError,
    flexprice_client,
)

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Verifies synchronization between local projections and remote Flexprice state."""

    @classmethod
    def reconcile_tenant_subscription(
        cls,
        db: Session,
        tenant_id: int,
        client: Optional[FlexpriceClient] = None,
    ) -> ReconciliationReport:
        """Compare a tenant's local projection against remote Flexprice state."""
        api_client = client or flexprice_client
        local_proj = (
            db.query(SubscriptionProjection)
            .filter(SubscriptionProjection.tenant_id == tenant_id)
            .first()
        )

        if not local_proj:
            return ReconciliationReport(
                tenant_id=tenant_id,
                external_subscription_id=None,
                local_status=None,
                remote_status=None,
                is_synchronized=True,
                discrepancy_details="No local subscription active",
            )

        try:
            remote_sub = api_client.get_subscription(local_proj.external_subscription_id)
            remote_status = (remote_sub.get("status") or "").lower()
            remote_plan = (remote_sub.get("plan_id") or "").lower()

            is_synced = (
                local_proj.status.lower() == remote_status
                and local_proj.plan_id.lower() == remote_plan
            )
            discrepancies = None
            if not is_synced:
                discrepancies = (
                    f"Status mismatch (local={local_proj.status}, remote={remote_status}) "
                    f"or Plan mismatch (local={local_proj.plan_id}, remote={remote_plan})"
                )

            return ReconciliationReport(
                tenant_id=tenant_id,
                external_subscription_id=local_proj.external_subscription_id,
                local_status=local_proj.status,
                remote_status=remote_status,
                is_synchronized=is_synced,
                discrepancy_details=discrepancies,
            )
        except FlexpriceClientError as exc:
            logger.warning("Reconciliation lookup failed for tenant %d: %s", tenant_id, exc)
            return ReconciliationReport(
                tenant_id=tenant_id,
                external_subscription_id=local_proj.external_subscription_id,
                local_status=local_proj.status,
                remote_status=None,
                is_synchronized=False,
                discrepancy_details=f"Provider lookup failed: {exc}",
            )

    @classmethod
    def get_dead_letter_inbox_events(
        cls,
        db: Session,
        limit: int = 50,
    ) -> List[ProviderEventInbox]:
        """Fetch failed or dead-letter provider events from the inbox for audit and repair."""
        return (
            db.query(ProviderEventInbox)
            .filter(ProviderEventInbox.processing_status.in_(["failed", "ignored"]))
            .order_by(ProviderEventInbox.id.desc())
            .limit(limit)
            .all()
        )


reconciliation_service = ReconciliationService()
