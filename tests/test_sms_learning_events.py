"""Test suite for unified learning event ingestion across SMS conversations and bootcamp."""

from datetime import datetime, timezone
import pytest
from fastapi import status

from app.core.security import create_access_token
from app.models.client import Client
from app.models.curated_memory import KnowledgeProposal
from app.models.learning_event import LearningEvent, compute_text_diff
from app.models.provider import Provider
from app.models.sms_account import SmsAccount
from app.models.sms_bootcamp import (
    SmsBootcampConversation,
    SmsBootcampMessage,
    SmsBootcampRun,
    SmsBootcampSettings,
)
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture
def test_setup(db_session):
    # Tenant A
    tenant_a = Tenant(name="Tenant Alpha", subdomain="tenant-alpha")
    db_session.add(tenant_a)
    db_session.commit()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin@alpha.com",
        password_hash="hash_a",
        role="admin",
    )
    db_session.add(admin_a)

    provider_a = Provider(tenant_id=tenant_a.id, name="Provider Alpha", active=True)
    db_session.add(provider_a)
    db_session.commit()

    account_a = SmsAccount(
        tenant_id=tenant_a.id,
        provider_id=provider_a.id,
        transport_type="simulator",
        display_name="Alpha Line",
        sender_address="61400000001",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="draft",
    )
    db_session.add(account_a)
    db_session.commit()

    client_a = Client(tenant_id=tenant_a.id, name="Customer Alice", phone="61411111111")
    db_session.add(client_a)
    db_session.commit()

    conv_a = SmsConversation(
        tenant_id=tenant_a.id,
        provider_id=provider_a.id,
        sms_account_id=account_a.id,
        customer_address="61411111111",
        client_id=client_a.id,
        state="auto-reply",
        unread_count=0,
        is_pinned=False,
        is_blocked=False,
        ai_enabled=True,
    )
    db_session.add(conv_a)
    db_session.commit()

    # Tenant B (for multi-tenant isolation tests)
    tenant_b = Tenant(name="Tenant Beta", subdomain="tenant-beta")
    db_session.add(tenant_b)
    db_session.commit()

    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin@beta.com",
        password_hash="hash_b",
        role="admin",
    )
    db_session.add(admin_b)

    provider_b = Provider(tenant_id=tenant_b.id, name="Provider Beta", active=True)
    db_session.add(provider_b)
    db_session.commit()

    account_b = SmsAccount(
        tenant_id=tenant_b.id,
        provider_id=provider_b.id,
        transport_type="simulator",
        display_name="Beta Line",
        sender_address="61400000002",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="draft",
    )
    db_session.add(account_b)
    db_session.commit()

    conv_b = SmsConversation(
        tenant_id=tenant_b.id,
        provider_id=provider_b.id,
        sms_account_id=account_b.id,
        customer_address="61422222222",
        state="auto-reply",
        unread_count=0,
        is_pinned=False,
        is_blocked=False,
        ai_enabled=True,
    )
    db_session.add(conv_b)
    db_session.commit()

    return {
        "tenant_a": tenant_a,
        "admin_a": admin_a,
        "provider_a": provider_a,
        "account_a": account_a,
        "conv_a": conv_a,
        "headers_a": {
            "X-Tenant": "tenant-alpha",
            "X-Token": create_access_token({"sub": str(admin_a.id)}),
        },
        "tenant_b": tenant_b,
        "admin_b": admin_b,
        "provider_b": provider_b,
        "account_b": account_b,
        "conv_b": conv_b,
        "headers_b": {
            "X-Tenant": "tenant-beta",
            "X-Token": create_access_token({"sub": str(admin_b.id)}),
        },
    }


def test_diff_utility():
    """Verify compute_text_diff calculates structural additions, removals and ratios."""
    orig = "Hello world from Tori"
    mod = "Hello wonderful world from Tori and Frank"
    diff = compute_text_diff(orig, mod)
    assert diff["original_length"] == len(orig)
    assert diff["new_length"] == len(mod)
    assert diff["ratio"] < 1.0
    assert "wonderful" in diff["added"]
    assert "Frank" in diff["added"]


def test_production_answer_info_request_learning_event(client, test_setup, db_session):
    """POST /answer-info-request creates a LearningEvent with source=production_messages and event_type=knowledge_answer."""
    conv = test_setup["conv_a"]
    headers = test_setup["headers_a"]

    payload = {
        "question": "Do you provide hot stone therapy?",
        "answer": "Yes, hot stone therapy is available for 60 or 90 minute sessions.",
        "category": "services",
    }
    resp = client.post(
        f"/api/admin/sms/conversations/{conv.id}/answer-info-request",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "success"
    assert data["proposal_id"] is not None

    event = (
        db_session.query(LearningEvent)
        .filter(
            LearningEvent.conversation_id == str(conv.id),
            LearningEvent.event_type == "knowledge_answer",
        )
        .first()
    )
    assert event is not None
    assert event.source == "production_messages"
    assert event.customer_message == payload["question"]
    assert event.human_content == payload["answer"]
    assert event.status == "pending"
    assert event.confidence_score == 1.0
    assert event.tenant_id == test_setup["tenant_a"].id
    assert event.provider_id == test_setup["provider_a"].id


def test_production_draft_edit_creates_learning_event(client, test_setup, db_session):
    """POST /drafts/{id}/review with action=edit creates a draft_edit LearningEvent with diff payload."""
    conv = test_setup["conv_a"]
    headers = test_setup["headers_a"]

    draft = SmsMessage(
        tenant_id=test_setup["tenant_a"].id,
        provider_id=test_setup["provider_a"].id,
        sms_account_id=test_setup["account_a"].id,
        conversation_id=conv.id,
        direction="outbound",
        author_type="ai",
        status="draft",
        body="We are open 9am to 5pm on weekdays.",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(draft)
    db_session.commit()

    edited_text = "We are open 9am to 6pm on weekdays and 10am to 2pm on Saturday."
    resp = client.post(
        f"/api/admin/sms/conversations/drafts/{draft.id}/review",
        json={"action": "edit", "text": edited_text},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK

    event = (
        db_session.query(LearningEvent)
        .filter(
            LearningEvent.message_id == str(draft.id),
            LearningEvent.event_type == "draft_edit",
        )
        .first()
    )
    assert event is not None
    assert event.source == "production_messages"
    assert event.original_ai_content == "We are open 9am to 5pm on weekdays."
    assert event.human_content == edited_text
    assert event.confidence_score == 0.5
    assert event.status == "pending"
    assert event.diff_payload is not None
    assert event.diff_payload["original_length"] == len("We are open 9am to 5pm on weekdays.")
    assert event.diff_payload["new_length"] == len(edited_text)
    assert event.diff_payload["ratio"] < 1.0
    assert "Saturday." in event.diff_payload["added"]


def test_production_draft_approve_learning_event(client, test_setup, db_session):
    """Verify draft approval creates an approved_draft (confidence=0.2) or draft_edit event."""
    conv = test_setup["conv_a"]
    headers = test_setup["headers_a"]

    # 1. Direct approve unchanged via POST /messages/{id}/approve
    draft_1 = SmsMessage(
        tenant_id=test_setup["tenant_a"].id,
        provider_id=test_setup["provider_a"].id,
        sms_account_id=test_setup["account_a"].id,
        conversation_id=conv.id,
        direction="outbound",
        author_type="ai",
        status="draft",
        body="Your appointment is confirmed for tomorrow at 2pm.",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(draft_1)
    db_session.commit()

    resp_1 = client.post(
        f"/api/admin/sms/conversations/messages/{draft_1.id}/approve",
        headers=headers,
    )
    assert resp_1.status_code == status.HTTP_200_OK

    event_1 = (
        db_session.query(LearningEvent)
        .filter(
            LearningEvent.message_id == str(draft_1.id),
            LearningEvent.event_type == "approved_draft",
        )
        .first()
    )
    assert event_1 is not None
    assert event_1.source == "production_messages"
    assert event_1.confidence_score == 0.2
    assert event_1.original_ai_content == draft_1.body
    assert event_1.human_content == draft_1.body

    # 2. Approve with modified text via POST /drafts/{id}/review
    draft_2 = SmsMessage(
        tenant_id=test_setup["tenant_a"].id,
        provider_id=test_setup["provider_a"].id,
        sms_account_id=test_setup["account_a"].id,
        conversation_id=conv.id,
        direction="outbound",
        author_type="ai",
        status="draft",
        body="Please bring your ID.",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(draft_2)
    db_session.commit()

    resp_2 = client.post(
        f"/api/admin/sms/conversations/drafts/{draft_2.id}/review",
        json={"action": "approve", "text": "Please bring your ID and insurance card."},
        headers=headers,
    )
    assert resp_2.status_code == status.HTTP_200_OK

    event_2 = (
        db_session.query(LearningEvent)
        .filter(
            LearningEvent.message_id == str(draft_2.id),
            LearningEvent.event_type == "draft_edit",
        )
        .first()
    )
    assert event_2 is not None
    assert event_2.confidence_score == 0.5
    assert event_2.human_content == "Please bring your ID and insurance card."
    assert "insurance" in event_2.diff_payload["added"]


def test_production_corrections_learning_event_and_proposal(client, test_setup, db_session):
    """POST /corrections creates flagged_response LearningEvent and a KnowledgeProposal with tenant isolation."""
    conv = test_setup["conv_a"]
    headers = test_setup["headers_a"]

    # Customer asks question
    cust_msg = SmsMessage(
        tenant_id=test_setup["tenant_a"].id,
        provider_id=test_setup["provider_a"].id,
        sms_account_id=test_setup["account_a"].id,
        conversation_id=conv.id,
        direction="inbound",
        author_type="customer",
        status="delivered",
        body="Can I cancel within 2 hours?",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(cust_msg)

    # AI sends flawed response
    ai_msg = SmsMessage(
        tenant_id=test_setup["tenant_a"].id,
        provider_id=test_setup["provider_a"].id,
        sms_account_id=test_setup["account_a"].id,
        conversation_id=conv.id,
        direction="outbound",
        author_type="ai",
        status="delivered",
        body="Yes, cancellations are free anytime before the appointment.",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(ai_msg)
    db_session.commit()

    corr_payload = {
        "message_id": ai_msg.id,
        "reason": "Policy requires at least 24 hours notice for free cancellation",
        "corrected_wording": "No, cancellations require 24 hours notice to avoid a late fee.",
        "contains_dynamic_facts": False,
    }
    resp = client.post(
        f"/api/admin/sms/conversations/{conv.id}/corrections",
        json=corr_payload,
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["status"] == "recorded"
    assert data["knowledge_changed"] is False
    assert data["proposal_id"] is not None
    assert data["learning_event_id"] is not None

    # Check LearningEvent
    event = (
        db_session.query(LearningEvent)
        .filter(LearningEvent.id == data["learning_event_id"])
        .first()
    )
    assert event is not None
    assert event.source == "production_messages"
    assert event.event_type == "flagged_response"
    assert event.customer_message == cust_msg.body
    assert event.original_ai_content == ai_msg.body
    assert event.human_content == corr_payload["corrected_wording"]
    assert event.metadata_payload["reason"] == corr_payload["reason"]
    assert event.confidence_score == 1.0
    assert event.status == "pending"
    assert event.tenant_id == test_setup["tenant_a"].id

    # Check KnowledgeProposal
    proposal = (
        db_session.query(KnowledgeProposal)
        .filter(KnowledgeProposal.id == data["proposal_id"])
        .first()
    )
    assert proposal is not None
    assert proposal.proposal_type == "conflict"
    assert proposal.authority == "production_correction"
    assert proposal.requires_review is True
    assert proposal.user_query == cust_msg.body
    assert proposal.proposed_response == corr_payload["corrected_wording"]
    assert proposal.tenant_id == test_setup["tenant_a"].id


def test_bootcamp_learning_events(client, test_setup, db_session):
    """Verify bootcamp information response, correction, and draft review ingest source=bootcamp."""
    tenant = test_setup["tenant_a"]
    headers = test_setup["headers_a"]

    # Setup bootcamp run & conversation
    run = SmsBootcampRun(
        tenant_id=tenant.id,
        status="running",
        selected_personas=["inpatient_ian"],
        max_turns=3,
        style_profile={},
    )
    db_session.add(run)
    db_session.commit()

    conv = SmsBootcampConversation(
        run_id=run.id,
        tenant_id=tenant.id,
        persona_id="inpatient_ian",
        persona_name="Inpatient Ian",
        status="handoff",
        current_turn=1,
        needs_handoff=True,
        handoff_reason="Need info about parking permit",
    )
    db_session.add(conv)
    db_session.commit()

    cust_msg = SmsBootcampMessage(
        id="bootcamp-msg-1",
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="persona",
        text="Do I need a parking permit?",
        meta={"status": "received"},
    )
    db_session.add(cust_msg)
    db_session.commit()

    # 1. Bootcamp Info Request Response -> knowledge_answer
    resp_info = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/information-request/respond",
        json={"information": "Customer parking is free in visitor bays 1 to 5."},
        headers=headers,
    )
    assert resp_info.status_code == status.HTTP_200_OK

    info_event = (
        db_session.query(LearningEvent)
        .filter(
            LearningEvent.conversation_id == conv.id,
            LearningEvent.event_type == "knowledge_answer",
        )
        .first()
    )
    assert info_event is not None
    assert info_event.source == "bootcamp"
    assert info_event.customer_message == cust_msg.text
    assert info_event.human_content == "Customer parking is free in visitor bays 1 to 5."
    assert info_event.confidence_score == 1.0

    # 2. Bootcamp Correction -> flagged_response
    tori_msg = (
        db_session.query(SmsBootcampMessage)
        .filter(
            SmsBootcampMessage.conversation_id == conv.id,
            SmsBootcampMessage.role == "tori",
        )
        .first()
    )
    assert tori_msg is not None

    resp_corr = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/corrections",
        json={
            "messageId": tori_msg.id,
            "reason": "Visitor bays have changed to 6 to 10",
            "correctedWording": "Customer parking is in visitor bays 6 to 10.",
            "containsDynamicFacts": False,
        },
        headers=headers,
    )
    assert resp_corr.status_code == status.HTTP_200_OK
    corr_event_id = resp_corr.json()["learning_event_id"]

    corr_event = db_session.query(LearningEvent).filter(LearningEvent.id == corr_event_id).first()
    assert corr_event is not None
    assert corr_event.source == "bootcamp"
    assert corr_event.event_type == "flagged_response"
    assert corr_event.confidence_score == 1.0
    assert corr_event.human_content == "Customer parking is in visitor bays 6 to 10."

    # 3. Bootcamp Draft Review -> draft_edit & approved_draft
    draft_msg_edit = SmsBootcampMessage(
        id="bootcamp-draft-edit",
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="tori",
        text="Draft text original",
        meta={"status": "draft"},
    )
    draft_msg_unchanged = SmsBootcampMessage(
        id="bootcamp-draft-unchanged",
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="tori",
        text="Draft text to remain unchanged",
        meta={"status": "draft"},
    )
    db_session.add_all([draft_msg_edit, draft_msg_unchanged])
    db_session.commit()

    # Edit review
    resp_draft_edit = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/drafts/{draft_msg_edit.id}/review",
        json={"action": "approve", "text": "Draft text modified by human"},
        headers=headers,
    )
    assert resp_draft_edit.status_code == status.HTTP_200_OK
    edit_id = resp_draft_edit.json()["learning_event_id"]
    event_draft_edit = db_session.query(LearningEvent).filter(LearningEvent.id == edit_id).first()
    assert event_draft_edit is not None
    assert event_draft_edit.source == "bootcamp"
    assert event_draft_edit.event_type == "draft_edit"
    assert event_draft_edit.confidence_score == 0.5
    assert event_draft_edit.human_content == "Draft text modified by human"
    assert event_draft_edit.diff_payload is not None

    # Unchanged review
    resp_draft_same = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/drafts/{draft_msg_unchanged.id}/review",
        json={"action": "approve"},
        headers=headers,
    )
    assert resp_draft_same.status_code == status.HTTP_200_OK
    same_id = resp_draft_same.json()["learning_event_id"]
    event_draft_same = db_session.query(LearningEvent).filter(LearningEvent.id == same_id).first()
    assert event_draft_same is not None
    assert event_draft_same.source == "bootcamp"
    assert event_draft_same.event_type == "approved_draft"
    assert event_draft_same.confidence_score == 0.2


def test_multi_tenant_isolation_on_learning_events(client, test_setup, db_session):
    """Verify tenant isolation on learning events query, corrections, and draft reviews."""
    headers_a = test_setup["headers_a"]
    headers_b = test_setup["headers_b"]
    conv_a = test_setup["conv_a"]
    conv_b = test_setup["conv_b"]

    # Tenant A answers info request
    client.post(
        f"/api/admin/sms/conversations/{conv_a.id}/answer-info-request",
        json={"question": "Tenant A question", "answer": "Tenant A answer"},
        headers=headers_a,
    )

    # Tenant B lists learning events -> should NOT see Tenant A's events
    resp_b = client.get("/api/admin/sms/conversations/learning-events", headers=headers_b)
    assert resp_b.status_code == status.HTTP_200_OK
    events_b = resp_b.json()
    assert len(events_b) == 0

    # Tenant A lists learning events -> sees own events
    resp_a = client.get("/api/admin/sms/conversations/learning-events", headers=headers_a)
    assert resp_a.status_code == status.HTTP_200_OK
    events_a = resp_a.json()
    assert len(events_a) == 1
    assert events_a[0]["customer_message"] == "Tenant A question"

    # Tenant B tries to correct Tenant A conversation -> 404
    resp_cross_corr = client.post(
        f"/api/admin/sms/conversations/{conv_a.id}/corrections",
        json={
            "message_id": 999,
            "reason": "Hacking tenant",
            "corrected_wording": "Malicious payload",
            "contains_dynamic_facts": False,
        },
        headers=headers_b,
    )
    assert resp_cross_corr.status_code == status.HTTP_404_NOT_FOUND


def test_learning_events_list_and_summary_endpoint(client, test_setup, db_session):
    """Verify GET /learning-events with filters and GET /learning-events/summary."""
    headers = test_setup["headers_a"]
    conv = test_setup["conv_a"]

    # Seed 2 events
    client.post(
        f"/api/admin/sms/conversations/{conv.id}/answer-info-request",
        json={"question": "Question 1", "answer": "Answer 1"},
        headers=headers,
    )
    client.post(
        f"/api/admin/sms/conversations/{conv.id}/answer-info-request",
        json={"question": "Question 2", "answer": "Answer 2"},
        headers=headers,
    )

    # Summary
    resp_summary = client.get(
        "/api/admin/sms/conversations/learning-events/summary",
        headers=headers,
    )
    assert resp_summary.status_code == status.HTTP_200_OK
    summary = resp_summary.json()
    assert summary["total_count"] == 2
    assert summary["pending_count"] == 2
    assert summary["by_source"]["production_messages"] == 2
    assert summary["by_type"]["knowledge_answer"] == 2

    # Filter by source
    resp_filter = client.get(
        "/api/admin/sms/conversations/learning-events?source=production_messages&event_type=knowledge_answer",
        headers=headers,
    )
    assert resp_filter.status_code == status.HTTP_200_OK
    assert len(resp_filter.json()) == 2
