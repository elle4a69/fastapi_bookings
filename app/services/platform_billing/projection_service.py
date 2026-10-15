"""Subscription projection and entitlement snapshot management service.

Implements transactional inbox event recording, signature-verified payload ingestion,
duplicate detection (idempotency), out-of-order protection (preventing resurrecting
cancelled subscriptions from stale webhooks), and atomic entitlement calculations.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.platform_billing import (
    BillingAccount,
    SubscriptionProjection,
    EntitlementSnapshot,
    ProviderEventInbox,
)
from app.services.platform_billing.webhook_verifier import webhook_verifier

logger = logging.getLogger(__name__)

# Canonical default plan entitlements
PLAN_ENTITLEMENT_CATALOG = {
    "starter": {
        "max_locations": ("numeric", "1"),
        "ai_voice_enabled": ("boolean", "false"),
        "sms_monthly_quota": ("numeric", "100"),
        "max_staff": ("numeric", "2"),
        "features.custom_domain": ("boolean", "false"),
        "features.advanced_reporting": ("boolean", "false"),
    },
    "pro": {
        "max_locations": ("numeric", "5"),
        "ai_voice_enabled": ("boolean", "true"),
        "sms_monthly_quota": ("numeric", "1000"),
        "max_staff": ("numeric", "10"),
        "features.custom_domain": ("boolean", "true"),
        "features.advanced_reporting": ("boolean", "false"),
    },
    "enterprise": {
        "max_locations": ("numeric", "100"),
        "ai_voice_enabled": ("boolean", "true"),
        "sms_monthly_quota": ("numeric", "10000"),
        "max_staff": ("numeric", "100"),
        "features.custom_domain": ("boolean", "true"),
        "features.advanced_reporting": ("boolean", "true"),
    },
}


def _parse_iso_datetime(val: Any) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        # replace Z with +00:00 for fromisoformat compatibility
        cleaned = str(val).replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SubscriptionProjectionService:
    """Manages subscription projections and derived entitlement snapshots."""

    @classmethod
    def record_inbox_event(
        cls,
        db: Session,
        external_event_id: str,
        event_type: str,
        raw_body: bytes,
        verified: bool = True,
    ) -> Tuple[ProviderEventInbox, bool]:
        """Atomically record incoming provider event into ProviderEventInbox.

        Returns:
            Tuple of (inbox_event, is_new). If already exists, returns existing and False.
        """
        existing = (
            db.query(ProviderEventInbox)
            .filter(
                ProviderEventInbox.provider == "flexprice",
                ProviderEventInbox.external_event_id == external_event_id,
            )
            .first()
        )
        if existing:
            logger.info(
                "Duplicate provider event received: %s (status=%s)",
                external_event_id,
                existing.processing_status,
            )
            return existing, False

        digest = webhook_verifier.compute_payload_digest(raw_body)
        now = datetime.now(timezone.utc)
        inbox_event = ProviderEventInbox(
            provider="flexprice",
            external_event_id=external_event_id,
            event_type=event_type,
            payload_digest=digest,
            verified_at=now if verified else None,
            processing_status="pending",
            retry_count=0,
            created_at=now,
        )
        db.add(inbox_event)
        db.commit()
        db.refresh(inbox_event)
        return inbox_event, True

    @classmethod
    def process_subscription_event(
        cls,
        db: Session,
        inbox_event: ProviderEventInbox,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process a validated subscription lifecycle event with out-of-order and idempotency guards.

        Args:
            db: Database session.
            inbox_event: The ProviderEventInbox record.
            event_data: Parsed JSON payload from Flexprice.

        Returns:
            Dict containing processing status and action details.
        """
        if inbox_event.processing_status == "processed":
            return {
                "status": "already_processed",
                "message": "Event was previously processed.",
            }

        # Extract nested payload or top-level
        data = event_data.get("data", event_data)
        event_type = event_data.get("event_type", inbox_event.event_type)

        external_sub_id = data.get("subscription_id") or data.get("id")
        if not external_sub_id:
            inbox_event.processing_status = "failed"
            inbox_event.error_message = "Missing subscription_id in event payload"
            inbox_event.processed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "failed", "error": inbox_event.error_message}

        customer_id = data.get("customer_id")
        tenant_id = data.get("tenant_id") or (data.get("metadata") or {}).get("tenant_id")
        if tenant_id is not None:
            try:
                tenant_id = int(tenant_id)
            except (ValueError, TypeError):
                tenant_id = None

        # If tenant_id not in event, resolve from customer_id via BillingAccount
        if tenant_id is None and customer_id:
            acct = (
                db.query(BillingAccount)
                .filter(BillingAccount.flexprice_customer_id == customer_id)
                .first()
            )
            if acct:
                tenant_id = acct.tenant_id

        if tenant_id is None:
            # Check if subscription projection already exists to infer tenant_id
            existing_sub = (
                db.query(SubscriptionProjection)
                .filter(SubscriptionProjection.external_subscription_id == external_sub_id)
                .first()
            )
            if existing_sub:
                tenant_id = existing_sub.tenant_id

        if tenant_id is None:
            inbox_event.processing_status = "failed"
            inbox_event.error_message = f"Unable to resolve tenant_id for customer={customer_id} sub={external_sub_id}"
            inbox_event.processed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "failed", "error": inbox_event.error_message}

        # Check tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            inbox_event.processing_status = "failed"
            inbox_event.error_message = f"Tenant {tenant_id} not found in local database"
            inbox_event.processed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "failed", "error": inbox_event.error_message}

        # Parse event ordering metadata
        raw_event_timestamp = event_data.get("event_timestamp") or data.get("updated_at") or data.get("created_at")
        event_timestamp = _parse_iso_datetime(raw_event_timestamp) or datetime.now(timezone.utc)
        sequence_num = int(event_data.get("sequence", 0) or data.get("sequence", 0))

        # Check existing subscription projection
        existing_proj = (
            db.query(SubscriptionProjection)
            .filter(SubscriptionProjection.external_subscription_id == external_sub_id)
            .first()
        )

        incoming_status = (data.get("status") or "active").lower()
        incoming_plan_id = (data.get("plan_id") or "starter").lower()
        incoming_plan_version = int(data.get("plan_version") or 1)

        if existing_proj:
            current_ts = _as_utc(event_timestamp)
            existing_ts = _as_utc(existing_proj.last_event_timestamp)

            # Out-of-order protection:
            # 1. Stale timestamp check
            if current_ts < existing_ts:
                logger.warning(
                    "Out-of-order event rejected: event ts %s < existing ts %s (sub=%s)",
                    current_ts,
                    existing_ts,
                    external_sub_id,
                )
                inbox_event.processing_status = "ignored"
                inbox_event.error_message = (
                    f"Ignored out-of-order event: timestamp {current_ts.isoformat()} "
                    f"is older than current projection state {existing_ts.isoformat()}"
                )
                inbox_event.processed_at = datetime.now(timezone.utc)
                db.commit()
                return {"status": "ignored", "reason": "out_of_order_timestamp"}

            # 2. Sequence check if timestamps match
            if current_ts == existing_ts and sequence_num <= existing_proj.last_event_sequence:
                inbox_event.processing_status = "ignored"
                inbox_event.error_message = "Ignored out-of-order event: sequence number not newer than current projection"
                inbox_event.processed_at = datetime.now(timezone.utc)
                db.commit()
                return {"status": "ignored", "reason": "out_of_order_sequence"}

            # 3. Resurrection guard: terminated/cancelled subscription cannot be re-activated by an older or equal sequence
            if existing_proj.status in ("cancelled", "terminated") and incoming_status in ("active", "trialing"):
                if current_ts <= existing_ts:
                    inbox_event.processing_status = "ignored"
                    inbox_event.error_message = "Rejected event attempting to resurrect cancelled subscription with non-monotonic event"
                    inbox_event.processed_at = datetime.now(timezone.utc)
                    db.commit()
                    return {"status": "ignored", "reason": "resurrection_blocked"}


            # Update existing projection
            existing_proj.plan_id = incoming_plan_id
            existing_proj.plan_version = incoming_plan_version
            existing_proj.status = incoming_status
            existing_proj.trial_end = _parse_iso_datetime(data.get("trial_end"))
            existing_proj.current_period_start = _parse_iso_datetime(data.get("current_period_start"))
            existing_proj.current_period_end = _parse_iso_datetime(data.get("current_period_end"))
            existing_proj.cancel_at = _parse_iso_datetime(data.get("cancel_at"))
            existing_proj.last_event_timestamp = event_timestamp
            existing_proj.last_event_sequence = sequence_num
            existing_proj.updated_at = datetime.now(timezone.utc)
            projection = existing_proj
        else:
            # Create new subscription projection
            projection = SubscriptionProjection(
                tenant_id=tenant_id,
                external_subscription_id=external_sub_id,
                plan_id=incoming_plan_id,
                plan_version=incoming_plan_version,
                status=incoming_status,
                trial_end=_parse_iso_datetime(data.get("trial_end")),
                current_period_start=_parse_iso_datetime(data.get("current_period_start")),
                current_period_end=_parse_iso_datetime(data.get("current_period_end")),
                cancel_at=_parse_iso_datetime(data.get("cancel_at")),
                last_event_timestamp=event_timestamp,
                last_event_sequence=sequence_num,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(projection)

        # Update or create BillingAccount
        billing_account = (
            db.query(BillingAccount)
            .filter(BillingAccount.tenant_id == tenant_id)
            .first()
        )
        if not billing_account:
            billing_account = BillingAccount(
                tenant_id=tenant_id,
                flexprice_customer_id=customer_id,
                billing_state=incoming_status,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(billing_account)
        else:
            if customer_id and not billing_account.flexprice_customer_id:
                billing_account.flexprice_customer_id = customer_id
            billing_account.billing_state = incoming_status
            billing_account.updated_at = datetime.now(timezone.utc)

        # Sync legacy tenant tier field
        tenant.subscription_tier = incoming_plan_id
        db.add(tenant)

        # Recalculate EntitlementSnapshot
        cls._recalculate_entitlements(
            db=db,
            tenant_id=tenant_id,
            plan_id=incoming_plan_id,
            subscription_status=incoming_status,
            source_subscription_id=external_sub_id,
            custom_entitlements=data.get("entitlements"),
        )

        inbox_event.processing_status = "processed"
        inbox_event.processed_at = datetime.now(timezone.utc)
        inbox_event.error_message = None
        db.commit()

        return {
            "status": "processed",
            "subscription_id": external_sub_id,
            "tenant_id": tenant_id,
            "plan_id": incoming_plan_id,
            "subscription_status": incoming_status,
        }

    @classmethod
    def _recalculate_entitlements(
        cls,
        db: Session,
        tenant_id: int,
        plan_id: str,
        subscription_status: str,
        source_subscription_id: str,
        custom_entitlements: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Atomically project entitlement snapshots for the tenant based on current subscription."""
        # Catalog lookup or fallback to starter
        base_entitlements = PLAN_ENTITLEMENT_CATALOG.get(plan_id, PLAN_ENTITLEMENT_CATALOG["starter"])
        is_subscription_active = subscription_status in ("active", "trialing")

        # Merge any custom overrides from payload
        entitlements_to_apply = dict(base_entitlements)
        if custom_entitlements and isinstance(custom_entitlements, dict):
            for k, v in custom_entitlements.items():
                if isinstance(v, bool):
                    entitlements_to_apply[k] = ("boolean", str(v).lower())
                elif isinstance(v, (int, float)):
                    entitlements_to_apply[k] = ("numeric", str(v))
                else:
                    entitlements_to_apply[k] = ("string", str(v))

        existing_snapshots = {
            snap.entitlement_key: snap
            for snap in db.query(EntitlementSnapshot).filter(EntitlementSnapshot.tenant_id == tenant_id).all()
        }

        now = datetime.now(timezone.utc)

        for key, (val_type, val_str) in entitlements_to_apply.items():
            if key in existing_snapshots:
                snap = existing_snapshots[key]
                snap.value_type = val_type
                snap.value = val_str
                snap.is_active = is_subscription_active
                snap.source_subscription_id = source_subscription_id
                snap.updated_at = now
            else:
                snap = EntitlementSnapshot(
                    tenant_id=tenant_id,
                    entitlement_key=key,
                    value_type=val_type,
                    value=val_str,
                    source_subscription_id=source_subscription_id,
                    is_active=is_subscription_active,
                    created_at=now,
                    updated_at=now,
                )
                db.add(snap)


projection_service = SubscriptionProjectionService()
