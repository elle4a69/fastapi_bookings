"""Authoritative Server-Side Entitlement and Quota Guard (WP3).

Enforces server-side feature access control, state and metered quota enforcement,
expiring platform grants, and tenant isolation.
Fails closed: if no active snapshot or grant exists, access is forbidden with 403.
Feature flags may restrict rollout; they may NEVER grant unpurchased features.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant, get_db
from app.models.location import Location
from app.models.platform_billing import (
    EntitlementSnapshot,
    PlatformEntitlementGrant,
    SubscriptionProjection,
    UsageEventOutbox,
)
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.services.platform_billing.metering_service import UsageMeteringService
from app.services.platform_billing.projection_service import PLAN_ENTITLEMENT_CATALOG

logger = logging.getLogger(__name__)

# Canonical stable entitlement catalogue keys
ENTITLEMENT_ASSISTANT_ENABLED = "assistant.enabled"
ENTITLEMENT_ASSISTANT_MONTHLY_RUNS = "assistant.monthly_runs"
ENTITLEMENT_SMS_ENABLED = "sms.enabled"
ENTITLEMENT_SMS_MONTHLY_MESSAGES = "sms.monthly_outbound_messages"
ENTITLEMENT_PROVIDERS_MAX = "providers.max"
ENTITLEMENT_LOCATIONS_MAX = "locations.max"
ENTITLEMENT_API_ENABLED = "api.enabled"

# Bidirectional alias mapping for backwards compatibility
ENTITLEMENT_ALIASES: Dict[str, str] = {
    "max_locations": ENTITLEMENT_LOCATIONS_MAX,
    ENTITLEMENT_LOCATIONS_MAX: "max_locations",
    "locations": ENTITLEMENT_LOCATIONS_MAX,
    "sms_monthly_quota": ENTITLEMENT_SMS_MONTHLY_MESSAGES,
    ENTITLEMENT_SMS_MONTHLY_MESSAGES: "sms_monthly_quota",
    "max_staff": ENTITLEMENT_PROVIDERS_MAX,
    ENTITLEMENT_PROVIDERS_MAX: "max_staff",
    "providers": ENTITLEMENT_PROVIDERS_MAX,
    "multiple_providers": ENTITLEMENT_PROVIDERS_MAX,
    "ai_voice_enabled": ENTITLEMENT_ASSISTANT_ENABLED,
    ENTITLEMENT_ASSISTANT_ENABLED: "ai_voice_enabled",
    "sms_assistant": ENTITLEMENT_SMS_ENABLED,
    "sms": ENTITLEMENT_SMS_ENABLED,
    ENTITLEMENT_SMS_ENABLED: "sms_assistant",
}

# Quota meter keys mapping
QUOTA_METER_MAPPING: Dict[str, List[str]] = {
    ENTITLEMENT_SMS_MONTHLY_MESSAGES: [
        "sms_outbound",
        "sms.monthly_outbound_messages",
        "sms_monthly_quota",
    ],
    "sms_monthly_quota": [
        "sms_outbound",
        "sms.monthly_outbound_messages",
        "sms_monthly_quota",
    ],
    ENTITLEMENT_ASSISTANT_MONTHLY_RUNS: [
        "assistant_runs",
        "assistant.monthly_runs",
    ],
}


class EntitlementRequiredError(HTTPException):
    """Raised when a tenant attempts to use a feature they are not entitled to."""

    def __init__(self, entitlement_key: str, message: Optional[str] = None):
        detail = {
            "error": "entitlement_required",
            "entitlement_key": entitlement_key,
            "message": message
            or f"Access to feature requires entitlement '{entitlement_key}', which is not active on your plan.",
        }
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class QuotaExceededError(HTTPException):
    """Raised when a tenant exceeds their allotted quota for a feature."""

    def __init__(
        self,
        quota_key: str,
        current_usage: int,
        limit: int,
        requested: int = 1,
        message: Optional[str] = None,
    ):
        detail = {
            "error": "quota_exceeded",
            "quota_key": quota_key,
            "current_usage": current_usage,
            "limit": limit,
            "requested": requested,
            "message": message
            or f"Quota exceeded for '{quota_key}'. Current usage: {current_usage}, limit: {limit}, requested: {requested}.",
        }
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_value(value_type: str, raw_val: Any) -> Any:
    """Parse raw string/stored value into typed Python object."""
    if raw_val is None:
        return None
    vt = value_type.lower()
    if vt == "boolean":
        return str(raw_val).strip().lower() in ("true", "1", "yes", "t")
    elif vt == "numeric":
        try:
            return int(float(str(raw_val).strip()))
        except (ValueError, TypeError):
            return 0
    return str(raw_val)


class EntitlementGuardService:
    """Service for resolving, evaluating, and enforcing entitlements and quotas."""

    @classmethod
    def get_effective_entitlement(
        cls,
        db: Session,
        tenant_id: int,
        entitlement_key: str,
    ) -> Optional[Tuple[str, Any]]:
        """Resolve effective entitlement tuple (value_type, parsed_value) for a tenant.

        Priority hierarchy:
        1. Active PlatformEntitlementGrant (not revoked, not expired).
        2. Active EntitlementSnapshot derived from subscription.
        3. Aliased key in PlatformEntitlementGrant / EntitlementSnapshot.
        4. Default plan catalog fallback if tenant has subscription_tier and no opposing projection.
        5. Fails closed (returns None).
        """
        now = datetime.now(timezone.utc)
        keys_to_check = [entitlement_key]
        if entitlement_key in ENTITLEMENT_ALIASES:
            alias = ENTITLEMENT_ALIASES[entitlement_key]
            if alias not in keys_to_check:
                keys_to_check.append(alias)

        # 1. Platform-authorized explicit grants (overrides)
        for key in keys_to_check:
            grant = (
                db.query(PlatformEntitlementGrant)
                .filter(
                    PlatformEntitlementGrant.tenant_id == tenant_id,
                    PlatformEntitlementGrant.entitlement_key == key,
                    PlatformEntitlementGrant.is_revoked == False,  # noqa: E712
                )
                .order_by(PlatformEntitlementGrant.id.desc())
                .first()
            )
            if grant:
                exp = _as_utc(grant.expires_at)
                if exp is None or exp > now:
                    return (grant.value_type, _parse_value(grant.value_type, grant.granted_value))
                else:
                    logger.debug("Platform grant %s for tenant %s is expired.", grant.id, tenant_id)

        # 2. Local subscription projection status check
        projection = (
            db.query(SubscriptionProjection)
            .filter(SubscriptionProjection.tenant_id == tenant_id)
            .order_by(SubscriptionProjection.id.desc())
            .first()
        )
        if projection and projection.status in ("cancelled", "terminated", "past_due"):
            # Subscription is cancelled or past due and no override grant was found -> fails closed!
            logger.info(
                "Tenant %s subscription projection is %s; failing closed for %s.",
                tenant_id,
                projection.status,
                entitlement_key,
            )
            return None

        # 3. Entitlement snapshots
        for key in keys_to_check:
            snapshot = (
                db.query(EntitlementSnapshot)
                .filter(
                    EntitlementSnapshot.tenant_id == tenant_id,
                    EntitlementSnapshot.entitlement_key == key,
                )
                .first()
            )
            if snapshot:
                if snapshot.is_active:
                    snap_exp = _as_utc(snapshot.expires_at)
                    if snap_exp is None or snap_exp > now:
                        return (snapshot.value_type, _parse_value(snapshot.value_type, snapshot.value))
                # Snapshot exists but is inactive or expired
                return None

        # 4. Default plan catalog fallback (for tenants before first billing sync or in demo)
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.status != "suspended":
            tier = (tenant.subscription_tier or "starter").lower()
            plan_catalog = PLAN_ENTITLEMENT_CATALOG.get(tier, PLAN_ENTITLEMENT_CATALOG.get("starter", {}))
            for key in keys_to_check:
                if key in plan_catalog:
                    val_type, val_str = plan_catalog[key]
                    return (val_type, _parse_value(val_type, val_str))

        # 5. Fails closed
        return None

    @classmethod
    def has_entitlement(
        cls,
        db: Session,
        tenant_id: int,
        entitlement_key: str,
        required_value: Any = True,
    ) -> bool:
        """Check whether tenant satisfies the given entitlement requirement."""
        resolved = cls.get_effective_entitlement(db, tenant_id, entitlement_key)
        if resolved is None:
            return False

        value_type, parsed_value = resolved

        if value_type.lower() == "boolean":
            return bool(parsed_value) is bool(required_value)
        elif value_type.lower() == "numeric":
            if isinstance(required_value, (int, float)):
                return parsed_value >= required_value
            return parsed_value > 0
        else:
            return str(parsed_value) == str(required_value)

    @classmethod
    def get_current_billing_period(
        cls,
        db: Session,
        tenant_id: int,
    ) -> Tuple[datetime, Optional[datetime]]:
        """Get the start and end of the current billing cycle for usage metering."""
        now = datetime.now(timezone.utc)
        projection = (
            db.query(SubscriptionProjection)
            .filter(
                SubscriptionProjection.tenant_id == tenant_id,
                SubscriptionProjection.status.in_(["active", "trialing"]),
            )
            .order_by(SubscriptionProjection.id.desc())
            .first()
        )
        if projection and projection.current_period_start:
            return (projection.current_period_start, projection.current_period_end)

        # Default fallback to start of current UTC calendar month
        first_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        return (first_of_month, None)

    @classmethod
    def get_current_usage(
        cls,
        db: Session,
        tenant_id: int,
        quota_key: str,
    ) -> int:
        """Calculate current period usage or state count for a given quota key."""
        # 1. State-based quotas (active entity counts)
        if quota_key in (ENTITLEMENT_PROVIDERS_MAX, "max_staff", "providers", "multiple_providers"):
            return (
                db.query(Provider)
                .filter(
                    Provider.tenant_id == tenant_id,
                    Provider.deleted_at == None,  # noqa: E711
                    Provider.active == True,  # noqa: E712
                )
                .count()
            )

        if quota_key in (ENTITLEMENT_LOCATIONS_MAX, "max_locations", "locations"):
            return (
                db.query(Location)
                .filter(
                    Location.tenant_id == tenant_id,
                    Location.active == True,  # noqa: E712
                )
                .count()
            )

        # 2. Consumption-based metered quotas
        meter_keys = QUOTA_METER_MAPPING.get(quota_key)
        if not meter_keys:
            # Check aliases
            alias = ENTITLEMENT_ALIASES.get(quota_key)
            if alias:
                meter_keys = QUOTA_METER_MAPPING.get(alias)

        if meter_keys:
            period_start, period_end = cls.get_current_billing_period(db, tenant_id)
            query = db.query(func.coalesce(func.sum(UsageEventOutbox.quantity), 0)).filter(
                UsageEventOutbox.tenant_id == tenant_id,
                UsageEventOutbox.meter_key.in_(meter_keys),
                UsageEventOutbox.occurred_at >= period_start,
            )
            if period_end:
                query = query.filter(UsageEventOutbox.occurred_at <= period_end)
            return int(query.scalar() or 0)

        return 0

    @classmethod
    def check_quota(
        cls,
        db: Session,
        tenant_id: int,
        quota_key: str,
        requested_quantity: int = 1,
        raise_exception: bool = True,
    ) -> bool:
        """Verify whether tenant has sufficient remaining quota for the requested operation.

        Args:
            db: Database session.
            tenant_id: Tenant ID.
            quota_key: Quota or entitlement limit key.
            requested_quantity: Units about to be consumed.
            raise_exception: If True, raises QuotaExceededError or EntitlementRequiredError.

        Returns:
            bool: True if allowed.

        Raises:
            EntitlementRequiredError: If no quota entitlement is configured (fails closed).
            QuotaExceededError: If current_usage + requested_quantity > limit.
        """
        resolved = cls.get_effective_entitlement(db, tenant_id, quota_key)
        if resolved is None:
            if raise_exception:
                raise EntitlementRequiredError(
                    entitlement_key=quota_key,
                    message=f"No active quota entitlement defined for '{quota_key}'.",
                )
            return False

        _, limit = resolved
        if not isinstance(limit, (int, float)):
            limit = int(float(str(limit)))

        current_usage = cls.get_current_usage(db, tenant_id, quota_key)

        if current_usage + requested_quantity > limit:
            if raise_exception:
                raise QuotaExceededError(
                    quota_key=quota_key,
                    current_usage=current_usage,
                    limit=limit,
                    requested=requested_quantity,
                )
            return False

        return True

    @classmethod
    def record_usage_with_deduplication(
        cls,
        db: Session,
        tenant_id: int,
        meter_key: str,
        quantity: int = 1,
        idempotency_key: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> UsageEventOutbox:
        """Record metered consumption with idempotency deduplication."""
        return UsageMeteringService.record_usage(
            db=db,
            tenant_id=tenant_id,
            meter_key=meter_key,
            quantity=quantity,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
        )

    # --- Platform Grant Management ---

    @classmethod
    def create_platform_grant(
        cls,
        db: Session,
        tenant_id: int,
        entitlement_key: str,
        granted_value: str,
        value_type: str = "boolean",
        expires_at: Optional[datetime] = None,
        reason: str = "Platform-authorized grant",
        granted_by_user_id: Optional[int] = None,
    ) -> PlatformEntitlementGrant:
        """Create an explicit platform-authorized entitlement grant override."""
        grant = PlatformEntitlementGrant(
            tenant_id=tenant_id,
            entitlement_key=entitlement_key,
            value_type=value_type,
            granted_value=str(granted_value),
            expires_at=expires_at,
            reason=reason,
            granted_by_user_id=granted_by_user_id,
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(grant)
        db.commit()
        db.refresh(grant)
        return grant

    @classmethod
    def revoke_platform_grant(
        cls,
        db: Session,
        grant_id: int,
        tenant_id: Optional[int] = None,
    ) -> bool:
        """Revoke an active platform entitlement grant."""
        query = db.query(PlatformEntitlementGrant).filter(PlatformEntitlementGrant.id == grant_id)
        if tenant_id is not None:
            query = query.filter(PlatformEntitlementGrant.tenant_id == tenant_id)
        grant = query.first()
        if not grant:
            return False
        grant.is_revoked = True
        grant.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True

    @classmethod
    def list_platform_grants(
        cls,
        db: Session,
        tenant_id: int,
    ) -> List[PlatformEntitlementGrant]:
        """List all platform grants for a tenant."""
        return (
            db.query(PlatformEntitlementGrant)
            .filter(PlatformEntitlementGrant.tenant_id == tenant_id)
            .order_by(PlatformEntitlementGrant.id.desc())
            .all()
        )


entitlement_guard = EntitlementGuardService()


def require_entitlement(entitlement_key: str, required_value: Any = True):
    """FastAPI dependency to enforce an active entitlement on an endpoint."""

    def dependency(
        tenant: Tenant = Depends(get_current_tenant),
        db: Session = Depends(get_db),
    ) -> bool:
        if not EntitlementGuardService.has_entitlement(
            db=db,
            tenant_id=tenant.id,
            entitlement_key=entitlement_key,
            required_value=required_value,
        ):
            raise EntitlementRequiredError(
                entitlement_key=entitlement_key,
                message=f"Access requires active entitlement '{entitlement_key}', which is not available on your subscription.",
            )
        return True

    return dependency


def require_quota(quota_key: str, requested_quantity: int = 1):
    """FastAPI dependency to enforce that a tenant has sufficient quota before starting an action."""

    def dependency(
        tenant: Tenant = Depends(get_current_tenant),
        db: Session = Depends(get_db),
    ) -> bool:
        EntitlementGuardService.check_quota(
            db=db,
            tenant_id=tenant.id,
            quota_key=quota_key,
            requested_quantity=requested_quantity,
            raise_exception=True,
        )
        return True

    return dependency
