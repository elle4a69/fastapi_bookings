import pytest
from datetime import datetime, timezone, timedelta
from fastapi import status
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.user import User
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsOutboundJob, SmsConversationEvent, SmsNote
from app.models.sms_quick_tool import SmsQuickTool
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.sms_knowledge import SmsKnowledgeEntry
from app.core.security import create_access_token


@pytest.fixture
def setup_controls_test_data(db_session):
    tenant = Tenant(name="Controls Tenant", subdomain="controls-test")
    db_session.add(tenant)
    db_session.commit()

    admin = User(
        tenant_id=tenant.id,
        login="admin@controlstest.com",
        password_hash="hash",
        role="admin",
    )
    db_session.add(admin)
    db_session.commit()

    provider = Provider(tenant_id=tenant.id, name="Therapist Sam", active=True)
    db_session.add(provider)
    db_session.commit()

    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Main Line",
        sender_address="61411111111",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="draft",
    )
    db_session.add(account)
    db_session.commit()

    conv = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        customer_address="61422222222",
        state="auto-reply",
        unread_count=1,
        is_pinned=False,
        is_blocked=False,
        ai_enabled=True,
    )
    db_session.add(conv)
    db_session.commit()

    return {
        "tenant": tenant,
        "admin": admin,
        "provider": provider,
        "account": account,
        "conversation": conv,
        "headers": {
            "X-Tenant": "controls-test",
            "X-Token": create_access_token({"sub": str(admin.id)}),
        },
    }


def test_update_conversation_controls(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]

    # 1. Enqueue a pending AI job to verify it cancels when AI is disabled
    job = SmsAiJob(
        conversation_id=conv.id,
        customer_turn_ref="ref-123",
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()

    # 2. PATCH controls: pin conversation and disable AI
    payload = {
        "is_pinned": True,
        "ai_enabled": False,
    }
    resp = client.patch(
        f"/api/admin/sms/conversations/{conv.id}/controls",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["is_pinned"] is True
    assert data["ai_enabled"] is False
    assert data["state"] == "paused"

    # Verify AI job was cancelled
    db_session.refresh(job)
    assert job.status == "CANCELLED"

    # 3. Block conversation
    resp_block = client.patch(
        f"/api/admin/sms/conversations/{conv.id}/controls",
        json={"is_blocked": True},
        headers=headers,
    )
    assert resp_block.status_code == status.HTTP_200_OK
    data_block = resp_block.json()
    assert data_block["is_blocked"] is True
    assert data_block["ai_enabled"] is False


def test_quick_tools_defaults_and_persistence(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    tenant = setup_controls_test_data["tenant"]
    admin = setup_controls_test_data["admin"]

    # 1. GET quick tools when none saved yet -> should return 5 defaults
    resp = client.get("/api/admin/sms/conversations/quick-tools", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    tools = resp.json()
    assert len(tools) == 5
    labels = [t["label"] for t in tools]
    assert labels == ["ADDR", "HOURS", "LINK", "PARKING", "POLICIES"]

    # 2. POST to slot 0: update ADDR
    new_slot = {
        "slot_index": 0,
        "label": "ADDR",
        "content": "742 Evergreen Terrace, Springfield",
    }
    post_resp = client.post(
        "/api/admin/sms/conversations/quick-tools",
        json=new_slot,
        headers=headers,
    )
    assert post_resp.status_code == status.HTTP_200_OK
    saved = post_resp.json()
    assert saved["slot_index"] == 0
    assert saved["label"] == "ADDR"
    assert saved["content"] == "742 Evergreen Terrace, Springfield"
    assert saved["id"] is not None

    # Verify in DB
    db_tool = db_session.query(SmsQuickTool).filter(
        SmsQuickTool.tenant_id == tenant.id,
        SmsQuickTool.user_id == admin.id,
        SmsQuickTool.slot_index == 0,
    ).first()
    assert db_tool is not None
    assert db_tool.content == "742 Evergreen Terrace, Springfield"

    # 3. GET quick tools again -> slot 0 updated, slots 1-4 default
    resp2 = client.get("/api/admin/sms/conversations/quick-tools", headers=headers)
    tools2 = resp2.json()
    assert len(tools2) == 5
    assert tools2[0]["content"] == "742 Evergreen Terrace, Springfield"
    assert tools2[1]["label"] == "HOURS"

    # 4. Out-of-range slot validation (e.g. slot 5 or -1)
    err_slot = client.post(
        "/api/admin/sms/conversations/quick-tools",
        json={"slot_index": 5, "label": "EXTRA", "content": "Too many slots"},
        headers=headers,
    )
    assert err_slot.status_code == 422

    # 5. Overlength label validation (>8 chars)
    err_label = client.post(
        "/api/admin/sms/conversations/quick-tools",
        json={"slot_index": 1, "label": "TOOLONGLABEL", "content": "Content"},
        headers=headers,
    )
    assert err_label.status_code == 422


def test_answer_info_request(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    tenant = setup_controls_test_data["tenant"]
    admin = setup_controls_test_data["admin"]

    memories_before = db_session.query(CuratedMemory).count()
    drafts_before = db_session.query(SmsMessage).filter(
        SmsMessage.conversation_id == conv.id,
        SmsMessage.status == "draft",
    ).count()

    payload = {
        "question": "What is your refund policy?",
        "answer": "Full refund is available if cancelled at least 24h prior.",
        "category": "policy",
    }
    resp = client.post(
        f"/api/admin/sms/conversations/{conv.id}/answer-info-request",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "success"
    assert "proposal_id" in data
    proposal_id = data["proposal_id"]

    # CRITICAL: live knowledge must NEVER be modified directly
    assert db_session.query(CuratedMemory).count() == memories_before
    assert db_session.query(SmsMessage).filter(
        SmsMessage.conversation_id == conv.id,
        SmsMessage.status == "draft",
    ).count() == drafts_before

    # Verify KnowledgeProposal created in pending status
    proposal = db_session.query(KnowledgeProposal).filter(KnowledgeProposal.id == proposal_id).first()
    assert proposal is not None
    assert proposal.tenant_id == tenant.id
    assert proposal.provider_id == conv.provider_id
    assert proposal.status == "pending"
    assert proposal.proposal_type == "gap"
    assert proposal.category == "policy"
    assert proposal.user_query == "What is your refund policy?"
    assert proposal.proposed_response == "Full refund is available if cancelled at least 24h prior."

    # Verify SmsConversationEvent recorded
    event = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "info_request_proposal_created",
        )
        .order_by(SmsConversationEvent.id.desc())
        .first()
    )
    assert event is not None
    assert event.meta["actor_id"] == admin.id
    assert event.meta["proposal_id"] == proposal_id
    assert event.meta["proposal_type"] == "gap"
    assert event.meta["category"] == "policy"


def test_knowledge_proposals_list_and_resolve(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    tenant = setup_controls_test_data["tenant"]
    provider = setup_controls_test_data["provider"]
    admin = setup_controls_test_data["admin"]

    # 1. Seed two pending proposals
    p1 = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=provider.id,
        proposal_type="gap",
        status="pending",
        category="faq",
        knowledge_kind="durable_fact",
        authority="conversation_candidate",
        user_query="Do you have parking?",
        proposed_response="Yes, free parking is available in the rear lot.",
        fingerprint="fp-test-parking-1",
        reason_code="staff_info_request_answer",
        confidence_score=1.0,
    )
    p2 = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=provider.id,
        proposal_type="add",
        status="pending",
        category="policy",
        knowledge_kind="durable_fact",
        authority="conversation_candidate",
        user_query="Can I bring pets?",
        proposed_response="Only registered service animals are permitted.",
        fingerprint="fp-test-pets-2",
        reason_code="curator_suggestion",
        confidence_score=0.9,
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    # 2. List proposals via main route
    resp = client.get("/api/admin/sms/knowledge/proposals", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    proposals = resp.json()
    ids = [p["id"] for p in proposals]
    assert p1.id in ids
    assert p2.id in ids

    # List proposals via aliases
    resp_alias_conv = client.get("/api/admin/sms/conversations/knowledge/proposals", headers=headers)
    assert resp_alias_conv.status_code == status.HTTP_200_OK
    assert p1.id in [p["id"] for p in resp_alias_conv.json()]

    # 3. Approve proposal p1
    approve_resp = client.post(
        f"/api/admin/sms/knowledge/proposals/{p1.id}/resolve",
        json={"action": "approve"},
        headers=headers,
    )
    assert approve_resp.status_code == status.HTTP_200_OK
    db_session.refresh(p1)
    assert p1.status == "accepted"
    assert p1.reviewed_by_user_id == admin.id
    assert p1.target_memory_id is not None

    # Verify CuratedMemory created and active
    curated = db_session.query(CuratedMemory).filter(CuratedMemory.id == p1.target_memory_id).first()
    assert curated is not None
    assert curated.tenant_id == tenant.id
    assert curated.category == "faq"
    assert curated.user_query == "Do you have parking?"
    assert curated.ideal_response == "Yes, free parking is available in the rear lot."
    assert curated.status == "active"
    assert curated.authority == "owner_verified"
    assert curated.verified_by_user_id == admin.id

    # Verify SmsKnowledgeEntry created and approved
    entry = (
        db_session.query(SmsKnowledgeEntry)
        .filter(SmsKnowledgeEntry.tenant_id == tenant.id, SmsKnowledgeEntry.source == f"proposal:{p1.id}")
        .first()
    )
    assert entry is not None
    assert entry.status == "approved"
    assert entry.approved_by_id == admin.id

    # 4. Dismiss proposal p2
    curated_count_before = db_session.query(CuratedMemory).count()
    dismiss_resp = client.post(
        f"/api/admin/sms/knowledge/proposals/{p2.id}/resolve",
        json={"action": "dismiss"},
        headers=headers,
    )
    assert dismiss_resp.status_code == status.HTTP_200_OK
    db_session.refresh(p2)
    assert p2.status == "dismissed"
    assert p2.reviewed_by_user_id == admin.id
    # Dismissed proposal does NOT create CuratedMemory
    assert db_session.query(CuratedMemory).count() == curated_count_before

    # 5. GET pending proposals now returns neither p1 nor p2
    resp_pending = client.get("/api/admin/sms/knowledge/proposals", headers=headers)
    assert resp_pending.status_code == status.HTTP_200_OK
    pending_ids = [p["id"] for p in resp_pending.json()]
    assert p1.id not in pending_ids
    assert p2.id not in pending_ids

    # 6. GET with status=all returns both
    resp_all = client.get("/api/admin/sms/knowledge/proposals?status=all", headers=headers)
    assert resp_all.status_code == status.HTTP_200_OK
    all_ids = [p["id"] for p in resp_all.json()]
    assert p1.id in all_ids
    assert p2.id in all_ids


def test_knowledge_proposals_merge_and_validation(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    tenant = setup_controls_test_data["tenant"]
    provider = setup_controls_test_data["provider"]
    admin = setup_controls_test_data["admin"]

    # 1. Existing curated memory
    existing_mem = CuratedMemory(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="faq",
        user_query="Wi-Fi password?",
        ideal_response="OldPassword123",
        status="active",
        verified_by_user_id=admin.id,
    )
    db_session.add(existing_mem)
    db_session.commit()

    # 2. Proposal to update Wi-Fi info
    p = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=provider.id,
        proposal_type="supersede",
        status="pending",
        category="faq",
        user_query="Wi-Fi password?",
        proposed_response="GuestNet2026",
        fingerprint="fp-test-wifi-update",
        reason_code="staff_update",
    )
    db_session.add(p)
    db_session.commit()

    # 3. Merge into existing memory
    resp = client.post(
        f"/api/admin/sms/knowledge/proposals/{p.id}/resolve",
        json={
            "action": "merge",
            "target_memory_id": existing_mem.id,
            "ideal_response": "GuestNet2026! (case-sensitive)",
        },
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    db_session.refresh(existing_mem)
    db_session.refresh(p)
    assert existing_mem.ideal_response == "GuestNet2026! (case-sensitive)"
    assert p.status == "resolved"
    assert p.target_memory_id == existing_mem.id

    # 4. Invalid action rejection
    invalid_resp = client.post(
        f"/api/admin/sms/knowledge/proposals/{p.id}/resolve",
        json={"action": "unsupported_action"},
        headers=headers,
    )
    assert invalid_resp.status_code == status.HTTP_400_BAD_REQUEST


def test_drafts_queue_and_review(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    tenant = setup_controls_test_data["tenant"]

    # Preceding inbound message
    inbound_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    inbound_msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Can I book an appointment tomorrow?",
        direction="inbound",
        author_type="customer",
        status="received",
        occurred_at=inbound_time,
        received_at=inbound_time,
    )
    db_session.add(inbound_msg)
    db_session.commit()

    # 1. Create a draft message
    draft = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Draft message awaiting review",
        direction="draft",
        author_type="ai",
        status="draft",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(draft)
    db_session.commit()

    # 2. Check drafts queue
    queue_resp = client.get(
        "/api/admin/sms/conversations/drafts/queue", headers=headers
    )
    assert queue_resp.status_code == status.HTTP_200_OK
    queue = queue_resp.json()
    assert len(queue) >= 1
    draft_item = next(q for q in queue if q["id"] == draft.id)
    assert draft_item["inbound_snippet"] == "Can I book an appointment tomorrow?"

    # 3. Review: Edit
    edit_resp = client.post(
        f"/api/admin/sms/conversations/drafts/{draft.id}/review",
        json={"action": "edit", "text": "Edited draft message"},
        headers=headers,
    )
    assert edit_resp.status_code == status.HTTP_200_OK
    db_session.refresh(draft)
    assert draft.body == "Edited draft message"
    assert draft.status == "draft"

    # 4. Review: Approve
    approve_resp = client.post(
        f"/api/admin/sms/conversations/drafts/{draft.id}/review",
        json={"action": "approve"},
        headers=headers,
    )
    assert approve_resp.status_code == status.HTTP_200_OK
    db_session.refresh(draft)
    assert draft.status == "queued"
    assert draft.direction == "outbound"

    # Verify outbound job was enqueued
    job = db_session.query(SmsOutboundJob).filter(
        SmsOutboundJob.message_id == draft.id
    ).first()
    assert job is not None
    assert job.status == "PENDING"

    # 5. Create another draft and test discard
    draft2 = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Another draft",
        direction="draft",
        author_type="ai",
        status="draft",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(draft2)
    db_session.commit()

    discard_resp = client.post(
        f"/api/admin/sms/conversations/drafts/{draft2.id}/review",
        json={"action": "discard"},
        headers=headers,
    )
    assert discard_resp.status_code == status.HTTP_200_OK
    db_session.refresh(draft2)
    assert draft2.status == "discarded"


def test_drafts_bulk_discard_and_audit(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    tenant = setup_controls_test_data["tenant"]

    now = datetime.now(timezone.utc)
    d1 = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Draft 1 for bulk discard",
        direction="draft",
        author_type="ai",
        status="draft",
        occurred_at=now - timedelta(seconds=10),
        received_at=now - timedelta(seconds=10),
    )
    d2 = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Draft 2 for bulk discard",
        direction="draft",
        author_type="ai",
        status="draft",
        occurred_at=now - timedelta(seconds=5),
        received_at=now - timedelta(seconds=5),
    )
    db_session.add_all([d1, d2])
    db_session.commit()

    resp = client.post(
        "/api/admin/sms/conversations/drafts/bulk/discard",
        json={"message_ids": [d1.id, d2.id], "reason": "Batch clear"},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["discarded_count"] == 2

    db_session.refresh(d1)
    db_session.refresh(d2)
    assert d1.status == "discarded"
    assert d2.status == "discarded"

    event = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "drafts_bulk_discarded",
        )
        .order_by(SmsConversationEvent.id.desc())
        .first()
    )
    assert event is not None
    assert event.type == "drafts_bulk_discarded"
    assert event.meta["discarded_count"] == 2
    assert event.meta["reason"] == "Batch clear"


def test_simulate_inbound_and_webhooks(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    acc = setup_controls_test_data["account"]

    # 1. Test /sms/conversations/simulate-inbound
    sim_payload = {
        "account_id": acc.id,
        "sender": "61499998888",
        "message": "Hi, what services do you offer?",
        "execute_dialogue_turn": False,
    }
    resp = client.post(
        "/api/admin/sms/conversations/simulate-inbound",
        json=sim_payload,
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "success"
    assert "conversation_id" in data
    assert "message_id" in data

    # 2. Test /api/sms/webhooks/incoming
    webhook_payload = {
        "message_id": "webhook-sim-1",
        "sender": "61499998888",
        "to": acc.sender_address,
        "message": "Another message via webhook incoming",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "account_public_id": acc.public_id,
        "transport_type": acc.transport_type,
    }
    webhook_resp = client.post(
        "/api/sms/webhooks/incoming",
        json=webhook_payload,
    )
    assert webhook_resp.status_code == status.HTTP_200_OK
    assert webhook_resp.json()["status"] == "success"


def test_approve_draft_message(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    tenant = setup_controls_test_data["tenant"]
    admin = setup_controls_test_data["admin"]

    # 1. Create a draft message
    draft = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Draft reply requiring approval",
        direction="draft",
        author_type="ai",
        status="draft",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(draft)
    db_session.commit()

    # 2. Approve draft
    resp = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/approve",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    db_session.refresh(draft)
    assert draft.status == "queued"
    assert draft.direction == "outbound"

    # Verify SmsOutboundJob created with status PENDING
    outbound_jobs = (
        db_session.query(SmsOutboundJob)
        .filter(SmsOutboundJob.message_id == draft.id)
        .all()
    )
    assert len(outbound_jobs) == 1
    job = outbound_jobs[0]
    assert job.status == "PENDING"
    assert job.sms_account_id == conv.sms_account_id

    # Verify SmsConversationEvent inserted
    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "draft_approved",
        )
        .all()
    )
    assert len(events) == 1
    event = events[0]
    assert event.meta["actor_id"] == admin.id
    assert event.meta["message_id"] == draft.id

    # 3. Idempotency: second call returns 200 without creating duplicate outbox job or event
    resp_second = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/approve",
        headers=headers,
    )
    assert resp_second.status_code == status.HTTP_200_OK
    outbound_jobs_second = (
        db_session.query(SmsOutboundJob)
        .filter(SmsOutboundJob.message_id == draft.id)
        .all()
    )
    assert len(outbound_jobs_second) == 1
    events_second = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "draft_approved",
        )
        .all()
    )
    assert len(events_second) == 1

    # 4. Rejecting non-draft message returns 409
    sent_msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Already sent message",
        direction="outbound",
        author_type="staff",
        status="failed",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(sent_msg)
    db_session.commit()

    resp_non_draft = client.post(
        f"/api/admin/sms/conversations/messages/{sent_msg.id}/approve",
        headers=headers,
    )
    assert resp_non_draft.status_code == status.HTTP_409_CONFLICT

    # 5. Cannot approve draft if conversation is blocked
    conv.is_blocked = True
    db_session.commit()

    draft_blocked = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Draft in blocked thread",
        direction="draft",
        author_type="ai",
        status="draft",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(draft_blocked)
    db_session.commit()

    resp_blocked = client.post(
        f"/api/admin/sms/conversations/messages/{draft_blocked.id}/approve",
        headers=headers,
    )
    assert resp_blocked.status_code == status.HTTP_409_CONFLICT
    conv.is_blocked = False
    db_session.commit()


def test_discard_draft_message(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    tenant = setup_controls_test_data["tenant"]
    admin = setup_controls_test_data["admin"]

    # 1. Create a draft message
    draft = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Draft to be discarded",
        direction="draft",
        author_type="ai",
        status="draft",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(draft)
    db_session.commit()

    # 2. Discard draft
    resp = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/discard",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    db_session.refresh(draft)
    assert draft.status == "discarded"

    # Verify event inserted
    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "draft_discarded",
        )
        .all()
    )
    assert len(events) == 1
    event = events[0]
    assert event.meta["actor_id"] == admin.id
    assert event.meta["message_id"] == draft.id

    # 3. Rejecting non-draft message returns 400
    # Calling discard on already discarded message (status="discarded")
    resp_again = client.post(
        f"/api/admin/sms/conversations/messages/{draft.id}/discard",
        headers=headers,
    )
    assert resp_again.status_code == status.HTTP_400_BAD_REQUEST

    # Inbound message (status="received") rejection returns 400
    inbound_msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Incoming inquiry",
        direction="inbound",
        author_type="customer",
        status="received",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(inbound_msg)
    db_session.commit()

    resp_inbound = client.post(
        f"/api/admin/sms/conversations/messages/{inbound_msg.id}/discard",
        headers=headers,
    )
    assert resp_inbound.status_code == status.HTTP_400_BAD_REQUEST


def test_conversation_takeover(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    admin = setup_controls_test_data["admin"]

    # Ensure conversation is in auto-reply and AI enabled
    conv.state = "auto-reply"
    conv.ai_enabled = True
    db_session.commit()

    # Enqueue a pending AI job
    job = SmsAiJob(
        conversation_id=conv.id,
        customer_turn_ref="turn-takeover-1",
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()

    resp = client.post(
        f"/api/admin/sms/conversations/{conv.id}/takeover",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["state"] == "taken-over"
    assert data["ai_enabled"] is False

    db_session.refresh(conv)
    assert conv.state == "taken-over"
    assert conv.ai_enabled is False

    # Pending AI job cancelled
    db_session.refresh(job)
    assert job.status == "CANCELLED"

    # Event inserted with type="conversation_takeover"
    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "conversation_takeover",
        )
        .all()
    )
    assert len(events) >= 1
    event = events[-1]
    assert event.meta["actor_id"] == admin.id
    assert event.meta["from_state"] == "auto-reply"
    assert event.meta["to_state"] == "taken-over"


def test_conversation_release(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    admin = setup_controls_test_data["admin"]

    # Put conversation into taken-over state
    conv.state = "taken-over"
    conv.ai_enabled = False
    conv.is_blocked = False
    db_session.commit()

    resp = client.post(
        f"/api/admin/sms/conversations/{conv.id}/release",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["state"] == "auto-reply"
    assert data["ai_enabled"] is True

    db_session.refresh(conv)
    assert conv.state == "auto-reply"
    assert conv.ai_enabled is True

    # Event inserted with type="conversation_release"
    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "conversation_release",
        )
        .all()
    )
    assert len(events) >= 1
    event = events[-1]
    assert event.meta["actor_id"] == admin.id
    assert event.meta["from_state"] == "taken-over"
    assert event.meta["to_state"] == "auto-reply"

    # Ineligible state: releasing when already in auto-reply returns 409
    resp_ineligible = client.post(
        f"/api/admin/sms/conversations/{conv.id}/release",
        headers=headers,
    )
    assert resp_ineligible.status_code == status.HTTP_409_CONFLICT

    # Ineligible state: blocked conversation returns 409
    conv.state = "taken-over"
    conv.is_blocked = True
    conv.ai_enabled = False
    db_session.commit()

    resp_blocked = client.post(
        f"/api/admin/sms/conversations/{conv.id}/release",
        headers=headers,
    )
    assert resp_blocked.status_code == status.HTTP_409_CONFLICT
    conv.is_blocked = False
    db_session.commit()


def test_conversation_escalate(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    admin = setup_controls_test_data["admin"]

    conv.state = "auto-reply"
    conv.ai_enabled = True
    db_session.commit()

    # Pending AI job to verify cancellation on escalation
    job = SmsAiJob(
        conversation_id=conv.id,
        customer_turn_ref="turn-escalate-1",
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()

    # 1. Missing reason returns 409
    resp_missing_body = client.post(
        f"/api/admin/sms/conversations/{conv.id}/escalate",
        headers=headers,
    )
    assert resp_missing_body.status_code == status.HTTP_409_CONFLICT

    resp_empty_json = client.post(
        f"/api/admin/sms/conversations/{conv.id}/escalate",
        json={},
        headers=headers,
    )
    assert resp_empty_json.status_code == status.HTTP_409_CONFLICT

    resp_whitespace = client.post(
        f"/api/admin/sms/conversations/{conv.id}/escalate",
        json={"reason": "    "},
        headers=headers,
    )
    assert resp_whitespace.status_code == status.HTTP_409_CONFLICT

    # 2. Valid reason succeeds
    resp_valid = client.post(
        f"/api/admin/sms/conversations/{conv.id}/escalate",
        json={"reason": "Customer expressed distress"},
        headers=headers,
    )
    assert resp_valid.status_code == status.HTTP_200_OK
    data = resp_valid.json()
    assert data["state"] == "escalated"
    assert data["ai_enabled"] is False

    db_session.refresh(conv)
    assert conv.state == "escalated"
    assert conv.ai_enabled is False

    # Verify pending AI job was cancelled
    db_session.refresh(job)
    assert job.status == "CANCELLED"

    # Verify event inserted
    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "conversation_escalate",
        )
        .all()
    )
    assert len(events) >= 1
    event = events[-1]
    assert event.meta["actor_id"] == admin.id
    assert event.meta["reason"] == "Customer expressed distress"
    assert event.meta["from_state"] == "auto-reply"
    assert event.meta["to_state"] == "escalated"


def test_conversation_resolve(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    admin = setup_controls_test_data["admin"]

    conv.state = "escalated"
    conv.ai_enabled = False
    db_session.commit()

    # 1. Missing reason returns 409
    resp_missing_body = client.post(
        f"/api/admin/sms/conversations/{conv.id}/resolve",
        headers=headers,
    )
    assert resp_missing_body.status_code == status.HTTP_409_CONFLICT

    resp_empty_json = client.post(
        f"/api/admin/sms/conversations/{conv.id}/resolve",
        json={},
        headers=headers,
    )
    assert resp_empty_json.status_code == status.HTTP_409_CONFLICT

    resp_whitespace = client.post(
        f"/api/admin/sms/conversations/{conv.id}/resolve",
        json={"reason": "   "},
        headers=headers,
    )
    assert resp_whitespace.status_code == status.HTTP_409_CONFLICT

    # 2. Valid reason succeeds
    resp_valid = client.post(
        f"/api/admin/sms/conversations/{conv.id}/resolve",
        json={"reason": "Issue resolved with clinic supervisor"},
        headers=headers,
    )
    assert resp_valid.status_code == status.HTTP_200_OK
    data = resp_valid.json()
    assert data["state"] == "resolved"
    assert data["ai_enabled"] is False

    db_session.refresh(conv)
    assert conv.state == "resolved"

    # Verify event inserted
    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "conversation_resolve",
        )
        .all()
    )
    assert len(events) >= 1
    event = events[-1]
    assert event.meta["actor_id"] == admin.id
    assert event.meta["reason"] == "Issue resolved with clinic supervisor"
    assert event.meta["from_state"] == "escalated"
    assert event.meta["to_state"] == "resolved"


def test_conversation_notes(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    admin = setup_controls_test_data["admin"]

    resp = client.post(
        f"/api/admin/sms/conversations/{conv.id}/notes",
        json={"text": "Spoke to customer via phone, agreed to session reschedule."},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert "id" in data
    note_id = data["id"]

    # Verify SmsNote persisted with author_id and text
    note = db_session.query(SmsNote).filter(SmsNote.id == note_id).first()
    assert note is not None
    assert note.conversation_id == conv.id
    assert note.author_id == admin.id
    assert note.text == "Spoke to customer via phone, agreed to session reschedule."

    # Verify SmsConversationEvent inserted
    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "internal_note_added",
        )
        .all()
    )
    assert len(events) >= 1
    event = events[-1]
    assert event.meta["actor_id"] == admin.id
    assert event.meta["note_id"] == note.id


def test_conversation_timeline(client, setup_controls_test_data, db_session):
    headers = setup_controls_test_data["headers"]
    conv = setup_controls_test_data["conversation"]
    tenant = setup_controls_test_data["tenant"]
    admin = setup_controls_test_data["admin"]

    now = datetime.now(timezone.utc)

    # 1. Insert a message
    msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=conv.provider_id,
        sms_account_id=conv.sms_account_id,
        conversation_id=conv.id,
        body="Timeline inquiry message",
        direction="inbound",
        author_type="customer",
        status="received",
        occurred_at=now - timedelta(minutes=10),
        received_at=now - timedelta(minutes=10),
    )
    db_session.add(msg)

    # 2. Insert an internal note
    note = SmsNote(
        conversation_id=conv.id,
        author_id=admin.id,
        text="Timeline internal note observation",
        created_at=now - timedelta(minutes=5),
    )
    db_session.add(note)

    # 3. Insert an event
    event = SmsConversationEvent(
        conversation_id=conv.id,
        type="conversation_takeover",
        meta={"actor_id": admin.id, "from_state": "auto-reply", "to_state": "taken-over"},
        created_at=now - timedelta(minutes=2),
    )
    db_session.add(event)
    db_session.commit()

    # 4. Fetch timeline
    resp = client.get(
        f"/api/admin/sms/conversations/{conv.id}/timeline",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()
    assert len(items) >= 3

    kinds = {item["kind"] for item in items}
    assert "message" in kinds
    assert "internal_note" in kinds
    assert "event" in kinds

    # Verify message kind fields
    msg_item = next(item for item in items if item["kind"] == "message" and item["id"] == msg.id)
    assert msg_item["body"] == "Timeline inquiry message"
    assert msg_item["direction"] == "inbound"
    assert msg_item["author_type"] == "customer"
    assert msg_item["status"] == "received"
    assert "occurred_at" in msg_item

    # Verify internal_note kind fields
    note_item = next(item for item in items if item["kind"] == "internal_note" and item["id"] == note.id)
    assert note_item["body"] == "Timeline internal note observation"
    assert note_item["author_id"] == admin.id
    assert "occurred_at" in note_item

    # Verify event kind fields
    event_item = next(item for item in items if item["kind"] == "event" and item["id"] == event.id)
    assert event_item["event_type"] == "conversation_takeover"
    assert event_item["meta"]["actor_id"] == admin.id
    assert event_item["meta"]["to_state"] == "taken-over"
    assert "occurred_at" in event_item

    # Verify chronological ordering
    parsed_dates = [
        datetime.fromisoformat(item["occurred_at"].replace("Z", "+00:00"))
        for item in items
        if item.get("occurred_at")
    ]
    assert parsed_dates == sorted(parsed_dates)


def test_multi_tenant_isolation_ui_controls(client, setup_controls_test_data, db_session):
    conv_a = setup_controls_test_data["conversation"]
    tenant_a = setup_controls_test_data["tenant"]

    # Create draft in Tenant A
    draft_a = SmsMessage(
        tenant_id=tenant_a.id,
        provider_id=conv_a.provider_id,
        sms_account_id=conv_a.sms_account_id,
        conversation_id=conv_a.id,
        body="Tenant A secret draft",
        direction="draft",
        author_type="ai",
        status="draft",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(draft_a)
    db_session.commit()

    # Create Tenant B and Admin B
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b")
    db_session.add(tenant_b)
    db_session.commit()

    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin@tenantb.com",
        password_hash="hash",
        role="admin",
    )
    db_session.add(admin_b)
    db_session.commit()

    headers_b = {
        "X-Tenant": "tenant-b",
        "X-Token": create_access_token({"sub": str(admin_b.id)}),
    }

    # Tenant B attempts actions on Tenant A resources -> all 404
    assert (
        client.post(
            f"/api/admin/sms/conversations/messages/{draft_a.id}/approve",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            f"/api/admin/sms/conversations/messages/{draft_a.id}/discard",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            f"/api/admin/sms/conversations/{conv_a.id}/takeover",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            f"/api/admin/sms/conversations/{conv_a.id}/release",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            f"/api/admin/sms/conversations/{conv_a.id}/escalate",
            json={"reason": "Malicious cross-tenant attempt"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            f"/api/admin/sms/conversations/{conv_a.id}/resolve",
            json={"reason": "Malicious cross-tenant attempt"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            f"/api/admin/sms/conversations/{conv_a.id}/notes",
            json={"text": "Cross-tenant note"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.get(
            f"/api/admin/sms/conversations/{conv_a.id}/timeline",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    # Tenant B queue does not expose Tenant A drafts
    queue_b = client.get("/api/admin/sms/conversations/drafts/queue", headers=headers_b).json()
    assert not any(d["id"] == draft_a.id for d in queue_b)

    # Tenant B cannot bulk discard Tenant A drafts
    assert (
        client.post(
            "/api/admin/sms/conversations/drafts/bulk/discard",
            json={"message_ids": [draft_a.id], "reason": "Cross tenant discard"},
            headers=headers_b,
        ).status_code
        == status.HTTP_409_CONFLICT
    )

    # Multi-tenant isolation for Knowledge Proposals & Info Requests
    proposal_a = KnowledgeProposal(
        tenant_id=tenant_a.id,
        proposal_type="gap",
        status="pending",
        category="faq",
        user_query="Cross-tenant question?",
        proposed_response="Confidential answer",
        fingerprint="fp-cross-tenant-1",
        reason_code="staff_info_request_answer",
    )
    db_session.add(proposal_a)
    db_session.commit()

    # Tenant B cannot submit info request answer to Tenant A conversation
    assert (
        client.post(
            f"/api/admin/sms/conversations/{conv_a.id}/answer-info-request",
            json={"question": "Q?", "answer": "A"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    # Tenant B cannot see Tenant A's knowledge proposal
    proposals_b = client.get("/api/admin/sms/knowledge/proposals", headers=headers_b).json()
    assert not any(p["id"] == proposal_a.id for p in proposals_b)

    # Tenant B cannot resolve Tenant A's knowledge proposal
    assert (
        client.post(
            f"/api/admin/sms/knowledge/proposals/{proposal_a.id}/resolve",
            json={"action": "approve"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    # Verify Tenant A proposal remains untouched
    db_session.refresh(proposal_a)
    assert proposal_a.status == "pending"
    assert proposal_a.reviewed_by_user_id is None

