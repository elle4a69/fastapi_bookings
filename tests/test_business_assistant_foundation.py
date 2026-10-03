"""Focused persistence and isolation tests for the Business Assistant foundation."""

import pytest

from app.models.business_assistant import (
    BusinessAssistantConversation,
    BusinessAssistantMessage,
    SupportTicket,
    SupportTicketEvent,
)
from app.models.conversation import Conversation, Message
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant import BusinessAssistantService


def _tenant_and_user(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"Foundation Tenant {suffix}", subdomain=f"foundation-{suffix}")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login=f"operator-{suffix}", password_hash="test", role="owner")
    db_session.add(user)
    db_session.flush()
    return tenant, user


def test_conversations_are_scoped_to_authenticated_tenant_and_user(db_session):
    tenant_a, user_a = _tenant_and_user(db_session, "a")
    tenant_b, user_b = _tenant_and_user(db_session, "b")
    service_a = BusinessAssistantService(db_session, tenant_a.id, user_a.id)
    service_b = BusinessAssistantService(db_session, tenant_b.id, user_b.id)

    conversation_a = service_a.create_conversation(title="A only", request_key="conversation-request-a")
    conversation_b = service_b.create_conversation(title="B only", request_key="conversation-request-b")

    assert [item.id for item in service_a.list_conversations()] == [conversation_a.id]
    assert [item.id for item in service_b.list_conversations()] == [conversation_b.id]
    assert service_a._repository.get_conversation(conversation_b.id) is None


def test_conversation_creation_is_idempotent_within_its_scope(db_session):
    tenant, user = _tenant_and_user(db_session, "idempotent")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    first = service.create_conversation(title="First", request_key="same-conversation-request")
    second = service.create_conversation(title="First", request_key="same-conversation-request")

    assert first.id == second.id
    assert db_session.query(BusinessAssistantConversation).filter_by(tenant_id=tenant.id, user_id=user.id).count() == 1


def test_messages_use_dedicated_tables_and_reject_cross_scope_writes(db_session):
    tenant_a, user_a = _tenant_and_user(db_session, "message-a")
    tenant_b, user_b = _tenant_and_user(db_session, "message-b")
    service_a = BusinessAssistantService(db_session, tenant_a.id, user_a.id)
    service_b = BusinessAssistantService(db_session, tenant_b.id, user_b.id)
    conversation_a = service_a.create_conversation(request_key="message-conversation-a")

    message = service_a.append_message(conversation_id=conversation_a.id, role="user", content="Need a hand")

    assert message.conversation_id == conversation_a.id
    assert db_session.query(BusinessAssistantMessage).count() == 1
    assert db_session.query(Conversation).count() == 0
    assert db_session.query(Message).count() == 0
    with pytest.raises(LookupError):
        service_b.append_message(conversation_id=conversation_a.id, role="user", content="Unauthorized")


def test_ticket_creation_is_idempotent_and_writes_an_append_only_initial_event(db_session):
    tenant, user = _tenant_and_user(db_session, "ticket")
    service = BusinessAssistantService(db_session, tenant.id, user.id)
    conversation = service.create_conversation(request_key="ticket-conversation")

    first = service.create_ticket(
        category="bug",
        severity="high",
        title="Calendar view error",
        description="A synthetic reproduction summary.",
        request_key="ticket-request-key",
        conversation_id=conversation.id,
    )
    second = service.create_ticket(
        category="bug",
        severity="high",
        title="Calendar view error",
        description="A synthetic reproduction summary.",
        request_key="ticket-request-key",
        conversation_id=conversation.id,
    )

    assert first.id == second.id
    assert first.status == "awaiting_engineering"
    assert db_session.query(SupportTicket).filter_by(tenant_id=tenant.id, user_id=user.id).count() == 1
    events = service._repository.list_ticket_events(first.id)
    assert len(events) == 1
    assert events[0].event_type == "created"
    assert events[0].safe_metadata == {"status": "awaiting_engineering"}
    assert db_session.query(SupportTicketEvent).count() == 1


def test_ticket_cannot_reference_a_conversation_outside_authenticated_scope(db_session):
    tenant_a, user_a = _tenant_and_user(db_session, "ticket-a")
    tenant_b, user_b = _tenant_and_user(db_session, "ticket-b")
    conversation_a = BusinessAssistantService(db_session, tenant_a.id, user_a.id).create_conversation(
        request_key="cross-scope-conversation"
    )
    service_b = BusinessAssistantService(db_session, tenant_b.id, user_b.id)

    with pytest.raises(LookupError):
        service_b.create_ticket(
            category="support",
            severity="normal",
            title="No cross scope",
            description="Synthetic test.",
            conversation_id=conversation_a.id,
        )
