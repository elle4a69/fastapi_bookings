"""Targeted tests for voice-first onboarding Pydantic schemas and errors.

Verifies schema parsing, command envelope serialization, lease/epoch validation,
receipt state machine transitions, and error hierarchy representation.
"""

import json
import uuid
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.services.business_assistant.onboarding import (
    FieldPayload,
    FormValidationError,
    InvalidStateTransitionError,
    LeaseExpiredError,
    OnboardingActionType,
    OnboardingCommandEnvelope,
    OnboardingError,
    OnboardingExecutionReceipt,
    OnboardingTargetForm,
    ReceiptState,
    StagingGuardConflictError,
    StaleControlEpochError,
)


class TestOnboardingEnums:
    """Verifies onboarding action types and target form enums."""

    def test_action_types_defined(self):
        expected_actions = {
            "navigate_subtab",
            "open_modal",
            "fill_fields",
            "select_option",
            "validate_form",
            "save_form",
            "manual_takeover",
        }
        actual_actions = {item.value for item in OnboardingActionType}
        assert expected_actions == actual_actions

    def test_target_forms_defined(self):
        expected_forms = {
            "business_settings",
            "catalog_services",
            "website",
        }
        actual_forms = {item.value for item in OnboardingTargetForm}
        assert expected_forms == actual_forms

    def test_receipt_states_defined(self):
        expected_states = {
            "received",
            "waiting_for_ui",
            "executing",
            "fields_staged",
            "saved",
            "rejected",
            "failed",
            "outcome_unknown",
        }
        actual_states = {item.value for item in ReceiptState}
        assert expected_states == actual_states


class TestFieldPayload:
    """Verifies typed field payload model and validations."""

    def test_valid_field_payload(self):
        field = FieldPayload(
            field_key="business_name",
            value="Coastal Canine Grooming",
            data_type="string",
            qualifier=None,
        )
        assert field.field_key == "business_name"
        assert field.value == "Coastal Canine Grooming"
        assert field.data_type == "string"
        assert field.effective_unit is None

    def test_field_payload_with_unit_and_qualifier(self):
        price_field = FieldPayload(
            field_key="price",
            value=85.50,
            data_type="number",
            qualifier="AUD",
        )
        assert price_field.effective_unit == "AUD"

        duration_field = FieldPayload(
            field_key="duration_mins",
            value=60,
            data_type="number",
            unit="minutes",
        )
        assert duration_field.effective_unit == "minutes"

    def test_blank_field_key_rejected(self):
        with pytest.raises(ValidationError):
            FieldPayload(field_key="   ", value="Value")

    def test_empty_field_key_rejected(self):
        with pytest.raises(ValidationError):
            FieldPayload(field_key="", value="Value")


class TestOnboardingCommandEnvelope:
    """Verifies command envelope serialization, lease and epoch constraints."""

    def test_envelope_creation_and_defaults(self):
        envelope = OnboardingCommandEnvelope(
            action_type=OnboardingActionType.NAVIGATE_SUBTAB,
            target_form=OnboardingTargetForm.BUSINESS_SETTINGS,
            payload={"subtab": "solo_provider"},
            lease_token="lease-uuid-12345",
            control_epoch=1,
            idempotency_key="idemp-key-abc",
        )

        assert envelope.action_type == OnboardingActionType.NAVIGATE_SUBTAB
        assert envelope.target_form == OnboardingTargetForm.BUSINESS_SETTINGS
        assert envelope.lease_token == "lease-uuid-12345"
        assert envelope.control_epoch == 1
        assert envelope.idempotency_key == "idemp-key-abc"
        assert uuid.UUID(envelope.action_id)  # valid uuid string
        assert isinstance(envelope.timestamp, datetime)

    def test_envelope_serialization_round_trip(self):
        envelope = OnboardingCommandEnvelope(
            action_type=OnboardingActionType.FILL_FIELDS,
            target_form=OnboardingTargetForm.CATALOG_SERVICES,
            payload={
                "fields": [
                    {"field_key": "name", "value": "Bath & Brush", "data_type": "string"},
                    {"field_key": "price", "value": 65, "data_type": "number", "qualifier": "AUD"},
                ]
            },
            lease_token="token-999",
            control_epoch=3,
            idempotency_key="idemp-fill-1",
        )

        raw_json = envelope.model_dump_json()
        data = json.loads(raw_json)
        rehydrated = OnboardingCommandEnvelope.model_validate(data)

        assert rehydrated.action_type == envelope.action_type
        assert rehydrated.target_form == envelope.target_form
        assert rehydrated.lease_token == envelope.lease_token
        assert rehydrated.control_epoch == envelope.control_epoch
        assert rehydrated.idempotency_key == envelope.idempotency_key

        extracted = rehydrated.extract_fields()
        assert len(extracted) == 2
        assert extracted[0].field_key == "name"
        assert extracted[1].value == 65
        assert extracted[1].qualifier == "AUD"

    def test_negative_control_epoch_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingCommandEnvelope(
                action_type=OnboardingActionType.SAVE_FORM,
                target_form=OnboardingTargetForm.BUSINESS_SETTINGS,
                lease_token="valid-token",
                control_epoch=-1,
                idempotency_key="idemp-1",
            )

    def test_blank_lease_token_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingCommandEnvelope(
                action_type=OnboardingActionType.SAVE_FORM,
                target_form=OnboardingTargetForm.BUSINESS_SETTINGS,
                lease_token="   ",
                control_epoch=0,
                idempotency_key="idemp-1",
            )

    def test_blank_idempotency_key_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingCommandEnvelope(
                action_type=OnboardingActionType.SAVE_FORM,
                target_form=OnboardingTargetForm.BUSINESS_SETTINGS,
                lease_token="token-valid",
                control_epoch=0,
                idempotency_key="  ",
            )


class TestReceiptStateTransitions:
    """Verifies receipt state machine invariants and transition rules."""

    def test_terminal_states(self):
        assert ReceiptState.SAVED.is_terminal is True
        assert ReceiptState.REJECTED.is_terminal is True
        assert ReceiptState.FAILED.is_terminal is True
        assert ReceiptState.OUTCOME_UNKNOWN.is_terminal is True

        assert ReceiptState.RECEIVED.is_terminal is False
        assert ReceiptState.WAITING_FOR_UI.is_terminal is False
        assert ReceiptState.EXECUTING.is_terminal is False
        assert ReceiptState.FIELDS_STAGED.is_terminal is False

    def test_valid_transitions(self):
        assert ReceiptState.can_transition(ReceiptState.RECEIVED, ReceiptState.WAITING_FOR_UI) is True
        assert ReceiptState.can_transition(ReceiptState.RECEIVED, ReceiptState.EXECUTING) is True
        assert ReceiptState.can_transition(ReceiptState.RECEIVED, ReceiptState.REJECTED) is True

        assert ReceiptState.can_transition(ReceiptState.WAITING_FOR_UI, ReceiptState.EXECUTING) is True
        assert ReceiptState.can_transition(ReceiptState.EXECUTING, ReceiptState.FIELDS_STAGED) is True
        assert ReceiptState.can_transition(ReceiptState.EXECUTING, ReceiptState.SAVED) is True
        assert ReceiptState.can_transition(ReceiptState.FIELDS_STAGED, ReceiptState.SAVED) is True

    def test_invalid_transitions(self):
        # Cannot transition from terminal states
        assert ReceiptState.can_transition(ReceiptState.SAVED, ReceiptState.EXECUTING) is False
        assert ReceiptState.can_transition(ReceiptState.REJECTED, ReceiptState.SAVED) is False
        assert ReceiptState.can_transition(ReceiptState.FAILED, ReceiptState.FIELDS_STAGED) is False

        # Cannot jump backwards
        assert ReceiptState.can_transition(ReceiptState.FIELDS_STAGED, ReceiptState.RECEIVED) is False
        assert ReceiptState.can_transition(ReceiptState.EXECUTING, ReceiptState.WAITING_FOR_UI) is False

        # Cannot jump from received straight to fields_staged without executing
        assert ReceiptState.can_transition(ReceiptState.RECEIVED, ReceiptState.FIELDS_STAGED) is False


class TestOnboardingExecutionReceipt:
    """Verifies execution receipt operations and staged vs saved boundaries."""

    def test_from_envelope_factory(self):
        envelope = OnboardingCommandEnvelope(
            action_type=OnboardingActionType.FILL_FIELDS,
            target_form=OnboardingTargetForm.BUSINESS_SETTINGS,
            lease_token="lease-abc",
            control_epoch=2,
            idempotency_key="idemp-env",
        )

        receipt = OnboardingExecutionReceipt.from_envelope(envelope)
        assert receipt.action_id == envelope.action_id
        assert receipt.state == ReceiptState.RECEIVED
        assert receipt.is_terminal is False
        assert receipt.is_saved is False
        assert receipt.is_staged is False

    def test_staged_is_not_saved_invariant(self):
        receipt = OnboardingExecutionReceipt(
            action_id="act-1",
            state=ReceiptState.FIELDS_STAGED,
            modified_fields=["business_name", "phone"],
        )

        assert receipt.is_staged is True
        assert receipt.is_saved is False
        assert receipt.is_terminal is False

    def test_saved_state_properties(self):
        receipt = OnboardingExecutionReceipt(
            action_id="act-2",
            state=ReceiptState.SAVED,
            modified_fields=["business_name"],
            details={"revision": 4, "entity_id": 12},
        )

        assert receipt.is_saved is True
        assert receipt.is_staged is False
        assert receipt.is_terminal is True

    def test_transition_to_valid_lifecycle(self):
        receipt = OnboardingExecutionReceipt(
            action_id="act-flow-1",
            state=ReceiptState.RECEIVED,
        )

        # 1. received -> waiting_for_ui
        r1 = receipt.transition_to(ReceiptState.WAITING_FOR_UI)
        assert r1.state == ReceiptState.WAITING_FOR_UI

        # 2. waiting_for_ui -> executing
        r2 = r1.transition_to(ReceiptState.EXECUTING)
        assert r2.state == ReceiptState.EXECUTING

        # 3. executing -> fields_staged
        r3 = r2.transition_to(ReceiptState.FIELDS_STAGED, modified_fields=["name", "description"])
        assert r3.state == ReceiptState.FIELDS_STAGED
        assert r3.modified_fields == ["name", "description"]
        assert r3.is_staged is True
        assert r3.is_saved is False

        # 4. fields_staged -> saved
        r4 = r3.transition_to(ReceiptState.SAVED, details={"committed": True})
        assert r4.state == ReceiptState.SAVED
        assert r4.is_saved is True
        assert r4.is_terminal is True
        assert r4.details.get("committed") is True

    def test_transition_to_invalid_raises_error(self):
        receipt = OnboardingExecutionReceipt(
            action_id="act-err-1",
            state=ReceiptState.SAVED,
        )

        # Terminal state cannot transition to executing
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            receipt.transition_to(ReceiptState.EXECUTING)

        assert exc_info.value.code == "INVALID_STATE_TRANSITION"
        assert exc_info.value.from_state == "saved"
        assert exc_info.value.to_state == "executing"

    def test_receipt_serialization_round_trip(self):
        receipt = OnboardingExecutionReceipt(
            action_id="act-ser-1",
            state=ReceiptState.REJECTED,
            error_code="STALE_CONTROL_EPOCH",
            error_message="User manual takeover superseded command.",
            details={"epoch": 5},
        )

        raw_json = receipt.model_dump_json()
        parsed = json.loads(raw_json)
        rehydrated = OnboardingExecutionReceipt.model_validate(parsed)

        assert rehydrated.action_id == "act-ser-1"
        assert rehydrated.state == ReceiptState.REJECTED
        assert rehydrated.error_code == "STALE_CONTROL_EPOCH"
        assert rehydrated.error_message == "User manual takeover superseded command."
        assert rehydrated.details == {"epoch": 5}


class TestOnboardingErrorHierarchy:
    """Verifies error hierarchy, status codes, and serialization dictionary."""

    def test_base_onboarding_error(self):
        err = OnboardingError("General automation fault", code="GENERIC_FAULT", details={"foo": "bar"})
        assert isinstance(err, Exception)
        assert err.code == "GENERIC_FAULT"
        assert err.details == {"foo": "bar"}
        d = err.to_dict()
        assert d["error_code"] == "GENERIC_FAULT"
        assert d["error_message"] == "General automation fault"
        assert d["details"] == {"foo": "bar"}

    def test_stale_control_epoch_error(self):
        err = StaleControlEpochError(
            expected_epoch=5,
            received_epoch=4,
        )
        assert isinstance(err, OnboardingError)
        assert err.code == "STALE_CONTROL_EPOCH"
        assert err.expected_epoch == 5
        assert err.received_epoch == 4
        assert err.details["expected_epoch"] == 5
        assert err.details["received_epoch"] == 4

    def test_lease_expired_error(self):
        err = LeaseExpiredError(lease_token="lease-exp-777")
        assert isinstance(err, OnboardingError)
        assert err.code == "LEASE_EXPIRED"
        assert err.lease_token == "lease-exp-777"
        assert err.details["lease_token"] == "lease-exp-777"

    def test_form_validation_error(self):
        err = FormValidationError(
            message="Invalid field inputs",
            field_errors={"phone": ["Invalid Australian phone format"], "email": ["Invalid email address"]},
        )
        assert isinstance(err, OnboardingError)
        assert err.code == "FORM_VALIDATION_ERROR"
        assert "phone" in err.field_errors
        assert err.details["field_errors"]["phone"] == ["Invalid Australian phone format"]

    def test_staging_guard_conflict_error(self):
        err = StagingGuardConflictError(
            conflicting_fields=["locStreet", "locCity"],
        )
        assert isinstance(err, OnboardingError)
        assert err.code == "STAGING_GUARD_CONFLICT"
        assert err.conflicting_fields == ["locStreet", "locCity"]
        assert err.details["conflicting_fields"] == ["locStreet", "locCity"]

    def test_invalid_state_transition_error(self):
        err = InvalidStateTransitionError(
            from_state="saved",
            to_state="executing",
        )
        assert isinstance(err, OnboardingError)
        assert err.code == "INVALID_STATE_TRANSITION"
        assert err.from_state == "saved"
        assert err.to_state == "executing"
