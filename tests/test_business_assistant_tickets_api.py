"""Authenticated support-ticket API tests using only native persistence."""

from app.core.security import create_access_token
from app.models.business_assistant import SupportTicket
from app.models.tenant import Tenant
from app.models.user import User


def _owner(db_session, suffix: str, *, tenant: Tenant | None = None) -> tuple[Tenant, User]:
    tenant = tenant or Tenant(name=f"Ticket Tenant {suffix}", subdomain=f"ticket-{suffix}")
    if tenant.id is None:
        db_session.add(tenant)
        db_session.flush()
    user = User(tenant_id=tenant.id, login=f"ticket-owner-{suffix}", password_hash="test", role="owner")
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def _ticket_payload(**overrides) -> dict:
    payload = {
        "category": "bug",
        "severity": "high",
        "title": "Calendar refresh fails after saving",
        "description": "A synthetic reproduction summary with no customer records.",
        "request_key": "ticket-create-request-key",
    }
    payload.update(overrides)
    return payload


def test_ticket_create_list_get_and_public_events_are_scoped_and_persistent(client, db_session):
    tenant, user = _owner(db_session, "lifecycle")
    headers = _headers(tenant, user)

    created = client.post("/api/admin/business-assistant/tickets", headers=headers, json=_ticket_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["duplicate_ticket"] is False
    assert body["ticket"]["status"] == "awaiting_engineering"
    assert "tenant_id" not in body["ticket"]
    ticket_id = body["ticket"]["id"]

    listed = client.get("/api/admin/business-assistant/tickets", headers=headers)
    assert listed.status_code == 200
    assert [ticket["id"] for ticket in listed.json()] == [ticket_id]

    fetched = client.get(f"/api/admin/business-assistant/tickets/{ticket_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Calendar refresh fails after saving"

    events = client.get(f"/api/admin/business-assistant/tickets/{ticket_id}/events", headers=headers)
    assert events.status_code == 200
    assert events.json()[0]["event_type"] == "created"
    assert events.json()[0]["safe_metadata"] == {"status": "awaiting_engineering"}
    assert "actor_user_id" not in events.json()[0]


def test_ticket_rejects_secret_and_direct_customer_identifier_before_persistence(client, db_session):
    tenant, user = _owner(db_session, "safety")
    headers = _headers(tenant, user)

    secret = client.post(
        "/api/admin/business-assistant/tickets",
        headers=headers,
        json=_ticket_payload(description="authorization: Bearer opaque-token-value"),
    )
    assert secret.status_code == 422
    assert "sanitised summary" in secret.json()["error"]["message"].lower()

    identifier = client.post(
        "/api/admin/business-assistant/tickets",
        headers=headers,
        json=_ticket_payload(request_key="ticket-customer-identifier-key", description="Contact person@example.test reported this."),
    )
    assert identifier.status_code == 422

    phone = client.post(
        "/api/admin/business-assistant/tickets",
        headers=headers,
        json=_ticket_payload(request_key="ticket-phone-identifier-key", description="The caller used +61 412 345 678."),
    )
    assert phone.status_code == 422
    assert db_session.query(SupportTicket).filter_by(tenant_id=tenant.id, user_id=user.id).count() == 0


def test_ticket_duplicate_active_content_reuses_the_same_ticket(client, db_session):
    tenant, user = _owner(db_session, "duplicate")
    headers = _headers(tenant, user)
    first = client.post("/api/admin/business-assistant/tickets", headers=headers, json=_ticket_payload())
    second = client.post(
        "/api/admin/business-assistant/tickets",
        headers=headers,
        json=_ticket_payload(request_key="a-different-ticket-request-key"),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["duplicate_ticket"] is True
    assert second.json()["ticket"]["id"] == first.json()["ticket"]["id"]
    assert db_session.query(SupportTicket).filter_by(tenant_id=tenant.id, user_id=user.id).count() == 1
    events = client.get(
        f"/api/admin/business-assistant/tickets/{first.json()['ticket']['id']}/events",
        headers=headers,
    )
    assert len(events.json()) == 2
    assert events.json()[0]["event_type"] == "created"
    assert events.json()[1]["event_type"] == "duplicate_referenced"


def test_ticket_request_key_rejects_a_changed_payload(client, db_session):
    tenant, user = _owner(db_session, "payload-conflict")
    headers = _headers(tenant, user)
    created = client.post("/api/admin/business-assistant/tickets", headers=headers, json=_ticket_payload())
    changed = client.post(
        "/api/admin/business-assistant/tickets",
        headers=headers,
        json=_ticket_payload(description="A changed synthetic reproduction summary."),
    )
    assert created.status_code == 201
    assert changed.status_code == 409


def test_ticket_and_events_are_hidden_from_other_users_and_tenants(client, db_session):
    tenant_a, user_a = _owner(db_session, "scope-a")
    _same_tenant, user_same_tenant = _owner(db_session, "scope-user", tenant=tenant_a)
    tenant_b, user_b = _owner(db_session, "scope-b")
    created = client.post(
        "/api/admin/business-assistant/tickets",
        headers=_headers(tenant_a, user_a),
        json=_ticket_payload(),
    )
    ticket_id = created.json()["ticket"]["id"]

    for headers in (_headers(tenant_a, user_same_tenant), _headers(tenant_b, user_b)):
        assert client.get(f"/api/admin/business-assistant/tickets/{ticket_id}", headers=headers).status_code == 404
        assert client.get(f"/api/admin/business-assistant/tickets/{ticket_id}/events", headers=headers).status_code == 404
        assert client.get("/api/admin/business-assistant/tickets", headers=headers).json() == []


def test_legacy_ticket_with_null_fields_serializes_cleanly_on_list_and_get(client, db_session):
    tenant, user = _owner(db_session, "legacy-ticket")
    headers = _headers(tenant, user)

    legacy_ticket = SupportTicket(
        tenant_id=tenant.id,
        user_id=user.id,
        category="bug",
        severity="normal",
        status="open",
        title="Legacy schema ticket",
        description="Ticket created before expanded fields were populated.",
        deduplication_key="legacy-dedup-key-null-check",
    )
    legacy_ticket.observed_behaviour = None
    legacy_ticket.affected_product_area = None
    legacy_ticket.user_impact = None
    legacy_ticket.acceptance_criteria = None
    legacy_ticket.authorisation_state = None
    legacy_ticket.requires_owner_approval = None
    legacy_ticket.resolution_summary = None
    legacy_ticket.coding_task_id = None
    db_session.add(legacy_ticket)
    db_session.commit()

    listed = client.get("/api/admin/business-assistant/tickets", headers=headers)
    assert listed.status_code == 200
    tickets = listed.json()
    assert len(tickets) == 1
    item = tickets[0]
    assert item["id"] == legacy_ticket.id
    assert item["title"] == "Legacy schema ticket"
    assert item["authorisation_state"] == "not_required"
    assert item["requires_owner_approval"] is False
    assert item["observed_behaviour"] is None
    assert item["affected_product_area"] is None

    fetched = client.get(f"/api/admin/business-assistant/tickets/{legacy_ticket.id}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == legacy_ticket.id
    assert body["authorisation_state"] == "not_required"
    assert body["requires_owner_approval"] is False
