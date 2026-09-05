"""Synthetic no-network coverage for Package C's fail-closed processor."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from app.models.client import Client
from app.models.provider import Provider
from app.models.sms_chatwoot import ChatwootConnection, SmsChatwootBinding
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsConversationEvent, SmsOutboundJob
from app.models.tenant import Tenant
from app.services.messaging.chatwoot_ingress import process_authenticated_event
from app.services.messaging.contracts import ParsedChatwootEvent
from app.services.messaging.policy import ProcessingProvenance
from app.services.messaging.processor import process_projected_message


NOW = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)


def _projection(db_session, *, state="auto-reply", automation_enabled=False):
    tenant = Tenant(name="Synthetic Processing", subdomain="processing-test")
    db_session.add(tenant)
    db_session.flush()
    provider = Provider(tenant_id=tenant.id, name="Synthetic Provider", active=True)
    db_session.add(provider)
    db_session.flush()
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        chatwoot_inbox_id=51002,
        automation_enabled=automation_enabled,
    )
    db_session.add(binding)
    db_session.flush()
    conversation = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=None,
        customer_address="chatwoot-projection-synthetic",
        state=state,
        unread_count=0,
        chatwoot_binding_id=binding.id,
        chatwoot_conversation_id=51003,
        chatwoot_contact_id=None,
        chatwoot_inbox_id=binding.chatwoot_inbox_id,
        last_activity_at=NOW,
    )
    db_session.add(conversation)
    db_session.flush()
    return tenant, provider, binding, conversation


def _message(
    db_session,
    *,
    binding: SmsChatwootBinding,
    conversation: SmsConversation,
    direction="inbound",
    author_type="customer",
    message_type="incoming",
    content_type="text",
    private=False,
    message_id=51004,
):
    message = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="SYNTHETIC-PROCESSING-CONTENT",
        normalized_body="synthetic-processing-content",
        direction=direction,
        author_type=author_type,
        status="received",
        chatwoot_binding_id=binding.id,
        chatwoot_message_id=message_id,
        chatwoot_message_type=message_type,
        chatwoot_content_type=content_type,
        chatwoot_private=private,
        chatwoot_sender_type="SyntheticSender",
        chatwoot_sender_reference="synthetic-reference",
        occurred_at=NOW,
        received_at=NOW,
    )
    db_session.add(message)
    db_session.flush()
    return message


@pytest.mark.parametrize(
    (
        "case",
        "message_fields",
        "provenance",
        "automation_enabled",
        "expected_state",
        "expected_reason",
        "expected_event_type",
        "pending_status",
    ),
    [
        (
            "incoming_customer_text_disabled",
            {},
            ProcessingProvenance.UNVERIFIED,
            False,
            "paused",
            "automation_disabled",
            "chatwoot_operator_review",
            "PENDING",
        ),
        (
            "incoming_customer_text_enabled_without_handoff",
            {},
            ProcessingProvenance.UNVERIFIED,
            True,
            "paused",
            "outbound_handoff_unavailable",
            "chatwoot_operator_review",
            "PENDING",
        ),
        (
            "human_public_reply",
            {"direction": "outbound", "author_type": "staff", "message_type": "outgoing"},
            ProcessingProvenance.UNVERIFIED,
            False,
            "taken-over",
            "human_staff_reply",
            "chatwoot_takeover",
            "CANCELLED",
        ),
        (
            "human_private_note",
            {
                "direction": "outbound",
                "author_type": "staff",
                "message_type": "outgoing",
                "private": True,
            },
            ProcessingProvenance.UNVERIFIED,
            False,
            "paused",
            "human_private_note",
            "chatwoot_operator_review",
            "CANCELLED",
        ),
        (
            "external_agent_bot",
            {"direction": "outbound", "author_type": "external_bot", "message_type": "outgoing"},
            ProcessingProvenance.UNVERIFIED,
            False,
            "paused",
            "external_bot_conflict",
            "chatwoot_operator_review",
            "CANCELLED",
        ),
        (
            "template",
            {"direction": "system", "author_type": "system", "message_type": "template"},
            ProcessingProvenance.UNVERIFIED,
            False,
            "paused",
            "unsupported_message_type",
            "chatwoot_operator_review",
            "PENDING",
        ),
        (
            "activity",
            {"direction": "system", "author_type": "system", "message_type": "activity"},
            ProcessingProvenance.UNVERIFIED,
            False,
            "paused",
            "unsupported_message_type",
            "chatwoot_operator_review",
            "PENDING",
        ),
        (
            "system",
            {"direction": "system", "author_type": "system", "message_type": "system"},
            ProcessingProvenance.UNVERIFIED,
            False,
            "paused",
            "unsupported_message_type",
            "chatwoot_operator_review",
            "PENDING",
        ),
        (
            "unknown_content",
            {"content_type": "form"},
            ProcessingProvenance.UNVERIFIED,
            False,
            "paused",
            "unsupported_content",
            "chatwoot_operator_review",
            "PENDING",
        ),
        (
            "unknown_sender",
            {"author_type": "system"},
            ProcessingProvenance.UNVERIFIED,
            False,
            "paused",
            "unsupported_sender",
            "chatwoot_operator_review",
            "PENDING",
        ),
        (
            "reserved_verified_echo",
            {"direction": "outbound", "author_type": "staff", "message_type": "outgoing"},
            ProcessingProvenance.VERIFIED_FASTAPI_ECHO,
            False,
            "auto-reply",
            "verified_fastapi_echo",
            "chatwoot_projection_reconciled",
            "PENDING",
        ),
    ],
    ids=lambda case: case,
)
def test_full_policy_matrix_is_structural_and_never_dispatches(
    db_session,
    case,
    message_fields,
    provenance,
    automation_enabled,
    expected_state,
    expected_reason,
    expected_event_type,
    pending_status,
):
    _, _, binding, conversation = _projection(
        db_session, automation_enabled=automation_enabled
    )
    message = _message(
        db_session,
        binding=binding,
        conversation=conversation,
        **message_fields,
    )
    pending = SmsAiJob(
        conversation_id=conversation.id,
        customer_turn_ref=f"synthetic-{case}",
        status="PENDING",
    )
    db_session.add(pending)
    db_session.flush()

    result = process_projected_message(
        db_session,
        binding=binding,
        conversation=conversation,
        message=message,
        provenance=provenance,
    )

    db_session.refresh(conversation)
    db_session.refresh(pending)
    event = db_session.query(SmsConversationEvent).one()
    assert result.reason_code == expected_reason
    assert conversation.state == expected_state
    assert pending.status == pending_status
    assert event.type == expected_event_type
    assert event.meta["reason_code"] == expected_reason
    assert "SYNTHETIC-PROCESSING-CONTENT" not in str(event.meta)
    assert "synthetic-reference" not in str(event.meta)
    assert db_session.query(SmsOutboundJob).count() == 0


def test_bare_client_reference_is_not_a_cross_channel_identity_binding(db_session):
    tenant, _, binding, conversation = _projection(db_session)
    client = Client(
        tenant_id=tenant.id,
        name="Synthetic Existing Client",
        phone="+61400000001",
    )
    db_session.add(client)
    db_session.flush()
    conversation.client_id = client.id
    message = _message(db_session, binding=binding, conversation=conversation)

    process_projected_message(
        db_session,
        binding=binding,
        conversation=conversation,
        message=message,
    )

    db_session.refresh(conversation)
    event = db_session.query(SmsConversationEvent).one()
    assert conversation.client_id == client.id
    assert conversation.state == "paused"
    assert event.meta == {
        "reason_code": "automation_disabled",
        "identity_code": "untrusted_client_identity",
    }
    assert db_session.query(SmsAiJob).count() == 0
    assert db_session.query(SmsOutboundJob).count() == 0


def test_copied_echo_value_cannot_select_reserved_verified_echo_path(db_session):
    _, _, binding, conversation = _projection(db_session)
    message = _message(
        db_session,
        binding=binding,
        conversation=conversation,
        direction="outbound",
        author_type="staff",
        message_type="outgoing",
    )

    process_projected_message(
        db_session,
        binding=binding,
        conversation=conversation,
        message=message,
        provenance="verified_fastapi_echo",  # type: ignore[arg-type]
    )

    db_session.refresh(conversation)
    event = db_session.query(SmsConversationEvent).one()
    assert conversation.state == "taken-over"
    assert event.meta == {"reason_code": "human_staff_reply"}


def _ingress_boundary(db_session):
    tenant = Tenant(name="Synthetic Ingress Policy", subdomain="ingress-policy")
    db_session.add(tenant)
    db_session.flush()
    provider = Provider(tenant_id=tenant.id, name="Synthetic Ingress Provider", active=True)
    db_session.add(provider)
    db_session.flush()
    connection = ChatwootConnection(
        tenant_id=tenant.id,
        instance_origin="https://synthetic-processing.example.test",
        chatwoot_account_id=52001,
        _signing_secret_ciphertext="synthetic-ciphertext",
        enabled=True,
    )
    db_session.add(connection)
    db_session.flush()
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        connection_id=connection.id,
        chatwoot_inbox_id=52002,
        channel="web_widget",
        ingress_enabled=True,
        is_enabled=False,
    )
    db_session.add(binding)
    db_session.commit()
    return connection


def _event(*, event_type="message_created", message_id=52004):
    return ParsedChatwootEvent(
        event_type=event_type,
        account_id=52001,
        inbox_id=52002,
        conversation_id=52003,
        message_id=message_id,
        message_type="incoming",
        content_type="text",
        body="SYNTHETIC-INGRESS-CONTENT",
        private=False,
        sender_type="Contact",
        sender_reference="synthetic-contact",
        attachments=[],
        occurred_at=NOW,
        channel_observation="Channel::WebWidget",
    )


def test_only_new_created_projection_invokes_processor(monkeypatch, db_session):
    import app.services.messaging.chatwoot_ingress as ingress

    connection = _ingress_boundary(db_session)
    original = ingress.process_projected_message
    calls: list[int] = []

    def spy(*args, **kwargs):
        calls.append(kwargs["message"].chatwoot_message_id)
        return original(*args, **kwargs)

    monkeypatch.setattr(ingress, "process_projected_message", spy)
    created = _event()
    first = process_authenticated_event(
        db_session,
        connection=connection,
        delivery_id=UUID("12345678-1234-4234-9234-123456789abc"),
        event=created,
        webhook_timestamp=NOW,
    )
    assert first.outcome == "projected"
    assert calls == [52004]

    calls.clear()
    duplicate_delivery = process_authenticated_event(
        db_session,
        connection=connection,
        delivery_id=UUID("12345678-1234-4234-9234-123456789abc"),
        event=created,
        webhook_timestamp=NOW,
    )
    duplicate_message = process_authenticated_event(
        db_session,
        connection=connection,
        delivery_id=UUID("22345678-1234-4234-9234-123456789abc"),
        event=created,
        webhook_timestamp=NOW,
    )
    updated = process_authenticated_event(
        db_session,
        connection=connection,
        delivery_id=UUID("32345678-1234-4234-9234-123456789abc"),
        event=replace(created, event_type="message_updated"),
        webhook_timestamp=NOW,
    )
    assert duplicate_delivery.outcome == "duplicate_delivery"
    assert duplicate_message.outcome == "duplicate_message"
    assert updated.outcome == "updated"
    assert calls == []
    assert db_session.query(SmsAiJob).count() == 0
    assert db_session.query(SmsOutboundJob).count() == 0
    assert db_session.query(SmsConversationEvent).count() == 1


def test_unknown_channel_is_receipt_only_and_never_dispatches(db_session):
    connection = _ingress_boundary(db_session)
    result = process_authenticated_event(
        db_session,
        connection=connection,
        delivery_id=UUID("42345678-1234-4234-9234-123456789abc"),
        event=replace(_event(), channel_observation="Channel::Unknown"),
        webhook_timestamp=NOW,
    )

    assert result.outcome == "unsupported_channel"
    assert db_session.query(SmsMessage).count() == 0
    assert db_session.query(SmsConversationEvent).count() == 0
    assert db_session.query(SmsAiJob).count() == 0
    assert db_session.query(SmsOutboundJob).count() == 0


def test_default_gate_is_not_exposed_or_used_as_an_activation_control(db_session):
    _, _, binding, _ = _projection(db_session)
    column = SmsChatwootBinding.__table__.c.automation_enabled
    assert column.default.arg is False
    assert "false" in str(column.server_default.arg).lower()
    assert binding.automation_enabled is False

    project_root = Path(__file__).parents[1]
    assert "automation_enabled" not in (
        project_root / "app" / "schemas" / "sms_chatwoot.py"
    ).read_text(encoding="utf-8")
    assert "automation_enabled" not in (
        project_root / "app" / "api" / "routers" / "chatwoot_admin.py"
    ).read_text(encoding="utf-8")


def test_processor_and_ingress_do_not_accept_legacy_echo_metadata_or_log_content(
    caplog,
):
    project_root = Path(__file__).parents[1]
    ingress_source = (
        project_root / "app" / "services" / "messaging" / "chatwoot_ingress.py"
    ).read_text(encoding="utf-8")
    processor_source = (
        project_root / "app" / "services" / "messaging" / "processor.py"
    ).read_text(encoding="utf-8")
    assert "source_id" not in ingress_source
    assert "logging" not in processor_source
    assert "ai_orchestrator" not in processor_source
    assert "outbound_service" not in processor_source
    assert "SYNTHETIC-PROCESSING-CONTENT" not in caplog.text
