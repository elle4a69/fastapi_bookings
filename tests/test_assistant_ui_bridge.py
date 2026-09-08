"""Synthetic no-network tests for the Chatwoot-to-Assistant UI bridge."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.models.provider import Provider
from app.models.sms_chatwoot import ChatwootConnection, ChatwootOutboundIntent, SmsChatwootBinding
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import AssistantUiBridgeJob
from app.models.tenant import Tenant
from app.services.messaging.assistant_ui_bridge import process_one_assistant_ui_bridge_job
from app.services.messaging.assistant_ui_client import AssistantUiDecision
from app.services.messaging.processor import process_projected_message
from app.services.messaging.policy import ProcessingProvenance


NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


def _context(db):
    tenant = Tenant(name="Synthetic Bridge", subdomain="bridge-test")
    db.add(tenant); db.flush()
    provider = Provider(tenant_id=tenant.id, name="Synthetic Bridge Provider", active=True)
    db.add(provider); db.flush()
    connection = ChatwootConnection(
        tenant_id=tenant.id, instance_origin="https://chatwoot.example.test",
        chatwoot_account_id=9901, enabled=True, outbound_enabled=True,
        expected_integration_sender_type="User", expected_integration_sender_id=991,
    )
    connection._signing_secret_ciphertext = "synthetic"
    connection._api_token_ciphertext = "synthetic"
    db.add(connection); db.flush()
    binding = SmsChatwootBinding(
        tenant_id=tenant.id, provider_id=provider.id, connection_id=connection.id,
        chatwoot_inbox_id=9902, channel="web_widget", ingress_enabled=True,
        outbound_enabled=True, automation_enabled=True,
        assistant_ui_policy_scope="synthetic-scope",
    )
    db.add(binding); db.flush()
    conversation = SmsConversation(
        tenant_id=tenant.id, provider_id=provider.id, sms_account_id=None,
        customer_address="chatwoot-synthetic", state="paused", unread_count=0,
        chatwoot_binding_id=binding.id, chatwoot_conversation_id=9903,
        chatwoot_inbox_id=binding.chatwoot_inbox_id, last_activity_at=NOW,
    )
    db.add(conversation); db.flush()
    message = SmsMessage(
        tenant_id=tenant.id, provider_id=provider.id, sms_account_id=None,
        conversation_id=conversation.id, body="SYNTHETIC CUSTOMER MESSAGE",
        normalized_body="synthetic customer message", direction="inbound",
        author_type="customer", status="received", chatwoot_binding_id=binding.id,
        chatwoot_message_id=9904, chatwoot_message_type="incoming",
        chatwoot_content_type="text", chatwoot_private=False,
        occurred_at=NOW, received_at=NOW,
    )
    db.add(message); db.flush()
    return binding, conversation, message


def test_eligible_projection_creates_one_binding_scoped_bridge_job(db_session):
    binding, conversation, message = _context(db_session)
    process_projected_message(
        db_session, binding=binding, conversation=conversation, message=message,
        provenance=ProcessingProvenance.UNVERIFIED,
    )
    job = db_session.query(AssistantUiBridgeJob).one()
    assert job.binding_id == binding.id
    assert job.source_message_id == message.id
    assert job.status == "PENDING"
    assert conversation.state == "auto-reply"


def test_reply_revalidates_and_creates_only_chatwoot_intent(db_session, monkeypatch):
    binding, conversation, message = _context(db_session)
    process_projected_message(
        db_session, binding=binding, conversation=conversation, message=message,
        provenance=ProcessingProvenance.UNVERIFIED,
    )
    job = db_session.query(AssistantUiBridgeJob).one()

    async def synthetic_decision(*, payload):
        assert payload["policy_scope"] == "synthetic-scope"
        return AssistantUiDecision(kind="reply", reply="Synthetic reply")

    monkeypatch.setattr("app.services.messaging.assistant_ui_bridge.request_decision", synthetic_decision)
    job.status = "PROCESSING"; db_session.commit()
    assert asyncio.run(process_one_assistant_ui_bridge_job(db_session, job_id=job.id)) == "COMPLETED"
    assert db_session.query(ChatwootOutboundIntent).count() == 1
    assert db_session.query(AssistantUiBridgeJob).one().status == "COMPLETED"


def test_staff_takeover_race_handoffs_without_customer_output(db_session, monkeypatch):
    binding, conversation, message = _context(db_session)
    process_projected_message(
        db_session, binding=binding, conversation=conversation, message=message,
        provenance=ProcessingProvenance.UNVERIFIED,
    )
    job = db_session.query(AssistantUiBridgeJob).one()

    async def synthetic_decision(*, payload):
        conversation.state = "taken-over"; db_session.commit()
        return AssistantUiDecision(kind="reply", reply="Synthetic reply")

    monkeypatch.setattr("app.services.messaging.assistant_ui_bridge.request_decision", synthetic_decision)
    job.status = "PROCESSING"; db_session.commit()
    assert asyncio.run(process_one_assistant_ui_bridge_job(db_session, job_id=job.id)) == "HANDOFF"
    assert db_session.query(ChatwootOutboundIntent).count() == 0
    assert db_session.query(AssistantUiBridgeJob).one().status == "HANDOFF"
