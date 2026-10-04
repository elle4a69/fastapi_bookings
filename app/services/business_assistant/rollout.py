"""Staged rollout lifecycle and feature flag gating for the native Business Assistant."""

from __future__ import annotations

from enum import Enum
import logging
from typing import Optional, Set

from fastapi import HTTPException, status
from pydantic import BaseModel

from ...core.config import settings
from ...models.tenant import Tenant
from ...models.user import User

logger = logging.getLogger(__name__)


class RolloutStage(str, Enum):
    """Authoritative lifecycle rollout stages for the native Business Assistant."""

    DISABLED = "disabled"
    INTERNAL_SYNTHETIC = "internal_synthetic"
    OWNER_STAGING = "owner_staging"
    ENABLED = "enabled"


class RolloutAccessDecision(BaseModel):
    """Structured decision explaining rollout admission or clean fallback."""

    allowed: bool
    stage: str
    code: str
    message: str


class BusinessAssistantRolloutRestrictionError(HTTPException):
    """Raised when Business Assistant access is disabled or restricted by rollout policy.

    Degrades cleanly with descriptive codes, safe HTTP status (503 for disabled,
    403 for role/tenant staging boundary restrictions), and structured error payloads.
    """

    def __init__(
        self,
        *,
        stage: str,
        code: str,
        message: str,
        status_code: int = status.HTTP_403_FORBIDDEN,
    ) -> None:
        self.stage = stage
        self.code = code
        self.message = message
        # Format detail as dict compatible with app/main.py http_exception_handler
        detail_payload = {
            "error_code": code,
            "code": code,
            "message": message,
            "stage": stage,
        }
        super().__init__(
            status_code=status_code,
            detail=detail_payload,
            headers={
                "X-Rollout-Stage": stage,
                "X-Rollout-Code": code,
            },
        )

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (stage: {self.stage})"


SYNTHETIC_SUBDOMAIN_PREFIXES = ("test-", "synthetic-", "internal-", "test_")
SYNTHETIC_SUBDOMAIN_SUFFIXES = ("-test", "-synthetic")


def is_synthetic_tenant(tenant: Tenant, allowlisted_ids: Optional[Set[int]] = None) -> bool:
    """Determine whether a tenant is an authorized internal synthetic/test tenant."""
    if tenant is None:
        return False

    synthetic_ids = allowlisted_ids if allowlisted_ids is not None else set(settings.BUSINESS_ASSISTANT_SYNTHETIC_TENANT_IDS)
    if tenant.id and tenant.id in synthetic_ids:
        return True

    # Explicit synthetic attribute if present
    if getattr(tenant, "is_synthetic", False) is True:
        return True

    subdomain = (tenant.subdomain or "").strip().lower()
    if any(subdomain.startswith(prefix) for prefix in SYNTHETIC_SUBDOMAIN_PREFIXES):
        return True
    if any(subdomain.endswith(suffix) for suffix in SYNTHETIC_SUBDOMAIN_SUFFIXES):
        return True

    name = (tenant.name or "").strip().lower()
    if name.startswith(("test-", "synthetic-", "internal-", "test ")):
        return True
    if "[synthetic]" in name or "synthetic tenant" in name:
        return True

    return False


def is_staging_tenant(tenant: Tenant, allowlisted_ids: Optional[Set[int]] = None) -> bool:
    """Determine whether a tenant is permitted in owner-only staging rollout."""
    if tenant is None:
        return False

    # Synthetic tenants are always eligible for staging tests
    if is_synthetic_tenant(tenant, allowlisted_ids=allowlisted_ids):
        return True

    staging_ids = allowlisted_ids if allowlisted_ids is not None else set(settings.BUSINESS_ASSISTANT_ALLOWLISTED_TENANT_IDS)
    if tenant.id and tenant.id in staging_ids:
        return True

    subdomain = (tenant.subdomain or "").strip().lower()
    if "staging" in subdomain:
        return True

    # In development/test/staging environments, allowlisted or local tenants are eligible
    if settings.APP_ENV in ("staging", "development", "test"):
        return True

    return False


class RolloutGate:
    """Evaluates and enforces staged rollout lifecycle transitions for Business Assistant."""

    @classmethod
    def current_stage(cls, stage_override: Optional[str] = None) -> RolloutStage:
        """Resolve the effective rollout stage from override or application settings."""
        stage_str = (stage_override or settings.BUSINESS_ASSISTANT_ROLLOUT_STAGE).strip().lower()
        try:
            return RolloutStage(stage_str)
        except ValueError:
            logger.warning(
                "Unrecognized Business Assistant rollout stage '%s'; defaulting to disabled.",
                stage_str,
            )
            return RolloutStage.DISABLED

    @classmethod
    def check_access(
        cls,
        *,
        tenant: Optional[Tenant],
        user: Optional[User],
        stage_override: Optional[str] = None,
        raise_exception: bool = True,
    ) -> RolloutAccessDecision:
        """Evaluate access against the current rollout stage.

        Stages:
        - disabled: Clean service unavailable (503) for all callers.
        - internal_synthetic: Bounded strictly to synthetic/test tenants.
        - owner_staging: Accessible only by tenant owners in staging/allowlisted tenants.
        - enabled: Fully active for authorized tenant users.
        """
        stage = cls.current_stage(stage_override)

        # 1. Stage: DISABLED -> Clean 503 fallback
        if stage == RolloutStage.DISABLED:
            decision = RolloutAccessDecision(
                allowed=False,
                stage=stage.value,
                code="BUSINESS_ASSISTANT_DISABLED",
                message="Business Assistant is currently disabled.",
            )
            if raise_exception:
                raise BusinessAssistantRolloutRestrictionError(
                    stage=stage.value,
                    code=decision.code,
                    message=decision.message,
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return decision

        # 2. Stage: INTERNAL_SYNTHETIC -> Bounded strictly to synthetic tenants
        if stage == RolloutStage.INTERNAL_SYNTHETIC:
            if not is_synthetic_tenant(tenant):
                decision = RolloutAccessDecision(
                    allowed=False,
                    stage=stage.value,
                    code="SYNTHETIC_TENANTS_ONLY",
                    message="Business Assistant is currently restricted to internal synthetic tenants.",
                )
                if raise_exception:
                    raise BusinessAssistantRolloutRestrictionError(
                        stage=stage.value,
                        code=decision.code,
                        message=decision.message,
                        status_code=status.HTTP_403_FORBIDDEN,
                    )
                return decision

            return RolloutAccessDecision(
                allowed=True,
                stage=stage.value,
                code="ACCESS_GRANTED",
                message="Access granted under internal synthetic tenant stage.",
            )

        # 3. Stage: OWNER_STAGING -> Accessible only by tenant owners in staging/allowlisted tenants
        if stage == RolloutStage.OWNER_STAGING:
            if not is_staging_tenant(tenant):
                decision = RolloutAccessDecision(
                    allowed=False,
                    stage=stage.value,
                    code="STAGING_TENANTS_ONLY",
                    message="Business Assistant is currently restricted to staging or allowlisted tenants.",
                )
                if raise_exception:
                    raise BusinessAssistantRolloutRestrictionError(
                        stage=stage.value,
                        code=decision.code,
                        message=decision.message,
                        status_code=status.HTTP_403_FORBIDDEN,
                    )
                return decision

            # Role check: Owner only
            user_role = (getattr(user, "role", None) or "").strip().lower()
            if user_role != "owner":
                decision = RolloutAccessDecision(
                    allowed=False,
                    stage=stage.value,
                    code="OWNER_ROLE_REQUIRED",
                    message="Business Assistant in staging is restricted to tenant owners.",
                )
                if raise_exception:
                    raise BusinessAssistantRolloutRestrictionError(
                        stage=stage.value,
                        code=decision.code,
                        message=decision.message,
                        status_code=status.HTTP_403_FORBIDDEN,
                    )
                return decision

            return RolloutAccessDecision(
                allowed=True,
                stage=stage.value,
                code="ACCESS_GRANTED",
                message="Access granted under owner staging stage.",
            )

        # 4. Stage: ENABLED -> Fully active for authorized tenant users
        if stage == RolloutStage.ENABLED:
            return RolloutAccessDecision(
                allowed=True,
                stage=stage.value,
                code="ACCESS_GRANTED",
                message="Access granted under fully enabled rollout stage.",
            )

        # Default fallback safety
        decision = RolloutAccessDecision(
            allowed=False,
            stage=stage.value,
            code="ROLLOUT_RESTRICTED",
            message="Business Assistant is restricted under the current rollout policy.",
        )
        if raise_exception:
            raise BusinessAssistantRolloutRestrictionError(
                stage=stage.value,
                code=decision.code,
                message=decision.message,
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return decision

    @classmethod
    def is_allowed(
        cls,
        *,
        tenant: Optional[Tenant],
        user: Optional[User],
        stage_override: Optional[str] = None,
    ) -> bool:
        """Check if access is permitted without raising an exception."""
        decision = cls.check_access(
            tenant=tenant,
            user=user,
            stage_override=stage_override,
            raise_exception=False,
        )
        return decision.allowed

    @classmethod
    def enforce(
        cls,
        *,
        tenant: Optional[Tenant],
        user: Optional[User],
        stage_override: Optional[str] = None,
    ) -> RolloutAccessDecision:
        """Enforce rollout policy, raising BusinessAssistantRolloutRestrictionError if restricted."""
        return cls.check_access(
            tenant=tenant,
            user=user,
            stage_override=stage_override,
            raise_exception=True,
        )
