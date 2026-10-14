"""Comprehensive test suite for Tenant Support Ticket Intake API and Onboarding Integration.

Covers:
1. Unauthenticated ticket intake and retrieval rejection (401).
2. Cross-tenant isolation: Tenant A cannot access or reply to Tenant B's ticket (404/403).
3. Idempotency key deduplication: returning existing ticket without creating duplicates.
4. Internal-only messages are never exposed to tenant intake/retrieval endpoints.
5. Platform owner check enforcement (require_platform_owner rejects non-owners with 403 Forbidden).
6. PII scrubbing enforcement on ticket descriptions and allowlisted error contexts.
"""

import pytest
from fastapi import HTTPException

from app.api.deps import require_platform_owner
from app.core.security import create_access_token
from app.models.support_ticket import SupportTicket, SupportTicketAuditEvent, SupportTicketMessage
from app.models.tenant import Tenant
from app.models.user import User


def _create_actor(db_session, suffix: str, role: str = "owner", *, tenant: Tenant | None = None) -> tuple[Tenant, User]:
    if tenant is None:
        tenant = Tenant(name=f"Intake Tenant {suffix}", subdomain=f"intake-{suffix}")
        db_session.add(tenant)
        db_session.flush()
    user = User(tenant_id=tenant.id, login=f"intake-{role}-{suffix}", password_hash="hash", role=role)
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User, **extra) -> dict[str, str]:
    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }
    headers.update(extra)
    return headers


# ---------------------------------------------------------------------------
# 1. Unauthenticated Intake Rejection
# ---------------------------------------------------------------------------

def test_unauthenticated_intake_rejected(client, db_session):
    """Endpoints require valid authentication tokens."""
    tenant, _ = _create_actor(db_session, "unauth")
    payload = {
        "title": "Onboarding issue",
        "description": "Encountered a problem during initial setup",
        "category": "general",
    }

    # Missing token on create
    res_create = client.post("/api/support/tickets", json=payload, headers={"X-Tenant": tenant.subdomain})
    assert res_create.status_code == 401

    # Missing token on get
    res_get = client.get("/api/support/tickets/non-existent-id", headers={"X-Tenant": tenant.subdomain})
    assert res_get.status_code == 401

    # Missing token on reply
    res_reply = client.post(
        "/api/support/tickets/non-existent-id/reply",
        json={"body": "Hello"},
        headers={"X-Tenant": tenant.subdomain},
    )
    assert res_reply.status_code == 401


# ---------------------------------------------------------------------------
# 2. Cross-Tenant Isolation
# ---------------------------------------------------------------------------

def test_tenant_a_cannot_access_tenant_b_ticket(client, db_session):
    """Tenant A's tickets cannot be accessed or modified by Tenant B."""
    tenant_a, user_a = _create_actor(db_session, "tenant-a", role="owner")
    tenant_b, user_b = _create_actor(db_session, "tenant-b", role="owner")

    headers_a = _headers(tenant_a, user_a)
    headers_b = _headers(tenant_b, user_b)

    create_res = client.post(
        "/api/support/tickets",
        json={
            "title": "Tenant A Secret Problem",
            "description": "Database connection drop on tenant A",
            "category": "general",
        },
        headers=headers_a,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # Tenant B attempts to read Tenant A's ticket
    get_res = client.get(f"/api/support/tickets/{ticket_id}", headers=headers_b)
    assert get_res.status_code == 404
    error_msg = get_res.json().get("detail") or get_res.json().get("error", {}).get("message", "")
    assert "not found" in str(error_msg).lower()

    # Tenant B attempts to post a reply to Tenant A's ticket
    reply_res = client.post(
        f"/api/support/tickets/{ticket_id}/reply",
        json={"body": "Injected message from competitor"},
        headers=headers_b,
    )
    assert reply_res.status_code == 404

    # Verify message was never stored on ticket
    messages_count = db_session.query(SupportTicketMessage).filter_by(ticket_id=ticket_id).count()
    assert messages_count == 0


# ---------------------------------------------------------------------------
# 3. Idempotency Key Deduplication
# ---------------------------------------------------------------------------

def test_idempotency_key_returns_existing_ticket_without_duplicates(client, db_session):
    """Submitting the same idempotency key returns the existing ticket without duplication."""
    tenant, user = _create_actor(db_session, "idemp", role="owner")
    headers = _headers(tenant, user, **{"X-Idempotency-Key": "idemp-req-key-9999"})

    payload = {
        "title": "Payment gateway timeout",
        "description": "Stripe webhook failed to verify signature",
        "category": "bug",
    }

    # First attempt: creates ticket
    res_first = client.post("/api/support/tickets", json=payload, headers=headers)
    assert res_first.status_code == 201
    ticket_id_1 = res_first.json()["id"]
    assert res_first.json()["tenant_status"] == "Received"

    # Second attempt with identical idempotency key: reuses existing ticket
    res_second = client.post("/api/support/tickets", json=payload, headers=headers)
    assert res_second.status_code in (200, 201)
    ticket_id_2 = res_second.json()["id"]

    assert ticket_id_1 == ticket_id_2

    # Verify only 1 ticket and 1 creation audit event were persisted
    tickets = db_session.query(SupportTicket).filter_by(tenant_id=tenant.id, idempotency_key="idemp-req-key-9999").all()
    assert len(tickets) == 1

    audit_events = db_session.query(SupportTicketAuditEvent).filter_by(ticket_id=ticket_id_1, action="created").all()
    assert len(audit_events) == 1


# ---------------------------------------------------------------------------
# 4. Internal-Only Messages Are Never Visible in Tenant Endpoint
# ---------------------------------------------------------------------------

def test_internal_only_messages_never_visible_in_tenant_endpoint(client, db_session):
    """Messages marked internal_only must never be returned in tenant endpoints."""
    tenant, user = _create_actor(db_session, "visibility", role="owner")
    headers = _headers(tenant, user)

    create_res = client.post(
        "/api/support/tickets",
        json={
            "title": "Need help setting business hours",
            "description": "Operating hours do not save on Sunday",
            "category": "support",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # Add a tenant visible reply
    reply_res = client.post(
        f"/api/support/tickets/{ticket_id}/reply",
        json={"body": "I am on the settings page now."},
        headers=headers,
    )
    assert reply_res.status_code == 201

    # Add an internal-only message (e.g. from Platform Owner or Codex engineer)
    internal_msg = SupportTicketMessage(
        ticket_id=ticket_id,
        sender_user_id=user.id,
        sender_type="platform_owner",
        visibility="internal_only",
        body="Internal engineering note: investigated Sunday daylight savings offset in scheduling service.",
    )
    db_session.add(internal_msg)
    db_session.commit()

    # Retrieve ticket from tenant endpoint
    get_res = client.get(f"/api/support/tickets/{ticket_id}", headers=headers)
    assert get_res.status_code == 200
    ticket_data = get_res.json()

    messages = ticket_data.get("messages", [])
    assert len(messages) == 1
    assert messages[0]["body"] == "I am on the settings page now."
    assert messages[0]["sender_type"] == "tenant_user"

    # Confirm internal-only note was strictly filtered out
    bodies = [m["body"] for m in messages]
    assert not any("Internal engineering note" in b for b in bodies)


# ---------------------------------------------------------------------------
# 5. Platform Owner Check Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_platform_owner_dependency_direct():
    """require_platform_owner enforces owner role or superuser privilege."""
    # 1. Non-owner regular staff -> 403 Forbidden
    staff_user = User(id=10, tenant_id=1, login="staff1", role="staff")
    with pytest.raises(HTTPException) as exc_info:
        await require_platform_owner(current_user=staff_user)
    assert exc_info.value.status_code == 403

    # 2. Provider role -> 403 Forbidden
    provider_user = User(id=11, tenant_id=1, login="provider1", role="provider")
    with pytest.raises(HTTPException) as exc_info:
        await require_platform_owner(current_user=provider_user)
    assert exc_info.value.status_code == 403

    # 3. Owner role -> allowed
    owner_user = User(id=12, tenant_id=1, login="owner1", role="owner")
    resolved_owner = await require_platform_owner(current_user=owner_user)
    assert resolved_owner == owner_user

    # 4. Superuser user -> allowed
    superuser = User(id=13, tenant_id=1, login="super1", role="manager")
    setattr(superuser, "is_superuser", True)
    resolved_super = await require_platform_owner(current_user=superuser)
    assert resolved_super == superuser


def test_platform_owner_endpoint_protection(client, db_session):
    """Platform owner internal note endpoint rejects non-owners with 403."""
    tenant, owner_user = _create_actor(db_session, "owner-act", role="owner")
    _, staff_user = _create_actor(db_session, "staff-act", role="staff", tenant=tenant)

    owner_headers = _headers(tenant, owner_user)
    staff_headers = _headers(tenant, staff_user)

    # Owner creates ticket
    create_res = client.post(
        "/api/support/tickets",
        json={"title": "Test Ticket", "description": "Needs review"},
        headers=owner_headers,
    )
    ticket_id = create_res.json()["id"]

    # Staff user tries to add an internal note -> 403 Forbidden
    staff_note_res = client.post(
        f"/api/support/tickets/{ticket_id}/internal-note",
        json={"body": "Staff note attempt"},
        headers=staff_headers,
    )
    assert staff_note_res.status_code == 403

    # Owner user adds internal note -> 201 Created
    owner_note_res = client.post(
        f"/api/support/tickets/{ticket_id}/internal-note",
        json={"body": "Platform owner confirmed root cause."},
        headers=owner_headers,
    )
    assert owner_note_res.status_code == 201
    assert owner_note_res.json()["sender_type"] == "platform_owner"


# ---------------------------------------------------------------------------
# 6. PII Scrubbing in Ticket Intake
# ---------------------------------------------------------------------------

def test_pii_scrubbing_in_ticket_intake(client, db_session):
    """Customer email, phone, and card numbers are scrubbed from error context and description."""
    tenant, user = _create_actor(db_session, "pii-scrub", role="owner")
    headers = _headers(tenant, user)

    payload = {
        "title": "Booking failure for john.doe@example.com",
        "description": "Customer reported phone 0412 345 678 and card 4111 2222 3333 4444 failed.",
        "category": "booking",
        "error_context": {
            "route": "/admin/calendar",
            "action_attempted": "submit_booking",
            "error_code": "CARD_DECLINED",
            "error_message": "Declined for john.doe@example.com on 0412 345 678",
            "client_timestamp": "2026-10-14T08:00:00Z",
        },
    }

    res = client.post("/api/support/tickets", json=payload, headers=headers)
    assert res.status_code == 201
    ticket_id = res.json()["id"]

    ticket = db_session.query(SupportTicket).filter_by(id=ticket_id).first()
    assert ticket is not None

    # Verify PII was redacted from stored fields
    assert "john.doe@example.com" not in ticket.title
    assert "4111 2222 3333 4444" not in ticket.description
    assert "0412 345 678" not in ticket.description

    assert ticket.error_context is not None
    assert "john.doe@example.com" not in ticket.error_context.get("error_message", "")
    assert "0412 345 678" not in ticket.error_context.get("error_message", "")
