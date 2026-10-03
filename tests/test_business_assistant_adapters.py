"""Native read-adapter tests using tenant-scoped FastAPI Bookings records."""

import pytest

from app.models.location import Location
from app.models.provider import Provider
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant import BusinessAssistantService
from app.services.business_assistant.adapters import BusinessAssistantReadAdapters


def _owner(db_session, suffix: str, *, enabled_modules: list[str] | None = None) -> tuple[Tenant, User]:
    tenant = Tenant(
        name=f"Adapter Tenant {suffix}",
        subdomain=f"adapter-{suffix}",
        enabled_modules=enabled_modules,
    )
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login=f"adapter-owner-{suffix}", password_hash="test", role="owner")
    db_session.add(user)
    db_session.flush()
    return tenant, user


def test_product_help_read_uses_live_allowlisted_records_in_the_current_tenant(db_session):
    tenant_a, user_a = _owner(db_session, "a", enabled_modules=["calendar", "website"])
    tenant_b, user_b = _owner(db_session, "b", enabled_modules=["finance_invoicing"])
    db_session.add_all(
        [
            Service(tenant_id=tenant_a.id, name="Consultation", duration=30, active=True),
            Provider(tenant_id=tenant_a.id, name="Provider A", active=True),
            Location(tenant_id=tenant_a.id, name="Location A", active=True),
            Service(tenant_id=tenant_b.id, name="Other tenant", duration=45, active=True),
            Provider(tenant_id=tenant_b.id, name="Provider B", active=True),
            Location(tenant_id=tenant_b.id, name="Location B", active=True),
        ]
    )
    db_session.commit()

    result = BusinessAssistantReadAdapters(
        db_session, tenant_id=tenant_a.id, user_id=user_a.id
    ).read_product_help()

    assert result.availability == "available"
    assert result.enabled_modules == ("dashboard", "calendar", "bookings", "website")
    assert (result.active_services, result.active_providers, result.active_locations) == (1, 1, 1)
    assert result.tool_result() == {
        "availability": "available",
        "enabled_modules": ["dashboard", "calendar", "bookings", "website"],
        "active_services": 1,
        "active_providers": 1,
        "active_locations": 1,
    }

    other_tenant = BusinessAssistantReadAdapters(
        db_session, tenant_id=tenant_b.id, user_id=user_b.id
    ).read_product_help()
    assert (other_tenant.active_services, other_tenant.active_providers, other_tenant.active_locations) == (1, 1, 1)
    assert "finance_invoicing" in other_tenant.enabled_modules
    assert "finance_invoicing" not in result.enabled_modules


def test_onboarding_read_uses_personal_progress_and_current_product_context(db_session):
    tenant, user = _owner(db_session, "onboarding", enabled_modules=["calendar"])
    db_session.add(Service(tenant_id=tenant.id, name="Setup service", duration=20, active=True))
    db_session.commit()
    service = BusinessAssistantService(db_session, tenant.id, user.id)
    service.complete_onboarding_step(step="review_product_context")

    result = BusinessAssistantReadAdapters(
        db_session, tenant_id=tenant.id, user_id=user.id
    ).read_onboarding()

    assert result.status == "in_progress"
    assert result.completed_steps == ("review_product_context",)
    assert result.product_help.availability == "available"
    assert result.product_help.active_services == 1
    assert "calendar" in result.tool_result()["product_help"]["enabled_modules"]


def test_ticket_handoff_status_is_scoped_and_excludes_ticket_body_and_worker_data(db_session):
    tenant_a, user_a = _owner(db_session, "ticket-a")
    tenant_b, user_b = _owner(db_session, "ticket-b")
    ticket = BusinessAssistantService(db_session, tenant_a.id, user_a.id).create_ticket(
        category="bug",
        severity="high",
        title="Calendar issue",
        description="Synthetic reproduction summary.",
        request_key="adapter-ticket-request-key",
    )

    adapter = BusinessAssistantReadAdapters(db_session, tenant_id=tenant_a.id, user_id=user_a.id)
    result = adapter.get_ticket_handoff_status(ticket.id)

    assert result.ticket_id == ticket.id
    assert result.status == "awaiting_engineering"
    assert result.event_types == ("created",)
    assert set(result.tool_result()) == {
        "ticket_id", "category", "severity", "status", "created_at", "updated_at", "event_types"
    }
    assert "description" not in result.tool_result()
    assert "title" not in result.tool_result()
    assert "worker" not in result.tool_result()

    with pytest.raises(LookupError):
        BusinessAssistantReadAdapters(
            db_session, tenant_id=tenant_b.id, user_id=user_b.id
        ).get_ticket_handoff_status(ticket.id)


def test_ticket_handoff_status_list_is_bounded_and_scoped(db_session):
    tenant, user = _owner(db_session, "list")
    service = BusinessAssistantService(db_session, tenant.id, user.id)
    for index in range(2):
        service.create_ticket(
            category="support",
            severity="normal",
            title=f"Distinct issue {index}",
            description=f"Synthetic detail {index}.",
            request_key=f"adapter-list-request-{index}",
        )

    adapter = BusinessAssistantReadAdapters(db_session, tenant_id=tenant.id, user_id=user.id)
    assert len(adapter.list_ticket_handoff_statuses(limit=1)) == 1
    assert len(adapter.list_ticket_handoff_statuses(limit=2)) == 2
    with pytest.raises(ValueError):
        adapter.list_ticket_handoff_statuses(limit=101)
