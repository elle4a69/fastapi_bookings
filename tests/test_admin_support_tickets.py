"""Comprehensive test suite for Platform Owner Support Ticket Review Queue and Codex Launch Bridge.

Tests:
1. Strict platform owner gate (401 unauthenticated, 403 non-owners, 200 owner).
2. Cross-tenant listing, message count, latest activity, and status/tenant filtering.
3. Full detail view including internal-only notes and audit events.
4. Status and triage priority mutation with audit logging.
5. Internal notes and tenant replies posting.
6. Isolated Codex thread & turn launch and ticket status progression.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.database import SessionLocal as CodexSessionLocal
from backend.models.codex import Turn as CodexTurn

from app.core.security import create_access_token
from app.models.support_ticket import SupportTicket, SupportTicketAuditEvent, SupportTicketMessage
from app.models.tenant import Tenant
from app.models.user import User


def _create_user(db_session: Session, suffix: str, role: str = "owner", tenant: Tenant | None = None) -> tuple[Tenant, User, dict[str, str]]:
    if tenant is None:
        tenant = Tenant(name=f"Admin Test Tenant {suffix}", subdomain=f"adm-test-{suffix}")
        db_session.add(tenant)
        db_session.flush()

    user = User(
        tenant_id=tenant.id,
        login=f"user-{role}-{suffix}",
        password_hash="fake-hash",
        role=role,
    )
    db_session.add(user)
    db_session.commit()

    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }
    return tenant, user, headers


def test_platform_owner_gate_enforcement(client: TestClient, db_session: Session):
    """Endpoints reject unauthenticated and non-owner callers with 401/403."""
    tenant, _, client_headers = _create_user(db_session, "gate-client", role="client")
    _, _, provider_headers = _create_user(db_session, "gate-provider", role="provider", tenant=tenant)
    _, _, owner_headers = _create_user(db_session, "gate-owner", role="owner", tenant=tenant)

    # 1. Unauthenticated -> 401
    res_unauth = client.get("/api/admin/support-tickets", headers={"X-Tenant": tenant.subdomain})
    assert res_unauth.status_code == 401

    # 2. Non-owner (client) -> 403
    res_client = client.get("/api/admin/support-tickets", headers=client_headers)
    assert res_client.status_code == 403

    # 3. Non-owner (provider) -> 403
    res_provider = client.get("/api/admin/support-tickets", headers=provider_headers)
    assert res_provider.status_code == 403

    # 4. Platform Owner -> 200
    res_owner = client.get("/api/admin/support-tickets", headers=owner_headers)
    assert res_owner.status_code == 200


def test_list_tickets_cross_tenant_and_filtering(client: TestClient, db_session: Session):
    """Platform owner can view tickets across multiple tenants, with filtering and message count."""
    tenant_a, user_a, _ = _create_user(db_session, "t-a", role="owner")
    tenant_b, user_b, _ = _create_user(db_session, "t-b", role="owner")
    _, platform_owner, owner_headers = _create_user(db_session, "t-boss", role="owner")

    ticket_a = SupportTicket(
        tenant_id=tenant_a.id,
        created_by_user_id=user_a.id,
        title="Tenant A Issue",
        description="Booking sync latency",
        category="technical",
        status="received",
        triage_priority="normal",
    )
    ticket_b = SupportTicket(
        tenant_id=tenant_b.id,
        created_by_user_id=user_b.id,
        title="Tenant B Issue",
        description="Payment webhook error",
        category="billing",
        status="under_review",
        triage_priority="high",
    )
    db_session.add_all([ticket_a, ticket_b])
    db_session.commit()

    # Add a message to ticket A
    msg_a = SupportTicketMessage(
        ticket_id=ticket_a.id,
        sender_user_id=user_a.id,
        sender_type="tenant_user",
        visibility="tenant_visible",
        body="Any updates on this?",
    )
    db_session.add(msg_a)
    db_session.commit()

    # Query all tickets
    res = client.get("/api/admin/support-tickets", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    ticket_ids = [t["id"] for t in data]
    assert ticket_a.id in ticket_ids
    assert ticket_b.id in ticket_ids

    # Check message count
    item_a = next(t for t in data if t["id"] == ticket_a.id)
    assert item_a["message_count"] == 1
    assert "latest_activity_at" in item_a
    assert item_a["tenant_status"] == "Received"

    # Filter by status="under_review"
    res_filtered_status = client.get("/api/admin/support-tickets?status=under_review", headers=owner_headers)
    assert res_filtered_status.status_code == 200
    filtered_ids = [t["id"] for t in res_filtered_status.json()]
    assert ticket_b.id in filtered_ids
    assert ticket_a.id not in filtered_ids

    # Filter by tenant_id
    res_filtered_tenant = client.get(f"/api/admin/support-tickets?tenant_id={tenant_a.id}", headers=owner_headers)
    assert res_filtered_tenant.status_code == 200
    tenant_ids = [t["tenant_id"] for t in res_filtered_tenant.json()]
    assert all(tid == tenant_a.id for tid in tenant_ids)


def test_get_ticket_detail_with_messages_and_audit(client: TestClient, db_session: Session):
    """GET /api/admin/support-tickets/{ticket_id} returns all messages (including internal) and audit log."""
    tenant, user, _ = _create_user(db_session, "detail-t", role="owner")
    _, owner, owner_headers = _create_user(db_session, "detail-boss", role="owner")

    ticket = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Database migration error",
        description="Alembic check fails on custom table",
        category="technical",
        status="received",
        error_context={"error_code": "PG_CONN_TIMEOUT", "route": "/admin/schema"},
    )
    db_session.add(ticket)
    db_session.flush()

    # Public message from tenant
    msg1 = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=user.id,
        sender_type="tenant_user",
        visibility="tenant_visible",
        body="It stopped working after 5pm",
    )
    # Internal note from owner
    msg2 = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=owner.id,
        sender_type="platform_owner",
        visibility="internal_only",
        body="Internal engineering note: check db connection pool",
    )
    # Audit event
    event1 = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=user.id,
        action="created",
        event_data={"has_error_context": True},
    )
    db_session.add_all([msg1, msg2, event1])
    db_session.commit()

    res = client.get(f"/api/admin/support-tickets/{ticket.id}", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == ticket.id
    assert data["error_context"]["error_code"] == "PG_CONN_TIMEOUT"
    assert len(data["messages"]) == 2

    # Internal message must be visible to platform owner
    internal_msgs = [m for m in data["messages"] if m["visibility"] == "internal_only"]
    assert len(internal_msgs) == 1
    assert "connection pool" in internal_msgs[0]["body"]

    # Audit events must be populated
    assert len(data["audit_events"]) >= 1
    assert data["audit_events"][0]["action"] == "created"


def test_patch_ticket_status_and_priority(client: TestClient, db_session: Session):
    """Platform owner can update ticket status and priority with audit trails."""
    tenant, user, _ = _create_user(db_session, "status-t", role="owner")
    _, _, owner_headers = _create_user(db_session, "status-boss", role="owner")

    ticket = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Billing invoice typo",
        description="Incorrect unit price on invoice #102",
        category="billing",
        status="received",
        triage_priority="normal",
    )
    db_session.add(ticket)
    db_session.commit()

    # 1. Update status to in_progress and priority to critical
    res = client.patch(
        f"/api/admin/support-tickets/{ticket.id}/status",
        json={"status": "in_progress", "triage_priority": "critical"},
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "in_progress"
    assert data["triage_priority"] == "critical"

    # Verify audit event recorded
    audit_events = data["audit_events"]
    status_event = next((e for e in audit_events if e["action"] == "status_changed"), None)
    assert status_event is not None
    assert status_event["event_data"]["old_status"] == "received"
    assert status_event["event_data"]["new_status"] == "in_progress"
    assert status_event["event_data"]["new_priority"] == "critical"

    # 2. Update status to resolved -> verify resolved_at is set
    res_resolved = client.patch(
        f"/api/admin/support-tickets/{ticket.id}/status",
        json={"status": "resolved"},
        headers=owner_headers,
    )
    assert res_resolved.status_code == 200
    assert res_resolved.json()["status"] == "resolved"
    assert res_resolved.json()["resolved_at"] is not None

    # 3. Invalid status rejected
    res_bad = client.patch(
        f"/api/admin/support-tickets/{ticket.id}/status",
        json={"status": "invalid_status_xyz"},
        headers=owner_headers,
    )
    assert res_bad.status_code == 422


def test_post_internal_note_and_tenant_reply(client: TestClient, db_session: Session):
    """Platform owner can post internal notes (internal_only) and tenant replies (tenant_visible)."""
    tenant, user, _ = _create_user(db_session, "msg-t", role="owner")
    _, _, owner_headers = _create_user(db_session, "msg-boss", role="owner")

    ticket = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Calendar sync error",
        description="Google Calendar token expired",
        category="technical",
        status="received",
    )
    db_session.add(ticket)
    db_session.commit()

    # 1. Post internal note
    res_note = client.post(
        f"/api/admin/support-tickets/{ticket.id}/internal-note",
        json={"body": "Investigating OAuth refresh token rotation issue."},
        headers=owner_headers,
    )
    assert res_note.status_code == 201
    note_data = res_note.json()
    assert note_data["sender_type"] == "platform_owner"
    assert note_data["visibility"] == "internal_only"
    assert "token rotation" in note_data["body"]

    # 2. Post tenant reply
    res_reply = client.post(
        f"/api/admin/support-tickets/{ticket.id}/tenant-reply",
        json={"body": "Hello, we have identified the sync issue and applied a fix."},
        headers=owner_headers,
    )
    assert res_reply.status_code == 201
    reply_data = res_reply.json()
    assert reply_data["sender_type"] == "platform_owner"
    assert reply_data["visibility"] == "tenant_visible"
    assert "applied a fix" in reply_data["body"]

    # Verify audit events recorded in database
    events = (
        db_session.query(SupportTicketAuditEvent)
        .filter(SupportTicketAuditEvent.ticket_id == ticket.id)
        .all()
    )
    actions = [e.action for e in events]
    assert "internal_note_added" in actions
    assert "tenant_reply_added" in actions


def test_launch_codex_investigation(
    client: TestClient,
    db_session: Session,
    tmp_path,
):
    """Platform owner can launch Codex investigation, creating a thread and turn, and updating ticket status."""
    tenant, user, _ = _create_user(db_session, "codex-t", role="owner")
    _, _, owner_headers = _create_user(db_session, "codex-boss", role="owner")

    ticket = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Webhook serialization failure in booking confirmation",
        description="Payload failed with KeyError 'slot_id'",
        category="technical",
        status="received",
        error_context={"route": "/api/webhooks/booking", "error_code": "KEY_ERROR_SLOT_ID"},
    )
    db_session.add(ticket)
    db_session.commit()

    # Launch only after the worker acknowledges turn/start.
    worker = MagicMock()
    worker.send_request = AsyncMock(return_value={"turn": {"id": "synthetic-turn"}})
    with (
        patch(
            "backend.routers.turns.ensure_thread_worktree",
            return_value=tmp_path,
        ),
        patch(
            "backend.routers.turns.worker_manager.get_worker_for_thread",
            AsyncMock(return_value=worker),
        ),
    ):
        res = client.post(
            f"/api/admin/support-tickets/{ticket.id}/launch-codex",
            json={},
            headers=owner_headers,
        )
    assert res.status_code == 200
    assert worker.send_request.await_args.args[0] == "turn/start"
    data = res.json()
    assert data["ticket_id"] == ticket.id
    assert "codex_thread_id" in data
    assert data["codex_thread_id"].startswith("th_") or len(data["codex_thread_id"]) > 5
    assert "turn_id" in data
    assert isinstance(data["turn_id"], int)

    # Verify ticket in database
    db_session.refresh(ticket)
    assert ticket.codex_thread_id == data["codex_thread_id"]
    assert ticket.status == "queued_for_codex"

    # Verify audit event
    audit_event = (
        db_session.query(SupportTicketAuditEvent)
        .filter(
            SupportTicketAuditEvent.ticket_id == ticket.id,
            SupportTicketAuditEvent.action == "launched_codex",
        )
        .first()
    )
    assert audit_event is not None
    assert audit_event.event_data["codex_thread_id"] == data["codex_thread_id"]


def test_support_launch_dispatch_failure_is_truthful(
    client: TestClient,
    db_session: Session,
    tmp_path,
):
    """Failure after turn creation cannot queue a ticket or leave an active turn."""
    tenant, user, _ = _create_user(db_session, "dispatch-fail-t", role="owner")
    _, _, owner_headers = _create_user(db_session, "dispatch-fail-owner", role="owner")
    ticket = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Synthetic dispatch failure",
        description="Labelled test ticket; no customer data.",
        category="technical",
        status="received",
    )
    db_session.add(ticket)
    db_session.commit()

    worker = MagicMock()
    worker.send_request = AsyncMock(
        side_effect=RuntimeError("synthetic worker rejected turn/start")
    )
    with (
        patch(
            "backend.routers.turns.ensure_thread_worktree",
            return_value=tmp_path,
        ),
        patch(
            "backend.routers.turns.worker_manager.get_worker_for_thread",
            AsyncMock(return_value=worker),
        ),
    ):
        response = client.post(
            f"/api/admin/support-tickets/{ticket.id}/launch-codex",
            json={},
            headers=owner_headers,
        )

    assert response.status_code == 503
    assert worker.send_request.await_count == 1
    assert worker.send_request.await_args.args[0] == "turn/start"
    db_session.refresh(ticket)
    assert ticket.status == "under_review"
    assert ticket.codex_thread_id is None

    failure_event = (
        db_session.query(SupportTicketAuditEvent)
        .filter(
            SupportTicketAuditEvent.ticket_id == ticket.id,
            SupportTicketAuditEvent.action == "codex_dispatch_failed",
        )
        .one()
    )
    assert failure_event.event_data["reason"] == "worker_dispatch_failed"
    assert "turn_id" not in failure_event.event_data

    with CodexSessionLocal() as codex_db:
        active_turns = (
            codex_db.query(CodexTurn)
            .filter(
                CodexTurn.status == "active",
                CodexTurn.prompt.contains("Synthetic dispatch failure"),
            )
            .all()
        )
    assert active_turns == []
