"""Tests for Codex Control Centre (CCC) Autonomous Agent Bridge Service & Endpoints."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.business_assistant import (
    BusinessAssistantConversation,
    BusinessAssistantMessage,
    SupportTicket,
    SupportTicketEvent,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.ccc_bridge_service import (
    CCCBridgeService,
    ccc_bridge_service,
)


def _create_actor(db_session: Session, suffix: str, role: str = "owner", tenant: Tenant | None = None) -> tuple[Tenant, User]:
    if tenant is None:
        tenant = Tenant(name=f"CCC Tenant {suffix}", subdomain=f"ccc-{suffix}")
        db_session.add(tenant)
        db_session.flush()
    user = User(tenant_id=tenant.id, login=f"ccc-{role}-{suffix}", password_hash="hash", role=role)
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def _create_ticket(
    db_session: Session,
    tenant: Tenant,
    user: User,
    status: str = "awaiting_engineering",
    coding_task_id: str | None = None,
    conversation_id: int | None = None,
    suffix: str = "default",
) -> SupportTicket:
    dedup_key = f"dedup-ccc-{tenant.id}-{user.id}-{suffix}"
    ticket = SupportTicket(
        tenant_id=tenant.id,
        user_id=user.id,
        conversation_id=conversation_id,
        category="bug",
        severity="high",
        status=status,
        title=f"Payment webhook idempotency failure {suffix}",
        description="Duplicate charge records logged on high load.",
        observed_behaviour="Multiple records created.",
        affected_product_area="checkout",
        user_impact="High - customer confusion.",
        acceptance_criteria="Ensure single record per webhook ID.",
        coding_task_id=coding_task_id,
        deduplication_key=dedup_key,
        authorisation_state="not_required",
        requires_owner_approval=False,
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)
    return ticket


# ==============================================================================
# 1. CCCBridgeService Unit Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_ccc_bridge_dispatch_ticket_success(db_session: Session):
    tenant, user = _create_actor(db_session, "dispatch-unit")
    ticket = _create_ticket(db_session, tenant, user, status="awaiting_engineering")

    bridge = CCCBridgeService(ccc_url="http://127.0.0.1:4500", ccc_token="test-token")

    # Mock httpx AsyncClient responses for create_thread and start_turn
    mock_post = AsyncMock()

    async def side_effect(url, **kwargs):
        if "/codex/threads" in url:
            return httpx.Response(200, json={"id": f"wt-{ticket.id}", "status": "created"})
        elif "/codex/turns/start" in url:
            return httpx.Response(200, json={"turn_id": 1, "status": "running"})
        return httpx.Response(404)

    mock_post.side_effect = side_effect

    with patch("httpx.AsyncClient.post", mock_post):
        with patch.object(bridge, "ensure_sse_listener"):
            res = await bridge.dispatch_ticket(ticket.id, db_session)

    assert res["status"] == "in_progress"
    assert res["ticket_id"] == ticket.id
    assert res["thread_id"] == f"wt-{ticket.id}"
    assert res["turn_id"] == 1
    assert res["workspace"] == f"worktrees/wt-{ticket.id}"

    db_session.refresh(ticket)
    assert ticket.status == "in_progress"
    assert ticket.coding_task_id == f"wt-{ticket.id}"

    # Verify event logged
    events = (
        db_session.query(SupportTicketEvent)
        .filter(SupportTicketEvent.ticket_id == ticket.id)
        .all()
    )
    assert len(events) == 1
    assert events[0].event_type == "dispatched_to_ccc"
    assert events[0].safe_metadata["thread_id"] == f"wt-{ticket.id}"
    assert events[0].safe_metadata["workspace"] == f"worktrees/wt-{ticket.id}"


@pytest.mark.asyncio
async def test_ccc_bridge_dispatch_ticket_already_dispatched(db_session: Session):
    tenant, user = _create_actor(db_session, "already-unit")
    ticket = _create_ticket(
        db_session,
        tenant,
        user,
        status="in_progress",
        coding_task_id="thread-existing-123",
    )

    bridge = CCCBridgeService(ccc_url="http://127.0.0.1:4500")
    with patch.object(bridge, "ensure_sse_listener") as mock_ensure:
        res = await bridge.dispatch_ticket(ticket.id, db_session)

    assert res["already_dispatched"] is True
    assert res["status"] == "in_progress"
    assert res["thread_id"] == "thread-existing-123"
    mock_ensure.assert_called_once()


@pytest.mark.asyncio
async def test_ccc_bridge_dispatch_ticket_not_found(db_session: Session):
    bridge = CCCBridgeService()
    with pytest.raises(LookupError, match="Ticket #999999 not found"):
        await bridge.dispatch_ticket(999999, db_session)


@pytest.mark.asyncio
async def test_ccc_bridge_steer_ticket_success(db_session: Session):
    tenant, user = _create_actor(db_session, "steer-unit")
    ticket = _create_ticket(
        db_session,
        tenant,
        user,
        status="in_progress",
        coding_task_id="thread-active-456",
    )

    bridge = CCCBridgeService(ccc_url="http://127.0.0.1:4500")

    mock_post = AsyncMock(return_value=httpx.Response(200, json={"status": "steered"}))
    with patch("httpx.AsyncClient.post", mock_post):
        res = await bridge.steer_ticket(
            ticket.id,
            "Target checkout webhook idempotency key validation.",
            db_session,
        )

    assert res["status"] == "steered"
    assert res["ticket_id"] == ticket.id
    assert res["thread_id"] == "thread-active-456"

    # Verify steer milestone event
    event = (
        db_session.query(SupportTicketEvent)
        .filter(
            SupportTicketEvent.ticket_id == ticket.id,
            SupportTicketEvent.event_type == "engineering_steer_sent",
        )
        .first()
    )
    assert event is not None
    assert event.safe_metadata["instruction"] == "Target checkout webhook idempotency key validation."
    assert event.safe_metadata["thread_id"] == "thread-active-456"


@pytest.mark.asyncio
async def test_ccc_bridge_steer_ticket_not_dispatched_raises_error(db_session: Session):
    tenant, user = _create_actor(db_session, "not-disp")
    ticket = _create_ticket(db_session, tenant, user, status="awaiting_engineering", coding_task_id=None)

    bridge = CCCBridgeService()
    with pytest.raises(ValueError, match="has not been dispatched"):
        await bridge.steer_ticket(ticket.id, "some instruction", db_session)


def test_ccc_bridge_record_ui_verify_receipt_resolves_ticket(db_session: Session):
    tenant, user = _create_actor(db_session, "verify-receipt")
    ticket = _create_ticket(
        db_session,
        tenant,
        user,
        status="awaiting_verification",
        coding_task_id="thread-verify-789",
    )

    bridge = CCCBridgeService()
    receipt = {
        "verified": True,
        "receipt_state": "verified",
        "route": "/admin/checkout",
        "verified_elements": ["checkout-form", "webhook-listener"],
        "resolution_summary": "Idempotency duplicate record issue verified fixed on checkout page.",
    }
    res = bridge.record_ui_verify_receipt(
        ticket_id=ticket.id,
        receipt_data=receipt,
        db=db_session,
        actor_user_id=user.id,
    )

    assert res["status"] == "resolved"
    db_session.refresh(ticket)
    assert ticket.status == "resolved"
    assert "Idempotency duplicate record issue verified fixed" in ticket.resolution_summary

    event = (
        db_session.query(SupportTicketEvent)
        .filter(
            SupportTicketEvent.ticket_id == ticket.id,
            SupportTicketEvent.event_type == "ui_verification_receipt",
        )
        .first()
    )
    assert event is not None
    assert event.safe_metadata["route"] == "/admin/checkout"
    assert event.safe_metadata["verified"] is True


def test_ccc_bridge_sse_milestone_processing(db_session: Session):
    tenant, user = _create_actor(db_session, "sse-milestone")
    conversation = BusinessAssistantConversation(
        tenant_id=tenant.id,
        user_id=user.id,
        title="Remediation Session",
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    ticket = _create_ticket(
        db_session,
        tenant,
        user,
        status="in_progress",
        coding_task_id="wt-ticket-999",
        conversation_id=conversation.id,
    )

    bridge = CCCBridgeService()

    # 1. Test turn_started
    bridge._process_sse_milestone(
        current_event_type="turn_started",
        payload={"turn_id": 1},
        ticket_id=ticket.id,
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        thread_id="wt-ticket-999",
        db=db_session,
    )
    event_start = (
        db_session.query(SupportTicketEvent)
        .filter(SupportTicketEvent.ticket_id == ticket.id, SupportTicketEvent.event_type == "engineering_turn_started")
        .first()
    )
    assert event_start is not None

    # 2. Test file_change
    bridge._process_sse_milestone(
        current_event_type="file_change",
        payload={"path": "app/services/checkout.py", "diff": "@@ -1 +1 @@"},
        ticket_id=ticket.id,
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        thread_id="wt-ticket-999",
        db=db_session,
    )
    event_file = (
        db_session.query(SupportTicketEvent)
        .filter(SupportTicketEvent.ticket_id == ticket.id, SupportTicketEvent.event_type == "file_modified")
        .first()
    )
    assert event_file is not None

    # 3. Test approval_requested / clarification dispatch to conversation
    bridge._process_sse_milestone(
        current_event_type="approval_requested",
        payload={"consequence": "Should we discard or re-attempt duplicate webhook payloads?"},
        ticket_id=ticket.id,
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        thread_id="wt-ticket-999",
        db=db_session,
    )
    event_clarify = (
        db_session.query(SupportTicketEvent)
        .filter(SupportTicketEvent.ticket_id == ticket.id, SupportTicketEvent.event_type == "clarification_requested")
        .first()
    )
    assert event_clarify is not None

    # Assert conversation message was added for clarification
    msg = (
        db_session.query(BusinessAssistantMessage)
        .filter(
            BusinessAssistantMessage.conversation_id == conversation.id,
            BusinessAssistantMessage.role == "business_assistant",
        )
        .first()
    )
    assert msg is not None
    assert f"[Codex Autonomous Engineer Clarification on Ticket #{ticket.id}]" in msg.content
    assert "Should we discard or re-attempt duplicate webhook payloads?" in msg.content

    # 4. Test turn_completed moves ticket to awaiting_verification
    bridge._process_sse_milestone(
        current_event_type="turn_completed",
        payload={"status": "completed", "summary": "Fix applied and tests passed."},
        ticket_id=ticket.id,
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        thread_id="wt-ticket-999",
        db=db_session,
    )
    db_session.refresh(ticket)
    assert ticket.status == "awaiting_verification"


# ==============================================================================
# 2. Router Endpoint API Tests
# ==============================================================================

def test_api_dispatch_ticket_ccc(client, db_session: Session):
    tenant, owner = _create_actor(db_session, "api-dispatch", role="owner")
    _t, staff = _create_actor(db_session, "api-staff", role="staff", tenant=tenant)
    other_tenant, other_owner = _create_actor(db_session, "other-api", role="owner")

    ticket = _create_ticket(db_session, tenant, owner, status="awaiting_engineering")

    owner_headers = _headers(tenant, owner)
    staff_headers = _headers(tenant, staff)
    other_headers = _headers(other_tenant, other_owner)

    # 1. Staff role forbidden
    staff_resp = client.post(
        f"/api/admin/business-assistant/tickets/{ticket.id}/dispatch-ccc",
        headers=staff_headers,
    )
    assert staff_resp.status_code == 403

    # 2. Cross-tenant access not found
    other_resp = client.post(
        f"/api/admin/business-assistant/tickets/{ticket.id}/dispatch-ccc",
        headers=other_headers,
    )
    assert other_resp.status_code == 404

    # 3. Owner dispatch succeeds
    mock_post = AsyncMock()

    async def side_effect(url, **kwargs):
        if "/codex/threads" in url:
            return httpx.Response(200, json={"id": f"wt-{ticket.id}", "status": "created"})
        elif "/codex/turns/start" in url:
            return httpx.Response(200, json={"turn_id": 10, "status": "running"})
        return httpx.Response(404)

    mock_post.side_effect = side_effect

    with patch("httpx.AsyncClient.post", mock_post):
        with patch.object(ccc_bridge_service, "ensure_sse_listener"):
            resp = client.post(
                f"/api/admin/business-assistant/tickets/{ticket.id}/dispatch-ccc",
                headers=owner_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_id"] == ticket.id
    assert data["status"] == "in_progress"
    assert data["thread_id"] == f"wt-{ticket.id}"
    assert data["turn_id"] == 10
    assert data["workspace"] == f"worktrees/wt-{ticket.id}"


def test_api_steer_ticket(client, db_session: Session):
    tenant, owner = _create_actor(db_session, "api-steer", role="owner")
    _t, staff = _create_actor(db_session, "api-steer-staff", role="staff", tenant=tenant)

    ticket = _create_ticket(
        db_session,
        tenant,
        owner,
        status="in_progress",
        coding_task_id="thread-active-999",
    )

    owner_headers = _headers(tenant, owner)
    staff_headers = _headers(tenant, staff)

    # 1. Staff forbidden
    staff_resp = client.post(
        f"/api/admin/business-assistant/tickets/{ticket.id}/steer",
        headers=staff_headers,
        json={"instruction": "Please make sure to run regression tests."},
    )
    assert staff_resp.status_code == 403

    # 2. Owner steers successfully
    mock_post = AsyncMock(return_value=httpx.Response(200, json={"status": "steered"}))
    with patch("httpx.AsyncClient.post", mock_post):
        resp = client.post(
            f"/api/admin/business-assistant/tickets/{ticket.id}/steer",
            headers=owner_headers,
            json={"instruction": "Please make sure to run regression tests."},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "steered"
    assert data["ticket_id"] == ticket.id
    assert data["thread_id"] == "thread-active-999"
    assert data["instruction"] == "Please make sure to run regression tests."


def test_api_verify_receipt(client, db_session: Session):
    tenant, owner = _create_actor(db_session, "api-receipt", role="owner")
    ticket = _create_ticket(
        db_session,
        tenant,
        owner,
        status="awaiting_verification",
        coding_task_id="thread-verify-555",
    )

    owner_headers = _headers(tenant, owner)

    payload = {
        "verified": True,
        "receipt_state": "verified",
        "route": "/admin/bookings",
        "verified_elements": ["table-row-1", "edit-button"],
        "resolution_summary": "Bug verified fixed in live browser session.",
    }
    resp = client.post(
        f"/api/admin/business-assistant/tickets/{ticket.id}/verify-receipt",
        headers=owner_headers,
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["ticket"]["id"] == ticket.id
    assert data["ticket"]["status"] == "resolved"
    assert data["event"]["event_type"] == "ui_verification_receipt"
    assert data["event"]["safe_metadata"]["route"] == "/admin/bookings"
