"""Error hierarchy for voice-first onboarding and visible in-app assistance.

Defines structured exception types for control epoch stale rejection, lease expiry,
form validation errors, and autosave staging guard conflicts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class OnboardingError(Exception):
    """Base exception for all onboarding and form automation failures."""

    def __init__(
        self,
        message: str,
        code: str = "ONBOARDING_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for receipts and audit logging."""
        return {
            "error_code": self.code,
            "error_message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r}, details={self.details!r})"


class StaleControlEpochError(OnboardingError):
    """Raised when an incoming command carries an older control epoch than the current session.

    Indicates manual takeover or higher-priority user interaction has superseded the command.
    """

    def __init__(
        self,
        message: str = "Command rejected: control epoch is stale due to manual takeover or epoch advancement.",
        expected_epoch: Optional[int] = None,
        received_epoch: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = dict(details or {})
        if expected_epoch is not None:
            err_details["expected_epoch"] = expected_epoch
        if received_epoch is not None:
            err_details["received_epoch"] = received_epoch
        super().__init__(
            message=message,
            code="STALE_CONTROL_EPOCH",
            details=err_details,
        )
        self.expected_epoch = expected_epoch
        self.received_epoch = received_epoch


class LeaseExpiredError(OnboardingError):
    """Raised when the active executor lease token has expired or belongs to an inactive tab."""

    def __init__(
        self,
        message: str = "Command rejected: active executor lease has expired or is invalid.",
        lease_token: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = dict(details or {})
        if lease_token:
            err_details["lease_token"] = lease_token
        super().__init__(
            message=message,
            code="LEASE_EXPIRED",
            details=err_details,
        )
        self.lease_token = lease_token


class FormValidationError(OnboardingError):
    """Raised when field values fail form validation rules or schema constraints."""

    def __init__(
        self,
        message: str = "Form validation failed for one or more fields.",
        field_errors: Optional[Dict[str, List[str]]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = dict(details or {})
        if field_errors:
            err_details["field_errors"] = field_errors
        super().__init__(
            message=message,
            code="FORM_VALIDATION_ERROR",
            details=err_details,
        )
        self.field_errors = field_errors or {}


class StagingGuardConflictError(OnboardingError):
    """Raised when staging fields conflicts with uncommitted manual user edits or active focus."""

    def __init__(
        self,
        message: str = "Staging guard conflict: User has uncommitted manual edits in target fields.",
        conflicting_fields: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = dict(details or {})
        if conflicting_fields:
            err_details["conflicting_fields"] = conflicting_fields
        super().__init__(
            message=message,
            code="STAGING_GUARD_CONFLICT",
            details=err_details,
        )
        self.conflicting_fields = conflicting_fields or []


class InvalidStateTransitionError(OnboardingError):
    """Raised when attempting an illegal receipt state machine transition."""

    def __init__(
        self,
        message: str = "Illegal receipt state transition.",
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = dict(details or {})
        if from_state:
            err_details["from_state"] = from_state
        if to_state:
            err_details["to_state"] = to_state
        super().__init__(
            message=message,
            code="INVALID_STATE_TRANSITION",
            details=err_details,
        )
        self.from_state = from_state
        self.to_state = to_state


class DelegationRefusalError(OnboardingError):
    """Raised when an operation violates session delegation policy or requires owner sign-off."""

    def __init__(
        self,
        message: str = "Operation refused by delegation policy.",
        domain: Optional[int] = None,
        step_id: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = dict(details or {})
        if domain is not None:
            err_details["domain"] = domain
        if step_id is not None:
            err_details["step_id"] = step_id
        if reason:
            err_details["refusal_reason"] = reason
        super().__init__(
            message=message,
            code="DELEGATION_REFUSED",
            details=err_details,
        )
        self.domain = domain
        self.step_id = step_id
        self.reason = reason


class InvalidNonceError(OnboardingError):
    """Raised when an authorization nonce is invalid, missing, or malformed."""

    def __init__(
        self,
        message: str = "Invalid authorization nonce.",
        code: str = "INVALID_NONCE",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details,
        )


class NonceExpiredError(InvalidNonceError):
    """Raised when an authorization nonce has expired (validity window exceeded)."""

    def __init__(
        self,
        message: str = "Authorization nonce has expired.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code="NONCE_EXPIRED",
            details=details,
        )


class NonceAlreadyUsedError(InvalidNonceError):
    """Raised when a single-use authorization nonce has already been consumed."""

    def __init__(
        self,
        message: str = "Authorization nonce has already been consumed (single-use).",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code="NONCE_ALREADY_USED",
            details=details,
        )

