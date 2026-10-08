"""Delegation policy and authoritative save guard for voice-first onboarding.

Enforces session-level delegation modes ('hands_off', 'guided', 'delegated', 'manual_only'),
per-domain write permissions, single-use cryptographic authorization nonces, control epoch
monotonicity, active-executor lease validity, and immutable audit logging.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from enum import Enum
from typing import Any, Dict, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.onboarding import OnboardingAuditLog, OnboardingPlan, OnboardingStep
from app.services.business_assistant.onboarding.errors import (
    DelegationRefusalError,
    InvalidNonceError,
    LeaseExpiredError,
    NonceAlreadyUsedError,
    NonceExpiredError,
    StaleControlEpochError,
)
from app.services.business_assistant.onboarding.plan_service import OnboardingPlanService


class DelegationMode(str, Enum):
    """Operational delegation mode for assistant onboarding interactions."""

    HANDS_OFF = "hands_off"      # Autonomous agent within safety gates
    GUIDED = "guided"            # Agent stages candidate values; user or nonce required to commit
    DELEGATED = "delegated"      # Routine steps saved by agent; high-impact domains require owner nonce
    MANUAL_ONLY = "manual_only"  # Agent writes strictly prohibited; user retains manual control


# Thread-safe in-memory tracking for consumed (single-use) nonces and issued metadata
_NONCE_LOCK = threading.Lock()
_CONSUMED_NONCES: Set[str] = set()
_ISSUED_NONCES: Dict[str, Dict[str, Any]] = {}


def _get_signing_key(override: Optional[str] = None) -> bytes:
    """Retrieve secret key for signing nonces."""
    key_str = override or getattr(settings, "SECRET_KEY", "onboarding-save-guard-secret-key-default")
    return key_str.encode("utf-8")


class DelegationSaveGuard:
    """Session-level delegation policy and authoritative mutation guard."""

    DEFAULT_NONCE_EXPIRY_SECONDS: int = 300  # 5 minutes per spec

    @classmethod
    def can_stage(
        cls,
        plan: OnboardingPlan,
        step: OnboardingStep,
        actor: str = "agent",
        mode: str = DelegationMode.DELEGATED.value,
    ) -> Tuple[bool, Optional[str]]:
        """Evaluate if fields can be staged for a given step.

        Returns (allowed: bool, refusal_reason: Optional[str]).
        """
        if mode == DelegationMode.MANUAL_ONLY.value and actor == "agent":
            return False, "Agent writes and staging are disabled in manual_only mode."
        return True, None

    @classmethod
    def can_save(
        cls,
        plan: OnboardingPlan,
        step: OnboardingStep,
        actor: str = "agent",
        mode: str = DelegationMode.DELEGATED.value,
        is_edit_mode: bool = False,
        is_publish: bool = False,
        nonce_present: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Evaluate whether a live save is permissible under the current delegation policy.

        Domain rules per Spec Section 12 & 15:
        - Domain 1 (Business Identity): can stage; owner must authorize live save.
        - Domain 2 (Locations/Timezone): can stage; owner must authorize live save.
        - Domain 3 (Services):
            * Creation mode: agent can save in delegated/hands_off mode.
            * Edit mode: modifying existing service requires explicit owner authorization.
        - Domain 4 (Providers), 5 (Hours), 6 (General Settings):
            * delegated/hands_off: agent can save.
            * guided: requires user confirmation / nonce.
        - Domain 7 (Website):
            * Draft website: agent can create/save draft.
            * PUBLISH: requires explicit owner confirmation and nonce.
        - manual_only:
            * Agent writes prohibited.

        Returns (allowed: bool, refusal_reason: Optional[str]).
        """
        # 1. Manual-only mode
        if mode == DelegationMode.MANUAL_ONLY.value and actor == "agent":
            return False, "Agent saves are prohibited in manual_only mode. User must perform manual action."

        # 2. User direct manual action
        if actor == "user":
            if step.domain == 7 and is_publish:
                if not nonce_present:
                    return False, "Website publication requires an explicit authorization nonce."
            return True, None

        # 3. Agent actions across modes
        # Guided mode: agent can stage, but all live saves require owner authorization nonce
        if mode == DelegationMode.GUIDED.value:
            if not nonce_present:
                return False, f"In guided mode, saving step '{step.step_id}' requires an authorization nonce."
            return True, None

        # Delegated and Hands-Off modes
        if mode in (DelegationMode.DELEGATED.value, DelegationMode.HANDS_OFF.value):
            # Domain 1: Business Identity
            if step.domain == 1:
                if not nonce_present:
                    return (
                        False,
                        "Domain 1 (Business Identity) live save requires explicit owner authorization nonce.",
                    )
                return True, None

            # Domain 2: Locations & Timezone
            if step.domain == 2:
                if not nonce_present:
                    return (
                        False,
                        "Domain 2 (Locations and Timezone) live save requires explicit owner authorization nonce.",
                    )
                return True, None

            # Domain 3: Services Catalog
            if step.domain == 3:
                if is_edit_mode:
                    if not nonce_present:
                        return (
                            False,
                            "Editing existing service in Domain 3 requires explicit owner authorization nonce.",
                        )
                    return True, None
                # Service creation is allowed directly in delegated/hands_off mode
                return True, None

            # Domain 7: Website
            if step.domain == 7:
                if is_publish:
                    if not nonce_present:
                        return (
                            False,
                            "Publishing website in Domain 7 requires explicit owner confirmation and authorization nonce.",
                        )
                    return True, None
                # Draft creation/save is allowed
                return True, None

            # Routine domains: 4 (Providers), 5 (Hours), 6 (Settings), 8 (Summary)
            return True, None

        return False, f"Unrecognized delegation mode '{mode}'."

    @classmethod
    def generate_save_nonce(
        cls,
        tenant_id: int,
        user_id: int,
        plan_id: int,
        step_id: str,
        action: str = "save",
        expires_in_seconds: int = DEFAULT_NONCE_EXPIRY_SECONDS,
        db: Optional[Session] = None,
        secret_key: Optional[str] = None,
    ) -> str:
        """Generate a cryptographically signed, single-use, tenant-scoped authorization nonce."""
        now = int(time.time())
        expires_at = now + expires_in_seconds
        nonce_id = secrets.token_hex(16)

        payload_dict = {
            "nonce_id": nonce_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "plan_id": plan_id,
            "step_id": step_id,
            "action": action,
            "exp": expires_at,
            "iat": now,
        }
        payload_bytes = json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")

        key = _get_signing_key(secret_key)
        sig = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
        token = f"{payload_b64}.{sig}"

        with _NONCE_LOCK:
            _ISSUED_NONCES[nonce_id] = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "plan_id": plan_id,
                "step_id": step_id,
                "action": action,
                "expires_at": expires_at,
                "used": False,
            }

        if db:
            audit = OnboardingAuditLog(
                tenant_id=tenant_id,
                plan_id=plan_id,
                action="nonce_generated",
                actor="system",
                details={
                    "step_id": step_id,
                    "action_scope": action,
                    "expires_in_seconds": expires_in_seconds,
                    "expires_at": expires_at,
                },
            )
            db.add(audit)
            db.commit()

        return token

    @classmethod
    def validate_save_nonce(
        cls,
        nonce: str,
        tenant_id: int,
        plan_id: Optional[int] = None,
        step_id: Optional[str] = None,
        action: Optional[str] = None,
        db: Optional[Session] = None,
        secret_key: Optional[str] = None,
    ) -> bool:
        """Validate and consume a single-use authorization nonce.

        Raises InvalidNonceError, NonceExpiredError, or NonceAlreadyUsedError if validation fails.
        """
        if not nonce or not isinstance(nonce, str) or "." not in nonce:
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, "Malformed nonce token.")
            raise InvalidNonceError("Malformed authorization nonce token.")

        parts = nonce.strip().split(".")
        if len(parts) != 2:
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, "Malformed nonce token structure.")
            raise InvalidNonceError("Malformed authorization nonce structure.")

        payload_b64, sig = parts
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        try:
            payload_bytes = base64.urlsafe_b64decode(padded)
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception as exc:
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, f"Failed decoding nonce: {exc}")
            raise InvalidNonceError(f"Failed to decode authorization nonce: {exc}") from exc

        # Verify signature
        key = _get_signing_key(secret_key)
        expected_sig = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, "Invalid nonce signature.")
            raise InvalidNonceError("Invalid authorization nonce signature.")

        # Expiry check
        now = int(time.time())
        exp = payload.get("exp", 0)
        if exp < now:
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, f"Nonce expired at {exp}, current {now}.")
            raise NonceExpiredError(
                f"Authorization nonce has expired (expired at {exp}, current {now})."
            )

        # Tenant scoping
        if payload.get("tenant_id") != tenant_id:
            cls._log_audit_refusal(
                db,
                tenant_id,
                plan_id,
                step_id,
                f"Tenant scope mismatch: token tenant {payload.get('tenant_id')} != expected {tenant_id}.",
            )
            raise InvalidNonceError("Authorization nonce tenant scope mismatch.")

        # Plan scoping if provided
        if plan_id is not None and payload.get("plan_id") != plan_id:
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, "Plan scope mismatch.")
            raise InvalidNonceError("Authorization nonce plan scope mismatch.")

        # Step scoping if provided
        if step_id is not None and payload.get("step_id") != step_id:
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, "Step scope mismatch.")
            raise InvalidNonceError("Authorization nonce step scope mismatch.")

        # Action scoping if provided
        if action is not None and payload.get("action") != action:
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, "Action scope mismatch.")
            raise InvalidNonceError("Authorization nonce action scope mismatch.")

        # Single-use enforcement
        nonce_id = payload.get("nonce_id")
        if not nonce_id:
            cls._log_audit_refusal(db, tenant_id, plan_id, step_id, "Missing nonce_id identifier.")
            raise InvalidNonceError("Authorization nonce lacks identifier.")

        with _NONCE_LOCK:
            if nonce_id in _CONSUMED_NONCES:
                cls._log_audit_refusal(db, tenant_id, plan_id, step_id, "Nonce already consumed.")
                raise NonceAlreadyUsedError("Authorization nonce has already been consumed (single-use).")
            _CONSUMED_NONCES.add(nonce_id)
            if nonce_id in _ISSUED_NONCES:
                _ISSUED_NONCES[nonce_id]["used"] = True

        if db and plan_id:
            audit = OnboardingAuditLog(
                tenant_id=tenant_id,
                plan_id=plan_id,
                action="nonce_validated",
                actor="system",
                details={
                    "step_id": payload.get("step_id"),
                    "action": payload.get("action"),
                    "nonce_id": nonce_id,
                },
            )
            db.add(audit)
            db.commit()

        return True

    @classmethod
    def authorize_save(
        cls,
        db: Session,
        plan: OnboardingPlan,
        step: OnboardingStep,
        actor: str = "agent",
        mode: str = DelegationMode.DELEGATED.value,
        control_epoch: Optional[int] = None,
        lease_token: Optional[str] = None,
        nonce: Optional[str] = None,
        is_edit_mode: bool = False,
        is_publish: bool = False,
        user_role: Optional[str] = None,
    ) -> None:
        """Validate all delegation gates, control epoch, lease, and authorization nonce before saving.

        Raises:
            StaleControlEpochError: If control epoch is older than plan.
            LeaseExpiredError: If active executor lease does not match.
            DelegationRefusalError: If policy forbids save or required nonce is absent.
            InvalidNonceError / NonceExpiredError / NonceAlreadyUsedError: If nonce fails validation.
        """
        # 1. Validate epoch
        if control_epoch is not None:
            OnboardingPlanService.validate_control_epoch(plan, control_epoch)

        # 2. Validate lease
        if lease_token is not None:
            OnboardingPlanService.validate_lease(plan, lease_token)

        # 3. Check delegation policy
        has_nonce = bool(nonce and nonce.strip())
        allowed, reason = cls.can_save(
            plan=plan,
            step=step,
            actor=actor,
            mode=mode,
            is_edit_mode=is_edit_mode,
            is_publish=is_publish,
            nonce_present=has_nonce,
        )

        if not allowed:
            audit = OnboardingAuditLog(
                tenant_id=plan.tenant_id,
                plan_id=plan.id,
                action="authorization_refused",
                actor=actor,
                details={
                    "step_id": step.step_id,
                    "domain": step.domain,
                    "mode": mode,
                    "is_edit_mode": is_edit_mode,
                    "is_publish": is_publish,
                    "reason": reason,
                },
            )
            db.add(audit)
            db.commit()
            raise DelegationRefusalError(
                message=reason or "Save refused by delegation guard.",
                domain=step.domain,
                step_id=step.step_id,
                reason=reason,
            )

        # 4. If nonce was provided, validate and consume it
        if has_nonce:
            cls.validate_save_nonce(
                nonce=nonce.strip(),
                tenant_id=plan.tenant_id,
                plan_id=plan.id,
                step_id=step.step_id,
                action="publish" if is_publish else "save",
                db=db,
            )

        # 5. Record save attempt audit log
        audit = OnboardingAuditLog(
            tenant_id=plan.tenant_id,
            plan_id=plan.id,
            action="save_attempt",
            actor=actor,
            details={
                "step_id": step.step_id,
                "domain": step.domain,
                "mode": mode,
                "is_edit_mode": is_edit_mode,
                "is_publish": is_publish,
            },
        )
        db.add(audit)
        db.commit()

    @classmethod
    def _log_audit_refusal(
        cls,
        db: Optional[Session],
        tenant_id: int,
        plan_id: Optional[int],
        step_id: Optional[str],
        reason: str,
    ) -> None:
        """Internal helper to log authorization refusal into OnboardingAuditLog."""
        if db and plan_id:
            audit = OnboardingAuditLog(
                tenant_id=tenant_id,
                plan_id=plan_id,
                action="authorization_refused",
                actor="system",
                details={"step_id": step_id, "reason": reason},
            )
            db.add(audit)
            db.commit()
