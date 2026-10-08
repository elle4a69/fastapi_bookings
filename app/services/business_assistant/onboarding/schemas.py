"""Pydantic schemas and typed action contracts for voice-first onboarding.

Mirroring frontend RPC contracts, these schemas enforce strict typing,
active-executor lease validation, control epoch monotonicity, and discrete
truthful receipt states (staged != saved).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.business_assistant.onboarding.errors import InvalidStateTransitionError


class OnboardingActionType(str, Enum):
    """Supported semantic onboarding action types."""

    NAVIGATE_SUBTAB = "navigate_subtab"
    OPEN_MODAL = "open_modal"
    FILL_FIELDS = "fill_fields"
    SELECT_OPTION = "select_option"
    VALIDATE_FORM = "validate_form"
    SAVE_FORM = "save_form"
    MANUAL_TAKEOVER = "manual_takeover"


class OnboardingTargetForm(str, Enum):
    """Allowed target forms for voice-first onboarding operations."""

    BUSINESS_SETTINGS = "business_settings"
    CATALOG_SERVICES = "catalog_services"
    WEBSITE = "website"


class ReceiptState(str, Enum):
    """Discrete truthful receipt states for onboarding action commands."""

    RECEIVED = "received"
    WAITING_FOR_UI = "waiting_for_ui"
    EXECUTING = "executing"
    FIELDS_STAGED = "fields_staged"
    SAVED = "saved"
    REJECTED = "rejected"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"

    @classmethod
    def valid_next_states(cls, current: "ReceiptState") -> Set["ReceiptState"]:
        """Return allowed next states from the given state."""
        return _VALID_RECEIPT_TRANSITIONS.get(current, set())

    @classmethod
    def can_transition(cls, from_state: "ReceiptState", to_state: "ReceiptState") -> bool:
        """Check if transitioning from from_state to to_state is valid."""
        return to_state in cls.valid_next_states(from_state)

    @property
    def is_terminal(self) -> bool:
        """Check whether this receipt state is terminal (no further transitions allowed)."""
        return len(_VALID_RECEIPT_TRANSITIONS.get(self, set())) == 0


_VALID_RECEIPT_TRANSITIONS: Dict[ReceiptState, Set[ReceiptState]] = {
    ReceiptState.RECEIVED: {
        ReceiptState.WAITING_FOR_UI,
        ReceiptState.EXECUTING,
        ReceiptState.REJECTED,
        ReceiptState.FAILED,
        ReceiptState.OUTCOME_UNKNOWN,
    },
    ReceiptState.WAITING_FOR_UI: {
        ReceiptState.EXECUTING,
        ReceiptState.REJECTED,
        ReceiptState.FAILED,
        ReceiptState.OUTCOME_UNKNOWN,
    },
    ReceiptState.EXECUTING: {
        ReceiptState.FIELDS_STAGED,
        ReceiptState.SAVED,
        ReceiptState.REJECTED,
        ReceiptState.FAILED,
        ReceiptState.OUTCOME_UNKNOWN,
    },
    ReceiptState.FIELDS_STAGED: {
        ReceiptState.SAVED,
        ReceiptState.REJECTED,
        ReceiptState.FAILED,
        ReceiptState.OUTCOME_UNKNOWN,
    },
    ReceiptState.SAVED: set(),
    ReceiptState.REJECTED: set(),
    ReceiptState.FAILED: set(),
    ReceiptState.OUTCOME_UNKNOWN: set(),
}


class FieldPayload(BaseModel):
    """Typed field value payload with qualifier and unit metadata."""

    model_config = ConfigDict(extra="ignore")

    field_key: str = Field(..., min_length=1, description="Target field key within the form")
    value: Any = Field(..., description="Interpreted and normalised field value")
    data_type: str = Field(
        default="string",
        description="Data type identifier: string, number, boolean, array, object",
    )
    qualifier: Optional[str] = Field(
        default=None,
        description="Optional qualifier, e.g. currency 'AUD', duration 'minutes', distance 'km'",
    )
    unit: Optional[str] = Field(
        default=None,
        description="Explicit measurement unit if applicable",
    )

    @field_validator("field_key", mode="before")
    @classmethod
    def validate_field_key(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field key must be a non-empty string.")
        return v.strip()

    @property
    def effective_unit(self) -> Optional[str]:
        """Resolve effective unit from unit or qualifier."""
        return self.unit or self.qualifier


class OnboardingCommandEnvelope(BaseModel):
    """Cryptographically auditable and idempotent envelope for onboarding commands."""

    model_config = ConfigDict(extra="ignore")

    action_type: OnboardingActionType = Field(
        ...,
        description="Semantic onboarding action type to execute",
    )
    target_form: OnboardingTargetForm = Field(
        ...,
        description="Registered onboarding target form",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Command-specific parameters or field batches",
    )
    lease_token: str = Field(
        ...,
        min_length=1,
        description="Active executor lease UUID ensuring single-tab execution",
    )
    control_epoch: int = Field(
        ...,
        ge=0,
        description="Monotonically increasing control epoch invalidated by manual takeover",
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        description="Unique key ensuring at-most-once execution across retries",
    )
    action_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique identifier for this action command",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of command envelope creation",
    )

    @field_validator("lease_token", "idempotency_key", mode="before")
    @classmethod
    def validate_non_blank_string(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Value must be a non-empty, non-whitespace string.")
        return v.strip()

    def extract_fields(self) -> List[FieldPayload]:
        """Extract and parse structured field payloads if present in payload dict."""
        raw_fields = self.payload.get("fields")
        if not raw_fields or not isinstance(raw_fields, list):
            return []
        parsed = []
        for item in raw_fields:
            if isinstance(item, FieldPayload):
                parsed.append(item)
            elif isinstance(item, dict):
                parsed.append(FieldPayload(**item))
        return parsed


class OnboardingExecutionReceipt(BaseModel):
    """Truthful execution receipt returned by frontend or gateway executor."""

    model_config = ConfigDict(extra="ignore")

    action_id: str = Field(..., min_length=1, description="Associated action identifier")
    state: ReceiptState = Field(..., description="Discrete execution receipt state")
    resulting_route: Optional[str] = Field(
        default=None,
        description="Resulting application route after navigation or modal action",
    )
    modified_fields: List[str] = Field(
        default_factory=list,
        description="List of field keys modified or staged by this action",
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code if rejected or failed",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable error explanation if rejected or failed",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of receipt generation or state transition",
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Supplementary execution metadata (e.g. entity_id, revision)",
    )

    @field_validator("action_id", mode="before")
    @classmethod
    def validate_action_id(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("action_id must be a non-empty string.")
        return v.strip()

    @classmethod
    def from_envelope(
        cls,
        envelope: OnboardingCommandEnvelope,
        state: ReceiptState = ReceiptState.RECEIVED,
        **kwargs: Any,
    ) -> "OnboardingExecutionReceipt":
        """Factory creating an initial receipt from a command envelope."""
        return cls(
            action_id=envelope.action_id,
            state=state,
            **kwargs,
        )

    def transition_to(
        self,
        next_state: Union[ReceiptState, str],
        *,
        resulting_route: Optional[str] = None,
        modified_fields: Optional[List[str]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> "OnboardingExecutionReceipt":
        """Transition receipt to a new state, enforcing state-machine transition validity."""
        target_state = ReceiptState(next_state)
        if not ReceiptState.can_transition(self.state, target_state):
            raise InvalidStateTransitionError(
                message=f"Illegal transition from '{self.state.value}' to '{target_state.value}'.",
                from_state=self.state.value,
                to_state=target_state.value,
            )

        updated_details = dict(self.details)
        if details:
            updated_details.update(details)

        return OnboardingExecutionReceipt(
            action_id=self.action_id,
            state=target_state,
            resulting_route=resulting_route if resulting_route is not None else self.resulting_route,
            modified_fields=modified_fields if modified_fields is not None else list(self.modified_fields),
            error_code=error_code if error_code is not None else self.error_code,
            error_message=error_message if error_message is not None else self.error_message,
            timestamp=datetime.now(timezone.utc),
            details=updated_details,
        )

    @property
    def is_terminal(self) -> bool:
        """Check whether current state is terminal."""
        return self.state.is_terminal

    @property
    def is_saved(self) -> bool:
        """Check whether receipt represents a committed database save."""
        return self.state == ReceiptState.SAVED

    @property
    def is_staged(self) -> bool:
        """Check whether receipt represents staged fields (not yet saved)."""
        return self.state == ReceiptState.FIELDS_STAGED
