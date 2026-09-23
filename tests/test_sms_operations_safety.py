import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.core.security import create_access_token
from app.models.client import Client
from app.models.provider import Provider
from app.models.sms_account import SmsAccount
from app.models.sms_chatwoot import SmsChatwootBinding
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsConversationEvent, SmsOutboundJob
from app.models.sms_receipt import SmsInboundReceipt
from app.models.tenant import Tenant
from app.models.user import User
from app.services.sms.chatwoot_service import process_chatwoot_webhook
from app.services.sms.inbound_service import find_duplicate_inbound_winner
from app.services.sms.operations_service import (
    SmsOperationConflict,
    transition_conversation,
)


@pytest.fixture
def operations_data(db_session):
    tenant = Tenant(name="Synthetic Operations Tenant", subdomain="synthetic-ops")
    db_session.add(tenant)
    db_session.commit()
    admin = User(
        tenant_id=tenant.id,
        login="synthetic-ops@example.invalid",
        password_hash="synthetic-hash",
        role="admin",
    )
    provider = Provider(tenant_id=tenant.id, name="Synthetic Provider", active=True)
    db_session.add_all([admin, provider])
    db_session.commit()
    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Synthetic Line",
        sender_address="61410000001",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="draft",
    )
    db_session.add(account)
    db_session.commit()
    return {
        "tenant": tenant,
        "admin": admin,
        "provider": provider,
        "account": account,
        "headers": {
            "X-Tenant": tenant.subdomain,
            "X-Token": create_access_token({"sub": str(admin.id)}),
        },
    }


def _conversation(db_session, data, *, state="auto-reply", suffix="01", **kwargs):
    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=data["account"].id,
        customer_address=f"61410000{suffix}",
        state=state,
        **kwargs,
    )
    db_session.add(conversation)
    db_session.commit()
    return conversation


@pytest.mark.parametrize(
    ("state", "action"),
    [
        ("needs-review", "takeover"),
        ("escalated", "takeover"),
        ("resolved", "takeover"),
        ("needs-review", "release"),
        ("escalated", "release"),
        ("resolved", "release"),
        ("paused", "release"),
    ],
)
def test_transition_matrix_rejects_protected_state_bypasses(
    db_session, operations_data, state, action
):
    conversation = _conversation(
        db_session, operations_data, state=state, suffix=f"{len(state):02d}"
    )
    with pytest.raises(SmsOperationConflict):
        transition_conversation(
            db_session,
            conversation=conversation,
            action=action,
            actor_id=operations_data["admin"].id,
        )
    assert conversation.state == state


def test_clear_reopen_then_release_are_separate_audited_workflows(
    db_session, operations_data
):
    conversation = _conversation(
        db_session, operations_data, state="needs-review", suffix="21"
    )
    transition_conversation(
        db_session,
        conversation=conversation,
        action="clear_review",
        actor_id=operations_data["admin"].id,
    )
    assert conversation.state == "taken-over"
    assert conversation.ai_enabled is False
    transition_conversation(
        db_session,
        conversation=conversation,
        action="release",
        actor_id=operations_data["admin"].id,
    )
    assert conversation.state == "auto-reply"

    conversation.state = "resolved"
    conversation.ai_enabled = False
    transition_conversation(
        db_session,
        conversation=conversation,
        action="reopen",
        actor_id=operations_data["admin"].id,
        reason="Synthetic follow-up required",
    )
    assert conversation.state == "taken-over"
    db_session.flush()
    event_types = {
        event.type
        for event in db_session.query(SmsConversationEvent).filter(
            SmsConversationEvent.conversation_id == conversation.id
        )
    }
    assert {
        "conversation_clear_review",
        "conversation_release",
        "conversation_reopen",
    }.issubset(event_types)


@pytest.mark.parametrize("state", ["needs-review", "escalated"])
def test_manual_send_preserves_review_and_escalation_state(
    client, db_session, operations_data, state
):
    conversation = _conversation(
        db_session, operations_data, state=state, suffix=f"3{len(state)}"
    )
    response = client.post(
        f"/api/admin/sms/conversations/{conversation.id}/messages",
        json={
            "body": "Synthetic staff response",
            "client_request_id": f"synthetic-{state}-request",
        },
        headers=operations_data["headers"],
    )
    assert response.status_code == status.HTTP_200_OK
    db_session.refresh(conversation)
    assert conversation.state == state
    assert conversation.ai_enabled is False


@pytest.mark.parametrize(
    ("state", "blocked"), [("resolved", False), ("paused", True)]
)
def test_manual_send_rejects_resolved_and_blocked_threads(
    client, db_session, operations_data, state, blocked
):
    conversation = _conversation(
        db_session,
        operations_data,
        state=state,
        suffix=f"4{int(blocked)}",
        is_blocked=blocked,
    )
    response = client.post(
        f"/api/admin/sms/conversations/{conversation.id}/messages",
        json={
            "body": "Synthetic staff response",
            "client_request_id": f"synthetic-protected-{state}",
        },
        headers=operations_data["headers"],
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert db_session.query(SmsOutboundJob).count() == 0


def test_draft_approval_reruns_safety_and_protected_state_checks(
    client, db_session, operations_data
):
    conversation = _conversation(
        db_session, operations_data, state="needs-review", suffix="51"
    )
    draft = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body="Synthetic safe draft",
        direction="draft",
        author_type="ai",
        status="draft",
    )
    db_session.add(draft)
    db_session.commit()

    edit = client.post(
        f"/api/admin/sms/conversations/drafts/{draft.id}/review",
        json={
            "action": "edit",
            "text": "api_key=sk-synthetic-secret-value",
        },
        headers=operations_data["headers"],
    )
    assert edit.status_code == status.HTTP_200_OK
    rejected = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/approve",
        headers=operations_data["headers"],
    )
    assert rejected.status_code == status.HTTP_409_CONFLICT
    db_session.refresh(draft)
    assert draft.status == "draft"
    assert db_session.query(SmsOutboundJob).filter(
        SmsOutboundJob.message_id == draft.id
    ).count() == 0

    draft.body = "Synthetic safe draft"
    conversation.state = "resolved"
    db_session.commit()
    protected = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/approve",
        headers=operations_data["headers"],
    )
    assert protected.status_code == status.HTTP_409_CONFLICT


def test_chatwoot_only_thread_requires_exact_enabled_binding_and_queues_no_carrier_account(
    client, db_session, operations_data
):
    binding = SmsChatwootBinding(
        tenant_id=operations_data["tenant"].id,
        provider_id=operations_data["provider"].id,
        chatwoot_account_id=71,
        chatwoot_inbox_id=72,
        chatwoot_base_url="https://chatwoot.invalid",
        chatwoot_api_token="synthetic-token",
        webhook_secret="synthetic-secret",
        is_enabled=True,
    )
    db_session.add(binding)
    db_session.commit()
    conversation = SmsConversation(
        tenant_id=operations_data["tenant"].id,
        provider_id=operations_data["provider"].id,
        sms_account_id=None,
        customer_address="chatwoot_contact_synthetic",
        state="taken-over",
        chatwoot_conversation_id=73,
        chatwoot_inbox_id=72,
    )
    db_session.add(conversation)
    db_session.commit()
    inbound = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="Synthetic inbound",
        direction="inbound",
        author_type="customer",
        status="received",
    )
    db_session.add(inbound)
    db_session.commit()

    listed = client.get(
        f"/api/admin/sms/conversations/{conversation.id}/messages",
        headers=operations_data["headers"],
    )
    assert listed.status_code == status.HTTP_200_OK
    sent = client.post(
        f"/api/admin/sms/conversations/{conversation.id}/messages",
        json={
            "body": "Synthetic Chatwoot response",
            "client_request_id": "synthetic-chatwoot-request",
        },
        headers=operations_data["headers"],
    )
    assert sent.status_code == status.HTTP_200_OK
    job = db_session.query(SmsOutboundJob).filter(
        SmsOutboundJob.message_id == sent.json()["id"]
    ).one()
    assert job.sms_account_id is None

    draft = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="Synthetic Chatwoot draft",
        direction="draft",
        author_type="ai",
        status="draft",
    )
    db_session.add(draft)
    db_session.commit()
    approved = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/approve",
        headers=operations_data["headers"],
    )
    repeated = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/approve",
        headers=operations_data["headers"],
    )
    assert approved.status_code == status.HTTP_200_OK
    assert repeated.status_code == status.HTTP_200_OK
    assert db_session.query(SmsOutboundJob).filter(
        SmsOutboundJob.message_id == draft.id,
        SmsOutboundJob.sms_account_id.is_(None),
    ).count() == 1

    binding.is_enabled = False
    db_session.commit()
    hidden = client.get(
        f"/api/admin/sms/conversations/{conversation.id}/messages",
        headers=operations_data["headers"],
    )
    assert hidden.status_code == status.HTTP_200_OK
    unavailable_send = client.post(
        f"/api/admin/sms/conversations/{conversation.id}/messages",
        json={
            "body": "Synthetic disabled-binding response",
            "client_request_id": "synthetic-disabled-binding",
        },
        headers=operations_data["headers"],
    )
    assert unavailable_send.status_code == status.HTTP_409_CONFLICT


def test_chatwoot_only_inbound_fails_closed_without_line_ai_configuration(
    db_session, operations_data
):
    binding = SmsChatwootBinding(
        tenant_id=operations_data["tenant"].id,
        provider_id=operations_data["provider"].id,
        chatwoot_account_id=81,
        chatwoot_inbox_id=82,
        chatwoot_base_url="https://chatwoot.invalid",
        chatwoot_api_token="synthetic-token",
        webhook_secret="synthetic-webhook-secret",
        is_enabled=True,
    )
    db_session.add(binding)
    db_session.commit()
    result = process_chatwoot_webhook(
        db_session,
        {
            "id": 83,
            "content": "Synthetic inbound question",
            "message_type": "incoming",
            "inbox": {"id": 82},
            "conversation": {"id": 84, "contact": {"id": 85}},
        },
        token="synthetic-webhook-secret",
    )
    conversation = db_session.query(SmsConversation).filter(
        SmsConversation.id == result["conversation_id"]
    ).one()
    assert conversation.state == "paused"
    assert conversation.ai_enabled is False
    assert result["ai_job_enqueued"] is False
    assert db_session.query(SmsAiJob).filter(
        SmsAiJob.conversation_id == conversation.id
    ).count() == 0


def test_chatwoot_same_inbox_id_isolated_by_binding_secret(
    db_session, operations_data
):
    other_tenant = Tenant(
        name="Synthetic Chatwoot Other", subdomain="synthetic-chatwoot-other"
    )
    db_session.add(other_tenant)
    db_session.commit()
    other_provider = Provider(
        tenant_id=other_tenant.id,
        name="Synthetic Chatwoot Other Provider",
        active=True,
    )
    db_session.add(other_provider)
    db_session.commit()
    bindings = [
        SmsChatwootBinding(
            tenant_id=operations_data["tenant"].id,
            provider_id=operations_data["provider"].id,
            chatwoot_account_id=91,
            chatwoot_inbox_id=92,
            chatwoot_base_url="https://chatwoot.invalid",
            chatwoot_api_token="synthetic-token-one",
            webhook_secret="synthetic-secret-one",
            is_enabled=True,
        ),
        SmsChatwootBinding(
            tenant_id=other_tenant.id,
            provider_id=other_provider.id,
            chatwoot_account_id=93,
            chatwoot_inbox_id=92,
            chatwoot_base_url="https://chatwoot.invalid",
            chatwoot_api_token="synthetic-token-two",
            webhook_secret="synthetic-secret-two",
            is_enabled=True,
        ),
    ]
    db_session.add_all(bindings)
    db_session.commit()
    result = process_chatwoot_webhook(
        db_session,
        {
            "id": 94,
            "content": "Synthetic isolated inbound",
            "message_type": "incoming",
            "inbox": {"id": 92},
            "conversation": {"id": 95, "contact": {"id": 96}},
        },
        token="synthetic-secret-two",
    )
    conversation = db_session.query(SmsConversation).filter(
        SmsConversation.id == result["conversation_id"]
    ).one()
    assert conversation.tenant_id == other_tenant.id
    assert conversation.provider_id == other_provider.id


def test_transitive_provider_and_client_scope_mismatches_fail_closed(
    client, db_session, operations_data
):
    other_tenant = Tenant(name="Synthetic Other Tenant", subdomain="synthetic-other")
    db_session.add(other_tenant)
    db_session.commit()
    other_provider = Provider(
        tenant_id=other_tenant.id, name="Synthetic Other Provider", active=True
    )
    other_client = Client(tenant_id=other_tenant.id, name="Synthetic Other Client")
    db_session.add_all([other_provider, other_client])
    db_session.commit()

    malformed_provider = SmsConversation(
        tenant_id=operations_data["tenant"].id,
        provider_id=other_provider.id,
        sms_account_id=operations_data["account"].id,
        customer_address="61410000991",
        state="taken-over",
    )
    malformed_client = SmsConversation(
        tenant_id=operations_data["tenant"].id,
        provider_id=operations_data["provider"].id,
        sms_account_id=operations_data["account"].id,
        client_id=other_client.id,
        customer_address="61410000992",
        state="taken-over",
    )
    db_session.add_all([malformed_provider, malformed_client])
    db_session.commit()
    for conversation in (malformed_provider, malformed_client):
        response = client.get(
            f"/api/admin/sms/conversations/{conversation.id}/messages",
            headers=operations_data["headers"],
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_duplicate_receipt_winner_requires_exact_account_scope(
    db_session, operations_data
):
    conversation = _conversation(
        db_session, operations_data, state="paused", suffix="61"
    )
    receipt = SmsInboundReceipt(
        sms_account_id=operations_data["account"].id,
        event_key="synthetic-receipt-hash",
        raw_payload=None,
    )
    db_session.add(receipt)
    db_session.commit()
    winner = find_duplicate_inbound_winner(
        db_session,
        account=operations_data["account"],
        receipt_key=receipt.event_key,
        customer_address=conversation.customer_address,
    )
    assert winner is not None
    assert winner[1].id == conversation.id

    other_account = SmsAccount(
        tenant_id=operations_data["tenant"].id,
        provider_id=operations_data["provider"].id,
        transport_type="simulator",
        display_name="Synthetic Other Line",
        sender_address="61410000009",
        is_enabled=True,
    )
    db_session.add(other_account)
    db_session.commit()
    assert find_duplicate_inbound_winner(
        db_session,
        account=other_account,
        receipt_key=receipt.event_key,
        customer_address=conversation.customer_address,
    ) is None


def test_openapi_requires_manual_idempotency_key_and_documents_conflict(
    client, db_session, operations_data
):
    document = client.app.openapi()
    create_schema = document["components"]["schemas"]["SmsMessageCreate"]
    assert set(create_schema["required"]) == {"body", "client_request_id"}
    operation = document["paths"][
        "/api/admin/sms/conversations/{conversation_id}/messages"
    ]["post"]
    assert {"200", "409", "422"}.issubset(operation["responses"])
    conversation = _conversation(
        db_session, operations_data, state="taken-over", suffix="71"
    )
    missing_key = client.post(
        f"/api/admin/sms/conversations/{conversation.id}/messages",
        json={"body": "Synthetic missing-key message"},
        headers=operations_data["headers"],
    )
    assert missing_key.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert db_session.query(SmsOutboundJob).count() == 0


@pytest.mark.parametrize(
    ("state", "ai_enabled", "suffix"),
    [
        ("paused", False, "81"),
        ("taken-over", False, "82"),
        ("needs-review", False, "83"),
        ("escalated", False, "84"),
        ("resolved", False, "85"),
        ("auto-reply", False, "86"),
    ],
)
def test_worker_quarantines_automated_jobs_in_protected_states(
    db_session, operations_data, state, ai_enabled, suffix
):
    conversation = _conversation(
        db_session,
        operations_data,
        state=state,
        suffix=suffix,
        ai_enabled=ai_enabled,
    )
    message = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body="Synthetic queued automated response",
        direction="outbound",
        author_type="ai",
        status="queued",
    )
    db_session.add(message)
    db_session.flush()
    job = SmsOutboundJob(
        message_id=message.id,
        sms_account_id=conversation.sms_account_id,
        status="PENDING",
    )
    db_session.add(job)
    db_session.commit()

    with (
        patch(
            "app.services.sms.ai_orchestrator.process_pending_sms_ai_jobs",
            new=AsyncMock(),
        ),
        patch("app.services.sms.arrival_service.process_repeated_arrival_alerts"),
        patch("app.services.sms.outbox_worker.get_transport_adapter") as transport,
    ):
        from app.services.sms.outbox_worker import process_pending_sms_outbound_jobs

        asyncio.run(process_pending_sms_outbound_jobs(db_session))

    db_session.refresh(job)
    db_session.refresh(message)
    assert job.status == "FAILED"
    assert job.error_log == "DELIVERY_STATE_BLOCKED"
    assert message.status == "failed"
    transport.assert_not_called()
    event = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == conversation.id,
        SmsConversationEvent.type == "outbound_delivery_quarantined",
    ).one()
    assert event.meta["message_id"] == message.id
    assert event.meta["reason"] == "DELIVERY_STATE_BLOCKED"


@pytest.mark.parametrize(
    ("direction", "message_status"),
    [("draft", "queued"), ("outbound", "discarded"), ("inbound", "queued")],
)
def test_worker_never_dispatches_non_deliverable_message_lifecycle(
    db_session, operations_data, direction, message_status
):
    conversation = _conversation(
        db_session, operations_data, state="taken-over", suffix=f"9{len(direction)}"
    )
    message = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body="Synthetic invalid lifecycle response",
        direction=direction,
        author_type="staff",
        status=message_status,
    )
    db_session.add(message)
    db_session.flush()
    job = SmsOutboundJob(
        message_id=message.id,
        sms_account_id=conversation.sms_account_id,
        status="PENDING",
    )
    db_session.add(job)
    db_session.commit()

    with (
        patch(
            "app.services.sms.ai_orchestrator.process_pending_sms_ai_jobs",
            new=AsyncMock(),
        ),
        patch("app.services.sms.arrival_service.process_repeated_arrival_alerts"),
        patch("app.services.sms.outbox_worker.get_transport_adapter") as transport,
    ):
        from app.services.sms.outbox_worker import process_pending_sms_outbound_jobs

        asyncio.run(process_pending_sms_outbound_jobs(db_session))

    db_session.refresh(job)
    assert job.status == "FAILED"
    transport.assert_not_called()


def test_worker_runs_independent_processors_without_outbound_and_redacts_exceptions(
    db_session, caplog
):
    canary = "SYNTHETIC_SECRET_PROMPT_CANARY"
    ai_processor = AsyncMock(side_effect=RuntimeError(canary))
    arrival_processor = MagicMock(side_effect=RuntimeError(canary))
    with (
        patch(
            "app.services.sms.ai_orchestrator.process_pending_sms_ai_jobs",
            new=ai_processor,
        ),
        patch(
            "app.services.sms.arrival_service.process_repeated_arrival_alerts",
            new=arrival_processor,
        ),
        caplog.at_level(logging.ERROR),
    ):
        from app.services.sms.outbox_worker import process_pending_sms_outbound_jobs

        asyncio.run(process_pending_sms_outbound_jobs(db_session))

    ai_processor.assert_awaited_once_with(db_session)
    arrival_processor.assert_called_once_with(db_session)
    assert canary not in caplog.text


def test_draft_routes_reject_non_ai_shape_and_blank_edits(
    client, db_session, operations_data
):
    conversation = _conversation(
        db_session, operations_data, state="taken-over", suffix="97"
    )
    malformed = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body="Synthetic customer-shaped draft",
        direction="draft",
        author_type="customer",
        status="draft",
    )
    db_session.add(malformed)
    db_session.commit()

    queue = client.get(
        "/api/admin/sms/conversations/drafts/queue",
        headers=operations_data["headers"],
    )
    assert queue.status_code == status.HTTP_200_OK
    assert malformed.id not in {item["id"] for item in queue.json()}
    approval = client.post(
        f"/api/admin/sms/conversations/messages/{malformed.id}/approve",
        headers=operations_data["headers"],
    )
    assert approval.status_code == status.HTTP_409_CONFLICT
    blank = client.post(
        f"/api/admin/sms/conversations/{conversation.id}/messages",
        json={"body": "   ", "client_request_id": "synthetic-blank-request"},
        headers=operations_data["headers"],
    )
    assert blank.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_correction_rejects_message_with_inconsistent_provider_scope(
    client, db_session, operations_data
):
    conversation = _conversation(
        db_session, operations_data, state="taken-over", suffix="98"
    )
    other_provider = Provider(
        tenant_id=operations_data["tenant"].id,
        name="Synthetic Inconsistent Provider",
        active=True,
    )
    db_session.add(other_provider)
    db_session.flush()
    malformed = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=other_provider.id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body="Synthetic malformed AI response",
        direction="outbound",
        author_type="ai",
        status="sent",
    )
    db_session.add(malformed)
    db_session.commit()

    response = client.post(
        f"/api/admin/sms/conversations/{conversation.id}/corrections",
        json={
            "message_id": malformed.id,
            "reason": "Synthetic correction evidence",
            "contains_dynamic_facts": False,
        },
        headers=operations_data["headers"],
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_retry_rejects_non_outbound_or_discarded_message(
    client, db_session, operations_data
):
    conversation = _conversation(
        db_session, operations_data, state="taken-over", suffix="99"
    )
    message = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body="Synthetic discarded draft",
        direction="draft",
        author_type="ai",
        status="discarded",
    )
    db_session.add(message)
    db_session.flush()
    job = SmsOutboundJob(
        message_id=message.id,
        sms_account_id=message.sms_account_id,
        status="FAILED",
    )
    db_session.add(job)
    db_session.commit()

    response = client.post(
        f"/api/admin/sms/conversations/jobs/{job.id}/retry",
        headers=operations_data["headers"],
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    db_session.refresh(job)
    assert job.status == "FAILED"


def test_draft_approval_then_bulk_discard_has_one_winner(
    client, db_session, operations_data
):
    conversation = _conversation(
        db_session, operations_data, state="taken-over", suffix="00"
    )
    draft = SmsMessage(
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=conversation.sms_account_id,
        conversation_id=conversation.id,
        body="Synthetic single-winner draft",
        direction="draft",
        author_type="ai",
        status="draft",
    )
    db_session.add(draft)
    db_session.commit()

    approved = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/approve",
        headers=operations_data["headers"],
    )
    discarded = client.post(
        "/api/admin/sms/conversations/drafts/bulk/discard",
        json={"message_ids": [draft.id], "reason": "Synthetic bulk cleanup"},
        headers=operations_data["headers"],
    )
    assert approved.status_code == status.HTTP_200_OK
    assert discarded.status_code == status.HTTP_409_CONFLICT
    db_session.refresh(draft)
    assert draft.status == "queued"
    assert db_session.query(SmsOutboundJob).filter(
        SmsOutboundJob.message_id == draft.id
    ).count() == 1
