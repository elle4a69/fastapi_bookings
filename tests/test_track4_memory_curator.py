"""Tests for background memory curator following the Mem0 pattern (Track 4)."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.curated_memory import CuratedMemory
from app.services.curation.memory_curator import (
    CuratorDecision,
    curate_conversation,
    extract_qa_candidates,
    is_valuable_qa,
    generate_deterministic_embedding,
    compute_cosine_distance,
)


import pytest_asyncio
from sqlalchemy.pool import StaticPool
from app.core.config import settings

@pytest_asyncio.fixture
async def async_test_db(monkeypatch):
    """Create in-memory SQLite async engine and session for curation tests."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        # Create relevant tables
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        # Seed test tenant and provider
        tenant = Tenant(
            name="Curator Test Clinic",
            subdomain="curator-test",
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

        provider = Provider(
            tenant_id=tenant.id,
            name="Dr. Alex Specialist",
            email="alex@curatortest.com",
        )
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        yield session, tenant.id, provider.id

    await engine.dispose()


def test_curator_decision_schema():
    """Verify CuratorDecision Pydantic schema validation."""
    decision = CuratorDecision(
        action="ADD",
        target_memory_id=None,
        ideal_response="You can cancel up to 24 hours in advance.",
        category="policy",
        rationale="New cancellation policy identified",
    )
    assert decision.action == "ADD"
    assert decision.category == "policy"
    assert decision.target_memory_id is None

    # Invalid action should fail validation
    with pytest.raises(Exception):
        CuratorDecision(
            action="INVALID_ACTION",  # type: ignore
            rationale="Invalid",
        )


def test_extract_qa_candidates():
    """Verify transcript parsing extracts user queries and assistant responses."""
    transcript = [
        {"role": "user", "content": "What are your opening hours?"},
        {"role": "assistant", "content": "We are open Monday to Friday from 9am to 5pm."},
        {"role": "user", "content": "Do you have weekend slots?"},
        {"role": "assistant", "content": "Yes, Saturday morning from 9am to 1pm."},
    ]
    candidates = extract_qa_candidates(transcript)
    assert len(candidates) == 2
    assert candidates[0][0] == "What are your opening hours?"
    assert "9am to 5pm" in candidates[0][1]
    assert candidates[1][0] == "Do you have weekend slots?"


def test_is_valuable_qa():
    """Verify trivial chit-chat and greetings are excluded from curation."""
    assert is_valuable_qa("Hi", "Hello! How can I help you today?") is False
    assert is_valuable_qa("thanks", "You're welcome!") is False
    assert is_valuable_qa("speak to a human please", "Transferring you to an agent.") is False
    assert is_valuable_qa(
        "What is your cancellation policy?",
        "Cancellations require at least 24 hours notice for a full refund.",
    ) is True


def test_deterministic_embedding():
    """Verify deterministic fallback produces a normalized 1536-dim vector."""
    vec1 = generate_deterministic_embedding("What is the booking fee?")
    vec2 = generate_deterministic_embedding("What is the booking fee?")
    vec_diff = generate_deterministic_embedding("Something completely different")

    assert len(vec1) == 1536
    assert vec1 == vec2  # Reproducible
    assert vec1 != vec_diff

    # Cosine distance to self should be ~0.0
    dist_self = compute_cosine_distance(vec1, vec2)
    assert dist_self < 1e-5


@pytest.mark.asyncio
async def test_curate_conversation_add_new_memory(async_test_db):
    """Test curation pipeline ADD action for fresh domain knowledge with PII scrubbing."""
    session, tenant_id, provider_id = async_test_db

    transcript = [
        {
            "role": "user",
            "content": "Hi, my name is Alice Cooper. What is your refund policy if I get sick?",
            "sender_name": "Alice Cooper",
        },
        {
            "role": "assistant",
            "content": "Hi Alice, if you are sick with medical proof, you receive a 100% refund.",
        },
    ]

    decisions = await curate_conversation(
        tenant_id=tenant_id,
        transcript=transcript,
        db=session,
        provider_id=provider_id,
    )

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.action == "ADD"
    assert decision.category == "policy"
    assert decision.target_memory_id is not None

    # Verify memory was inserted in database
    db_mem = await session.get(CuratedMemory, decision.target_memory_id)
    assert db_mem is not None
    assert db_mem.tenant_id == tenant_id
    assert db_mem.category == "policy"
    # Verify PII was scrubbed from both user_query and ideal_response
    assert "Alice Cooper" not in db_mem.user_query
    assert "[NAME]" in db_mem.user_query
    assert "Alice" not in db_mem.ideal_response
    assert "[NAME]" in db_mem.ideal_response


@pytest.mark.asyncio
async def test_curate_conversation_noop_for_identical_memory(async_test_db):
    """Test curation pipeline returns NOOP when knowledge already exists."""
    session, tenant_id, provider_id = async_test_db

    query = "What is your parking situation?"
    answer = "We offer free parking at the rear of the building on 10 High Street."
    vec = generate_deterministic_embedding(query)

    existing = CuratedMemory(
        tenant_id=tenant_id,
        provider_id=provider_id,
        category="location",
        user_query=query,
        ideal_response=answer,
        embedding=vec,
        confidence_score=1.0,
        last_verified_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(existing)
    await session.commit()
    await session.refresh(existing)

    transcript = [
        {"role": "user", "content": query},
        {"role": "assistant", "content": answer},
    ]

    decisions = await curate_conversation(
        tenant_id=tenant_id,
        transcript=transcript,
        db=session,
        provider_id=provider_id,
    )

    assert len(decisions) == 1
    assert decisions[0].action == "NOOP"
    assert decisions[0].target_memory_id == existing.id


@pytest.mark.asyncio
async def test_curate_conversation_update_existing_memory(async_test_db):
    """Test curation pipeline updates existing memory when response details change."""
    session, tenant_id, provider_id = async_test_db

    query = "What is the consultation pricing?"
    initial_answer = "Standard consultation is $100 for 30 minutes."
    vec = generate_deterministic_embedding(query)

    existing = CuratedMemory(
        tenant_id=tenant_id,
        provider_id=provider_id,
        category="pricing",
        user_query=query,
        ideal_response=initial_answer,
        embedding=vec,
        confidence_score=1.0,
        last_verified_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(existing)
    await session.commit()
    await session.refresh(existing)

    updated_answer = "Effective immediately, standard consultation is $120 for 30 minutes."
    transcript = [
        {"role": "user", "content": query},
        {"role": "assistant", "content": updated_answer},
    ]

    decisions = await curate_conversation(
        tenant_id=tenant_id,
        transcript=transcript,
        db=session,
        provider_id=provider_id,
    )

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.action == "UPDATE"
    assert decision.target_memory_id == existing.id

    # Verify database record updated
    await session.refresh(existing)
    assert existing.ideal_response == updated_answer


@pytest.mark.asyncio
async def test_curate_conversation_empty_and_trivial(async_test_db):
    """Test curation pipeline gracefully handles empty and trivial transcripts."""
    session, tenant_id, provider_id = async_test_db

    # Empty
    res1 = await curate_conversation(tenant_id, [], session)
    assert res1[0].action == "NOOP"

    # Only greetings
    res2 = await curate_conversation(
        tenant_id,
        [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there! How can I help you today?"},
        ],
        session,
    )
    assert res2[0].action == "NOOP"
