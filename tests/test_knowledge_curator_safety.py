"""Regression tests for governed, proposal-first knowledge curation."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models import Provider, Tenant, User
from app.models.audit import AuditLog
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.services.curation.knowledge_policy import classify_knowledge_safety
from app.services.curation.memory_curator import (
    CuratorPolicy,
    analyze_knowledge_records,
    curate_conversation,
    ingest_trusted_knowledge,
    review_proposal,
)
from app.services.curation.retrieval import retrieve_durable_knowledge


@pytest_asyncio.fixture
async def curator_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        tenant_a = Tenant(name="Synthetic A", subdomain="synthetic-a")
        tenant_b = Tenant(name="Synthetic B", subdomain="synthetic-b")
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        provider_a = Provider(tenant_id=tenant_a.id, name="Provider A")
        owner_a = User(
            tenant_id=tenant_a.id,
            login="curator-owner",
            password_hash="not-a-real-credential",
            role="owner",
        )
        session.add_all([provider_a, owner_a])
        await session.commit()
        yield session, tenant_a, tenant_b, provider_a, owner_a
    await engine.dispose()


@pytest.mark.parametrize(
    ("question", "answer", "category"),
    [
        ("What does it cost?", "The current fee is $100.", "pricing"),
        ("Can I book tomorrow?", "There is an open slot at 3pm.", "availability"),
        ("Is my booking ready?", "Your appointment is confirmed.", "booking_status"),
        ("Where do I pay?", "Use https://example.invalid/pay.", "payment"),
    ],
)
def test_dynamic_fact_classifier_fails_closed(question, answer, category):
    decision = classify_knowledge_safety(question, answer, category=category)
    assert decision.durable is False
    assert decision.reason_code == "dynamic_fact_requires_live_source"
    assert decision.dynamic_types


def test_durable_policy_guidance_is_allowed():
    decision = classify_knowledge_safety(
        "What is the cancellation policy?",
        "Please contact the business before cancelling so staff can explain the policy.",
        category="policy",
    )
    assert decision.durable is True


@pytest.mark.asyncio
async def test_conversation_curation_is_proposal_only(curator_db):
    session, tenant, _other_tenant, provider, _owner = curator_db
    decisions = await curate_conversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transcript=[
            {"role": "user", "content": "What is your general cancellation policy?"},
            {
                "role": "assistant",
                "content": "Please contact the business before cancelling so staff can explain the policy.",
            },
        ],
        db=session,
    )

    assert [decision.action for decision in decisions] == ["PROPOSE_ADD"]
    assert decisions[0].requires_review is True
    memories = (await session.execute(select(CuratedMemory))).scalars().all()
    proposals = (await session.execute(select(KnowledgeProposal))).scalars().all()
    assert memories == []
    assert len(proposals) == 1
    assert proposals[0].status == "pending"
    assert proposals[0].tenant_id == tenant.id
    assert proposals[0].provider_id == provider.id


@pytest.mark.asyncio
async def test_dynamic_conversation_is_rejected_without_content_retention(curator_db):
    session, tenant, _other_tenant, provider, _owner = curator_db
    decisions = await curate_conversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transcript=[
            {"role": "user", "content": "What appointments are available tomorrow?"},
            {"role": "assistant", "content": "There is an open slot tomorrow at 3pm."},
        ],
        db=session,
    )

    assert decisions[0].action == "REJECT_DYNAMIC"
    proposal = (await session.execute(select(KnowledgeProposal))).scalar_one()
    assert proposal.status == "rejected"
    assert proposal.contains_dynamic_fact is True
    assert proposal.user_query is None
    assert proposal.proposed_response is None
    assert (await session.execute(select(CuratedMemory))).scalars().all() == []

    audit = (await session.execute(select(AuditLog))).scalar_one()
    assert "tomorrow" not in (audit.details or "").lower()
    assert "3pm" not in (audit.details or "").lower()


@pytest.mark.asyncio
async def test_owner_acceptance_creates_reviewed_memory_and_audit(curator_db):
    session, tenant, _other_tenant, provider, owner = curator_db
    decision = (
        await curate_conversation(
            tenant_id=tenant.id,
            provider_id=provider.id,
            transcript=[
                {"role": "user", "content": "What is your communication policy?"},
                {
                    "role": "assistant",
                    "content": "Staff respond respectfully and explain any next step clearly.",
                },
            ],
            db=session,
        )
    )[0]

    proposal, memory = await review_proposal(
        session,
        tenant_id=tenant.id,
        proposal_id=decision.proposal_id,
        actor_user_id=owner.id,
        actor_role="owner",
        decision="accept",
        resolution_code="owner_verified_source",
    )

    assert proposal.status == "accepted"
    assert memory is not None
    assert memory.tenant_id == tenant.id
    assert memory.authority == "owner_verified"
    assert memory.status == "active"
    audit_actions = set((await session.execute(select(AuditLog.action))).scalars().all())
    assert "knowledge_proposal_created" in audit_actions
    assert "knowledge_proposal_accepted" in audit_actions


@pytest.mark.asyncio
async def test_cross_tenant_proposal_review_is_denied(curator_db):
    session, tenant, other_tenant, provider, owner = curator_db
    decision = (
        await curate_conversation(
            tenant_id=tenant.id,
            provider_id=provider.id,
            transcript=[
                {"role": "user", "content": "How should staff communicate?"},
                {"role": "assistant", "content": "Staff should communicate clearly and respectfully."},
            ],
            db=session,
        )
    )[0]

    with pytest.raises((LookupError, PermissionError)):
        await review_proposal(
            session,
            tenant_id=other_tenant.id,
            proposal_id=decision.proposal_id,
            actor_user_id=owner.id,
            actor_role="owner",
            decision="dismiss",
            resolution_code="not_relevant",
        )


@pytest.mark.asyncio
async def test_trusted_ingestion_is_explicit_and_rejects_dynamic_data(curator_db):
    session, tenant, _other_tenant, provider, owner = curator_db
    disabled = CuratorPolicy()
    with pytest.raises(PermissionError):
        await ingest_trusted_knowledge(
            session,
            tenant_id=tenant.id,
            provider_id=provider.id,
            actor_user_id=owner.id,
            actor_role="owner",
            user_query="What is the staff communication policy?",
            ideal_response="Staff communicate clearly and respectfully.",
            category="policy",
            confidence_score=1.0,
            authority="owner_verified",
            policy=disabled,
        )

    enabled = CuratorPolicy(
        mode="trusted_ingestion", allow_trusted_owner_ingestion=True
    )
    with pytest.raises(ValueError, match="dynamic_fact_requires_live_source"):
        await ingest_trusted_knowledge(
            session,
            tenant_id=tenant.id,
            provider_id=provider.id,
            actor_user_id=owner.id,
            actor_role="owner",
            user_query="What is the current price?",
            ideal_response="The current price is $100.",
            category="pricing",
            confidence_score=1.0,
            authority="owner_verified",
            policy=enabled,
        )


@pytest.mark.asyncio
async def test_retrieval_enforces_tenant_scope_status_authority_dates_and_conflict(curator_db):
    session, tenant, other_tenant, provider, owner = curator_db
    now = datetime.now(timezone.utc)
    provider_b = Provider(tenant_id=tenant.id, name="Provider B")
    session.add(provider_b)
    await session.flush()

    def memory(**overrides):
        values = {
            "tenant_id": tenant.id,
            "provider_id": provider.id,
            "category": "policy",
            "user_query": "What is the communication policy?",
            "ideal_response": "Staff communicate clearly and respectfully.",
            "confidence_score": 1.0,
            "authority": "owner_verified",
            "status": "active",
            "conflict_state": "clear",
            "knowledge_kind": "durable_fact",
            "verified_by_user_id": owner.id,
            "effective_from": now - timedelta(days=1),
            "last_verified_at": now,
        }
        values.update(overrides)
        return CuratedMemory(**values)

    allowed = memory()
    session.add_all(
        [
            allowed,
            memory(status="quarantined"),
            memory(conflict_state="needs_review"),
            memory(authority="conversation_candidate"),
            memory(effective_from=now + timedelta(days=1)),
            memory(provider_id=provider_b.id),
            memory(tenant_id=other_tenant.id, provider_id=None),
        ]
    )
    await session.commit()

    results = await retrieve_durable_knowledge(
        session,
        tenant_id=tenant.id,
        provider_id=provider.id,
        query="communication policy",
    )
    assert [item.id for item, _decision in results] == [allowed.id]
    assert results[0][1].decision_code == "selected_active_durable_knowledge"


def test_curator_scan_detects_invalid_stale_duplicate_and_conflict():
    now = datetime.now(timezone.utc)

    def record(record_id, question, answer, **overrides):
        values = {
            "id": record_id,
            "tenant_id": 1,
            "provider_id": None,
            "category": "policy",
            "user_query": question,
            "ideal_response": answer,
            "confidence_score": 1.0,
            "authority": "owner_verified",
            "status": "active",
            "conflict_state": "clear",
            "knowledge_kind": "durable_fact",
            "effective_from": now,
            "last_verified_at": now,
        }
        values.update(overrides)
        return CuratedMemory(**values)

    records = [
        record(1, "What is the communication policy?", "Staff communicate clearly and respectfully."),
        record(2, "What is the communication policy?", "Staff communicate clearly and respectfully."),
        record(3, "What is the communication policy?", "Staff always use a deliberately different response."),
        record(4, "What is the current price?", "The current price is $100.", category="pricing"),
        record(
            5,
            "What is the privacy policy?",
            "Staff explain the privacy policy clearly.",
            last_verified_at=now - timedelta(days=400),
        ),
    ]
    issue_types = {issue.issue_type for issue in analyze_knowledge_records(records)}
    assert {"invalid", "stale", "duplicate", "conflict"}.issubset(issue_types)
