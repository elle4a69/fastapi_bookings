"""Database-bound idempotency tests without model-provider simulation."""

import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.db.database import Base
from app.models.business_assistant import SupportTicketDeduplicationClaim
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant import BusinessAssistantService


def test_concurrent_conversation_creation_returns_one_persisted_result(tmp_path):
    database_path = tmp_path / "business-assistant-idempotency.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    seed = sessions()
    tenant = Tenant(name="Concurrent Tenant", subdomain="concurrent-tenant")
    seed.add(tenant)
    seed.flush()
    user = User(tenant_id=tenant.id, login="concurrent-owner", password_hash="test", role="owner")
    seed.add(user)
    seed.commit()
    tenant_id, user_id = tenant.id, user.id
    seed.close()

    barrier = threading.Barrier(3)
    results: list[int] = []
    errors: list[Exception] = []

    def create_once() -> None:
        session = sessions()
        try:
            barrier.wait(timeout=5)
            conversation = BusinessAssistantService(session, tenant_id, user_id).create_or_get_conversation(
                title="Concurrent subject",
                request_key="concurrent-conversation-key",
            )
            results.append(conversation.id)
        except Exception as exc:  # The assertion below reports an unexpected real database failure.
            errors.append(exc)
        finally:
            session.close()

    first = threading.Thread(target=create_once)
    second = threading.Thread(target=create_once)
    first.start()
    second.start()
    barrier.wait(timeout=5)
    first.join(timeout=10)
    second.join(timeout=10)

    assert not errors
    assert len(results) == 2
    assert results[0] == results[1]
    verify = sessions()
    try:
        assert BusinessAssistantService(verify, tenant_id, user_id).list_conversations()[0].id == results[0]
        assert len(BusinessAssistantService(verify, tenant_id, user_id).list_conversations()) == 1
    finally:
        verify.close()
        engine.dispose()


def test_ticket_active_claim_can_be_released_for_a_later_resolved_ticket(db_session):
    tenant = Tenant(name="Claim Tenant", subdomain="claim-tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login="claim-owner", password_hash="test", role="owner")
    db_session.add(user)
    db_session.commit()
    service = BusinessAssistantService(db_session, tenant.id, user.id)
    first = service.create_ticket(
        category="bug",
        severity="normal",
        title="Synthetic summary",
        description="Synthetic details with no customer data.",
        request_key="claim-first-request-key",
    )
    claim = db_session.query(SupportTicketDeduplicationClaim).filter_by(ticket_id=first.id).one()
    first.status = "resolved"
    db_session.delete(claim)
    db_session.commit()

    second = service.create_ticket(
        category="bug",
        severity="normal",
        title="Synthetic summary",
        description="Synthetic details with no customer data.",
        request_key="claim-second-request-key",
    )
    assert second.id != first.id
    assert db_session.query(SupportTicketDeduplicationClaim).filter_by(ticket_id=second.id).count() == 1
