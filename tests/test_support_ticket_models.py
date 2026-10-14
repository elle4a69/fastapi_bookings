"""Tests for Support Ticket database models and persistence invariants."""

import uuid
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.support_ticket import (
    SupportTicket,
    SupportTicketMessage,
    SupportTicketAuditEvent,
)
from app.models.tenant import Tenant
from app.models.user import User


def _create_tenant_and_user(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"Support Tenant {suffix}", subdomain=f"support-{suffix}")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login=f"support-user-{suffix}", password_hash="hash", role="owner")
    db_session.add(user)
    db_session.flush()
    return tenant, user


def test_support_ticket_creation_and_defaults(db_session):
    tenant, user = _create_tenant_and_user(db_session, "defaults")

    ticket = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Payment Gateway Timeout",
        description="Booking checkout fails on Stripe webhook response timeout.",
        error_context={"endpoint": "/api/checkout", "http_code": 504},
        idempotency_key="idemp-key-101",
        codex_thread_id="thread-ccc-404",
    )
    db_session.add(ticket)
    db_session.commit()

    assert ticket.id is not None
    assert len(ticket.id) == 36
    assert ticket.category == "general"
    assert ticket.status == "received"
    assert ticket.triage_priority == "normal"
    assert ticket.created_at is not None
    assert ticket.updated_at is not None
    assert ticket.resolved_at is None
    assert ticket.error_context == {"endpoint": "/api/checkout", "http_code": 504}
    assert ticket.idempotency_key == "idemp-key-101"
    assert ticket.codex_thread_id == "thread-ccc-404"
    assert ticket.tenant.id == tenant.id
    assert ticket.created_by.id == user.id


def test_support_ticket_relationships_and_cascades(db_session):
    tenant, user = _create_tenant_and_user(db_session, "rel")

    ticket = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Bug in Calendar Sync",
        description="Google Calendar sync is throwing 401.",
    )
    db_session.add(ticket)
    db_session.flush()

    msg1 = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=user.id,
        sender_type="tenant_user",
        visibility="tenant_visible",
        body="Sync started failing at 9:00 AM.",
    )
    msg2 = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=None,
        sender_type="system",
        visibility="internal_only",
        body="Internal error log attached.",
    )
    audit1 = SupportTicketAuditEvent(
        ticket_id=ticket.id,
        actor_user_id=user.id,
        action="ticket_created",
        event_data={"initial_priority": "normal"},
    )
    db_session.add_all([msg1, msg2, audit1])
    db_session.commit()

    db_session.refresh(ticket)
    assert len(ticket.messages) == 2
    assert len(ticket.audit_events) == 1
    assert ticket.messages[0].sender_type == "tenant_user"
    assert ticket.messages[1].visibility == "internal_only"
    assert ticket.messages[0].ticket.id == ticket.id
    assert ticket.audit_events[0].action == "ticket_created"

    # Test cascade deletion of messages and audit events
    ticket_id = ticket.id
    db_session.delete(ticket)
    db_session.commit()

    assert db_session.query(SupportTicket).filter_by(id=ticket_id).first() is None
    assert db_session.query(SupportTicketMessage).filter_by(ticket_id=ticket_id).count() == 0
    assert db_session.query(SupportTicketAuditEvent).filter_by(ticket_id=ticket_id).count() == 0


def test_support_ticket_tenant_idempotency_unique_constraint(db_session):
    tenant, user = _create_tenant_and_user(db_session, "idemp")

    ticket1 = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Duplicate Request 1",
        description="First attempt",
        idempotency_key="unique-idemp-123",
    )
    db_session.add(ticket1)
    db_session.commit()

    ticket2 = SupportTicket(
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        title="Duplicate Request 2",
        description="Second attempt with same idempotency key",
        idempotency_key="unique-idemp-123",
    )
    db_session.add(ticket2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
