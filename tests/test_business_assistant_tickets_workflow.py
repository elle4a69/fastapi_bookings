"""Comprehensive regression suite for Business Assistant Work Package WP6:
Support-Ticket Workflow & Triage Gates.

Covers:
1. Secret & PII sanitisation and rejection (JWTs, DB URLs, API keys, private keys, emails, phones, CCs).
2. Structured ticket contract expansion (observed_behaviour, affected_product_area, user_impact, acceptance_criteria).
3. Active duplicate ticket detection and append-only duplicate_referenced events.
4. Access & Security stop gate: pending_owner_approval, owner-only approval/rejection, token binding.
5. Closed dispatch gate preservation: tickets remain in awaiting_engineering without worker dispatch.
6. Support and Engineering tool pack execution (create_support_ticket, get_ticket_status, list_support_tickets, request_ticket_approval).
7. Tenant and role security boundaries.

All tests execute against live database models and native services with NO MOCKS.
"""

import pytest
from app.core.security import create_access_token
from app.models.business_assistant import SupportTicket, SupportTicketEvent
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant import (
    BusinessAssistantService,
    BusinessAssistantToolRegistry,
    SUPPORT_ENGINEERING_TOOLS,
)
from app.services.business_assistant.adapters import BusinessAssistantReadAdapters
from app.services.business_assistant.confirmation import generate_confirmation_token


def _create_actor(db_session, suffix: str, role: str = "owner", tenant: Tenant | None = None) -> tuple[Tenant, User]:
    if tenant is None:
        tenant = Tenant(name=f"WP6 Tenant {suffix}", subdomain=f"wp6-{suffix}")
        db_session.add(tenant)
        db_session.flush()
    user = User(tenant_id=tenant.id, login=f"wp6-{role}-{suffix}", password_hash="hash", role=role)
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


# ---------------------------------------------------------------------------
# 1. Secret & Sensitive Data Sanitisation & Rejection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "secret_snippet",
    [
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...",
        "api_key=sk-proj-1234567890abcdef1234",
        "secret: my-super-secret-password-123",
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgN7s5c",
        "postgresql://postgres:secretpassword@localhost:5432/mydb",
        "redis://:p4ssw0rd@10.0.0.1:6379/0",
        "sk_live_1234567890abcdef123456",
        "ghp_1234567890abcdef1234567890abcdef",
        "xoxb-1234567890-abcdefghij",
        "AKIAIOSFODNN7EXAMPLE",
    ],
)
def test_ticket_rejects_raw_secrets(client, db_session, secret_snippet):
    tenant, user = _create_actor(db_session, "secret-test")
    headers = _headers(tenant, user)

    payload = {
        "category": "bug",
        "severity": "high",
        "title": "Database connection issue",
        "description": f"Encountered error connecting to {secret_snippet}",
    }
    response = client.post("/api/admin/business-assistant/tickets", headers=headers, json=payload)
    assert response.status_code == 422
    assert "secret" in response.json()["error"]["message"].lower() or "sanitised" in response.json()["error"]["message"].lower()


@pytest.mark.parametrize(
    "pii_snippet",
    [
        "customer reported from john.doe@example.com",
        "call client at +61 412 345 678 immediately",
        "US phone number 555-123-4567 provided",
        "customer_id: CUST-9988776655",
        "credit card charged: 4111 2222 3333 4444",
        "customer SSN 123-45-6789",
        "Australian TFN 123 456 789",
    ],
)
def test_ticket_rejects_unmasked_customer_pii(client, db_session, pii_snippet):
    tenant, user = _create_actor(db_session, "pii-test")
    headers = _headers(tenant, user)

    # Test rejection in description
    payload_desc = {
        "category": "support",
        "title": "Customer query regarding invoice",
        "description": f"Details: {pii_snippet}",
    }
    resp = client.post("/api/admin/business-assistant/tickets", headers=headers, json=payload_desc)
    assert resp.status_code == 422

    # Test rejection in observed_behaviour
    payload_obs = {
        "category": "support",
        "title": "Customer query regarding invoice",
        "description": "Safe explanation without secrets",
        "observed_behaviour": f"Error logged for {pii_snippet}",
    }
    resp = client.post("/api/admin/business-assistant/tickets", headers=headers, json=payload_obs)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 2. Structured Ticket Contract Expansion
# ---------------------------------------------------------------------------

def test_ticket_creation_with_full_contract(client, db_session):
    tenant, user = _create_actor(db_session, "contract")
    headers = _headers(tenant, user)

    payload = {
        "category": "bug",
        "severity": "critical",
        "title": "Double billing on instant checkout confirmation",
        "description": "Synthetic report: duplicate webhook received from payment gateway.",
        "observed_behaviour": "Two invoice records generated with identical order sequence.",
        "affected_product_area": "checkout",
        "user_impact": "Clients see duplicate charge notifications on mobile app.",
        "acceptance_criteria": "Idempotency key prevents duplicate transaction creation.",
        "request_key": "contract-test-req-001",
    }
    response = client.post("/api/admin/business-assistant/tickets", headers=headers, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["duplicate_ticket"] is False
    ticket = data["ticket"]

    assert ticket["category"] == "bug"
    assert ticket["severity"] == "critical"
    assert ticket["status"] == "awaiting_engineering"
    assert ticket["observed_behaviour"] == "Two invoice records generated with identical order sequence."
    assert ticket["affected_product_area"] == "checkout"
    assert ticket["user_impact"] == "Clients see duplicate charge notifications on mobile app."
    assert ticket["acceptance_criteria"] == "Idempotency key prevents duplicate transaction creation."
    assert ticket["authorisation_state"] == "not_required"
    assert ticket["requires_owner_approval"] is False
    assert ticket["coding_task_id"] is None

    # Verify database persistence
    db_ticket = db_session.query(SupportTicket).filter_by(id=ticket["id"]).first()
    assert db_ticket is not None
    assert db_ticket.observed_behaviour == "Two invoice records generated with identical order sequence."
    assert db_ticket.affected_product_area == "checkout"


# ---------------------------------------------------------------------------
# 3. Active Duplicate Ticket Detection & Append-Only Event Trail
# ---------------------------------------------------------------------------

def test_active_duplicate_detection_and_events(client, db_session):
    tenant, user = _create_actor(db_session, "dedup")
    headers = _headers(tenant, user)

    payload = {
        "category": "bug",
        "severity": "normal",
        "title": "Calendar sync offset by 1 hour",
        "description": "Daylight saving offset discrepancy.",
        "affected_product_area": "calendar",
        "request_key": "dedup-ticket-req-1",
    }
    resp1 = client.post("/api/admin/business-assistant/tickets", headers=headers, json=payload)
    assert resp1.status_code == 201
    ticket_id = resp1.json()["ticket"]["id"]
    assert resp1.json()["duplicate_ticket"] is False

    # Second submission with same title, category, and affected area under a different request_key
    payload2 = dict(payload)
    payload2["request_key"] = "dedup-ticket-req-2"
    resp2 = client.post("/api/admin/business-assistant/tickets", headers=headers, json=payload2)
    assert resp2.status_code == 201
    assert resp2.json()["duplicate_ticket"] is True
    assert resp2.json()["ticket"]["id"] == ticket_id

    # Verify event trail
    events_resp = client.get(f"/api/admin/business-assistant/tickets/{ticket_id}/events", headers=headers)
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) == 2
    assert events[0]["event_type"] == "created"
    assert events[1]["event_type"] == "duplicate_referenced"
    assert "Active duplicate ticket referenced" in events[1]["safe_metadata"]["reason"]


# ---------------------------------------------------------------------------
# 4. Access / Security Stop-Gate & Owner Approval Lifecycle
# ---------------------------------------------------------------------------

def test_access_and_security_stop_gate_and_owner_approval(client, db_session):
    tenant, owner = _create_actor(db_session, "approval-flow", role="owner")
    _t, staff = _create_actor(db_session, "staff-user", role="staff", tenant=tenant)
    owner_headers = _headers(tenant, owner)
    staff_headers = _headers(tenant, staff)

    # 1. Create a security ticket
    sec_payload = {
        "category": "security",
        "severity": "high",
        "title": "Request API credential rotation for webhook delivery",
        "description": "Rotate signing keys after infrastructure upgrade.",
        "affected_product_area": "webhooks",
    }
    create_resp = client.post("/api/admin/business-assistant/tickets", headers=owner_headers, json=sec_payload)
    assert create_resp.status_code == 201
    ticket_data = create_resp.json()
    ticket = ticket_data["ticket"]
    token = ticket_data["confirmation_token"]

    assert ticket["status"] == "pending_owner_approval"
    assert ticket["authorisation_state"] == "pending_approval"
    assert ticket["requires_owner_approval"] is True
    assert token is not None
    ticket_id = ticket["id"]

    # Check events recorded: created + approval_requested
    events = client.get(f"/api/admin/business-assistant/tickets/{ticket_id}/events", headers=owner_headers).json()
    assert len(events) == 2
    assert events[0]["event_type"] == "created"
    assert events[1]["event_type"] == "approval_requested"

    # 2. Staff user cannot approve or reject
    staff_approve_resp = client.post(
        f"/api/admin/business-assistant/tickets/{ticket_id}/approve",
        headers=staff_headers,
        json={"confirmation_token": token},
    )
    assert staff_approve_resp.status_code == 403

    # 3. Owner approves ticket with confirmation token
    owner_approve_resp = client.post(
        f"/api/admin/business-assistant/tickets/{ticket_id}/approve",
        headers=owner_headers,
        json={"confirmation_token": token, "note": "Approved by owner Frank"},
    )
    assert owner_approve_resp.status_code == 200
    approved_body = owner_approve_resp.json()
    assert approved_body["action"] == "approved"
    assert approved_body["ticket"]["status"] == "awaiting_engineering"
    assert approved_body["ticket"]["authorisation_state"] == "approved"

    # 4. Closed Dispatch Gate Check: Ticket status remains awaiting_engineering without worker dispatch
    fetched = client.get(f"/api/admin/business-assistant/tickets/{ticket_id}", headers=owner_headers).json()
    assert fetched["status"] == "awaiting_engineering"
    assert fetched["coding_task_id"] is None

    # Check updated event trail
    events_after = client.get(f"/api/admin/business-assistant/tickets/{ticket_id}/events", headers=owner_headers).json()
    assert len(events_after) == 3
    assert events_after[2]["event_type"] == "owner_approved"
    assert events_after[2]["safe_metadata"]["note"] == "Approved by owner Frank"


def test_access_ticket_owner_rejection(client, db_session):
    tenant, owner = _create_actor(db_session, "reject-flow", role="owner")
    headers = _headers(tenant, owner)

    payload = {
        "category": "access",
        "severity": "normal",
        "title": "Request temporary elevated root token for analytics debugging",
        "description": "Need direct database access for ad-hoc SQL query.",
    }
    create_resp = client.post("/api/admin/business-assistant/tickets", headers=headers, json=payload)
    assert create_resp.status_code == 201
    ticket_id = create_resp.json()["ticket"]["id"]
    assert create_resp.json()["ticket"]["status"] == "pending_owner_approval"

    # Reject
    reject_resp = client.post(
        f"/api/admin/business-assistant/tickets/{ticket_id}/reject",
        headers=headers,
        json={"note": "Rejected: Direct root access is against policy."},
    )
    assert reject_resp.status_code == 200
    rejected_body = reject_resp.json()
    assert rejected_body["action"] == "rejected"
    assert rejected_body["ticket"]["status"] == "rejected"
    assert rejected_body["ticket"]["authorisation_state"] == "rejected"

    # Verify event trail
    events = client.get(f"/api/admin/business-assistant/tickets/{ticket_id}/events", headers=headers).json()
    assert len(events) == 3
    assert events[2]["event_type"] == "owner_rejected"
    assert "Rejected: Direct root access is against policy." in events[2]["safe_metadata"]["note"]


# ---------------------------------------------------------------------------
# 5. Support & Engineering Tool Pack Execution
# ---------------------------------------------------------------------------

def test_support_engineering_tool_pack_execution(db_session):
    tenant, owner = _create_actor(db_session, "tool-pack", role="owner")
    adapters = BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=owner.id)
    service = BusinessAssistantService(db_session, tenant.id, owner.id)
    registry = BusinessAssistantToolRegistry(adapters, service=service, packs=("support_engineering",))

    tool_names = [t["function"]["name"] for t in registry.schemas]
    assert "create_support_ticket" in tool_names
    assert "get_ticket_status" in tool_names
    assert "list_support_tickets" in tool_names
    assert "request_ticket_approval" in tool_names

    # 1. create_support_ticket tool
    created = registry.execute(
        "create_support_ticket",
        {
            "category": "bug",
            "severity": "high",
            "title": "SMS dispatch delayed during peak hours",
            "description": "Provider webhook queue latency increases.",
            "affected_product_area": "sms",
        },
    )
    assert created["status"] == "ok"
    ticket_info = created["ticket"]
    assert ticket_info["title"] == "SMS dispatch delayed during peak hours"
    assert ticket_info["status"] == "awaiting_engineering"
    ticket_id = ticket_info["id"]

    # 2. get_ticket_status tool
    status_res = registry.execute("get_ticket_status", {"ticket_id": ticket_id})
    assert status_res["status"] == "ok"
    assert status_res["ticket"]["ticket_id"] == ticket_id
    assert status_res["ticket"]["status"] == "awaiting_engineering"
    assert "created" in status_res["ticket"]["event_types"]

    # 3. list_support_tickets tool
    list_res = registry.execute("list_support_tickets", {"category": "bug", "limit": 10})
    assert list_res["status"] == "ok"
    assert len(list_res["tickets"]) >= 1
    assert any(t["ticket_id"] == ticket_id for t in list_res["tickets"])

    # 4. Elevated ticket and request_ticket_approval tool
    sec_created = registry.execute(
        "create_support_ticket",
        {
            "category": "access",
            "title": "Enable multi-tenant provider audit logs access",
            "description": "Security audit requirement for staff.",
        },
    )
    assert sec_created["status"] == "ok"
    sec_id = sec_created["ticket"]["id"]
    assert sec_created["ticket"]["status"] == "pending_owner_approval"

    approval_res = registry.execute("request_ticket_approval", {"ticket_id": sec_id, "note": "Audit deadline"})
    assert approval_res["status"] == "ok"
    assert approval_res["ticket_status"] == "pending_owner_approval"
    assert "confirmation_token" in approval_res


# ---------------------------------------------------------------------------
# 6. Negative & Isolation Tests
# ---------------------------------------------------------------------------

def test_ticket_isolation_between_tenants(client, db_session):
    tenant_a, owner_a = _create_actor(db_session, "tenant-a")
    tenant_b, owner_b = _create_actor(db_session, "tenant-b")
    headers_a = _headers(tenant_a, owner_a)
    headers_b = _headers(tenant_b, owner_b)

    create_resp = client.post(
        "/api/admin/business-assistant/tickets",
        headers=headers_a,
        json={"category": "bug", "title": "Tenant A Secret Bug", "description": "Tenant A issue."},
    )
    ticket_id = create_resp.json()["ticket"]["id"]

    # Tenant B cannot read or approve Tenant A ticket
    assert client.get(f"/api/admin/business-assistant/tickets/{ticket_id}", headers=headers_b).status_code == 404
    assert client.get(f"/api/admin/business-assistant/tickets/{ticket_id}/events", headers=headers_b).status_code == 404
    assert client.post(f"/api/admin/business-assistant/tickets/{ticket_id}/approve", headers=headers_b, json={}).status_code == 404
