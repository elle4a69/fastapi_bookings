"""Adversarial and dirty-transcript QA audit test suite for Track 4 (Memory Curator).

Verifies:
1. Aggressive PII leaks: complex mixed strings with multiple phone formats,
   fake credit cards with Luhn validity, disguised street addresses with periods/PO boxes.
2. Memory conflict resolution: contradictory pricing ($100 vs $120) triggers UPDATE,
   service obsolescence/discontinuation triggers DELETE, without corrupting database state.
3. Multi-tenant isolation: ensures tenant A cannot mutate or delete tenant B's memories.
4. Zero leakage: ensures raw PII is never persisted to CuratedMemory records in the database.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.database import Base
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.curated_memory import CuratedMemory
from app.services.curation.pii_scrubber import PIIScrubber, scrub_pii
from app.services.curation.memory_curator import (
    CuratorDecision,
    curate_conversation,
    evaluate_curator_decision,
    generate_deterministic_embedding,
)


# -------------------------------------------------------------------------
# Test Fixtures
# -------------------------------------------------------------------------

@pytest_asyncio.fixture
async def adversarial_test_db(monkeypatch):
    """Set up isolated async in-memory SQLite database with multi-tenant seed data."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        # Tenant 1: Alpha Clinic
        t1 = Tenant(name="Alpha Clinic", subdomain="alpha-clinic")
        session.add(t1)
        # Tenant 2: Beta Health
        t2 = Tenant(name="Beta Health", subdomain="beta-health")
        session.add(t2)
        await session.commit()
        await session.refresh(t1)
        await session.refresh(t2)

        p1 = Provider(tenant_id=t1.id, name="Dr. Alice Smith", email="alice@alphaclinic.com")
        p2 = Provider(tenant_id=t2.id, name="Dr. Bob Jones", email="bob@betahealth.com")
        session.add_all([p1, p2])
        await session.commit()
        await session.refresh(p1)
        await session.refresh(p2)

        yield session, t1.id, t2.id, p1.id, p2.id

    await engine.dispose()


# -------------------------------------------------------------------------
# 1. Aggressive PII Leakage Tests
# -------------------------------------------------------------------------

class TestAggressivePIIScrubbing:
    """Audit PII scrubber resilience against adversarial and disguised PII patterns."""

    @pytest.mark.parametrize(
        "phone_sample,sensitive_part",
        [
            ("Call my mobile on 0412.345.678 right away.", "0412.345.678"),
            ("You can reach me at (0412) 345 678 anytime.", "345 678"),
            ("Direct desk line: (02) 9876-5432.", "9876-5432"),
            ("Melbourne office line: 03.9123.4567.", "9123.4567"),
            ("International direct: +1 (555) 234-5678 extension 4.", "+1 (555) 234-5678"),
            ("UK desk: +44 20 7946 0958 thanks.", "+44 20 7946 0958"),
            ("Free call: 1800-123-456 support.", "1800-123-456"),
            ("National rate: 13 11 14 lifeline.", "13 11 14"),
            ("Toll-free dot: 1300.555.123 for billing.", "1300.555.123"),
            ("Intl Australia: +61.412.345.678 mobile.", "+61.412.345.678"),
        ],
    )
    def test_aggressive_phone_formats_scrubbed(self, phone_sample: str, sensitive_part: str):
        scrubbed = scrub_pii(phone_sample)
        assert sensitive_part not in scrubbed, f"Leaked phone in: '{scrubbed}'"
        assert "[PHONE]" in scrubbed

    @pytest.mark.parametrize(
        "card_sample,card_digits",
        [
            # Luhn-valid Visa test numbers
            ("Please charge Visa 4532 0151 1283 0366 exp 11/28", "4532 0151 1283 0366"),
            ("Card number: 4532-0151-1283-0366 cvc 123", "4532-0151-1283-0366"),
            ("Contiguous Visa: 4532015112830366", "4532015112830366"),
            ("Dot-separated card: 4532.0151.1283.0366", "4532.0151.1283.0366"),
            # Luhn-valid Mastercard test numbers
            ("Mastercard: 5425-2334-3010-9821 now", "5425-2334-3010-9821"),
            # Luhn-valid Amex test numbers
            ("Amex formatted: 3782-822463-10005", "3782-822463-10005"),
            ("Amex space: 3782 822463 10005", "3782 822463 10005"),
            # Luhn-valid 13-digit card
            ("Old Visa: 4012888888881", "4012888888881"),
        ],
    )
    def test_luhn_valid_credit_cards_scrubbed(self, card_sample: str, card_digits: str):
        scrubbed = scrub_pii(card_sample)
        for part in card_digits.replace("-", " ").replace(".", " ").split():
            assert part not in scrubbed, f"Card chunk '{part}' leaked in: '{scrubbed}'"
        assert "[CREDIT_CARD]" in scrubbed

    @pytest.mark.parametrize(
        "address_sample,leaked_keywords",
        [
            ("Drop off at 15 King St., Sydney NSW 2000 please.", ["15 King", "Sydney NSW 2000"]),
            ("Send documents to P.O. Box 789, Melbourne VIC 3001.", ["P.O. Box 789", "Melbourne VIC 3001"]),
            ("Billing: PO Box 123, Sydney NSW 2000.", ["PO Box 123", "Sydney NSW 2000"]),
            ("Office at Suite 12B, 100-102 George Street, The Rocks NSW 2000.", ["George Street", "The Rocks NSW 2000"]),
            ("Residence: Unit 4/15 High St, Melbourne VIC 3000.", ["Unit 4/15 High St", "Melbourne VIC 3000"]),
            ("Clinic is at Level 2, 742 Evergreen Terrace, Springfield.", ["Level 2", "742 Evergreen Terrace"]),
            ("Apartment: Apt 3B, 88 Queen Street, Brisbane QLD 4000.", ["Queen Street", "Brisbane QLD 4000"]),
        ],
    )
    def test_disguised_street_addresses_and_pobox_scrubbed(self, address_sample: str, leaked_keywords: list[str]):
        scrubbed = scrub_pii(address_sample)
        for kw in leaked_keywords:
            assert kw not in scrubbed, f"Address keyword '{kw}' leaked in: '{scrubbed}'"
        assert "[ADDRESS]" in scrubbed

    def test_mixed_adversarial_transcript_scrubbed(self):
        """Mixed adversarial string containing names, phones, addresses, and credit cards."""
        dirty = (
            "Hi, this is Dr. Bruce Wayne calling from Suite 5, 22-24 Victoria Rd., Rozelle NSW 2039. "
            "Please update my file. Phone is (0412) 345-678 or office +61.2.9876.5432. "
            "My billing email is bwayne@wayne-enterprises.co.uk and card is 4532-0151-1283-0366. "
            "Postal mail to P.O. Box 450, Sydney NSW 2001. Best regards, Bruce Wayne"
        )
        scrubbed = scrub_pii(dirty, customer_names=["Bruce Wayne"])

        # Check all sensitive markers are present
        assert "[NAME]" in scrubbed
        assert "[ADDRESS]" in scrubbed
        assert "[PHONE]" in scrubbed
        assert "[EMAIL]" in scrubbed
        assert "[CREDIT_CARD]" in scrubbed

        # Ensure complete zero leakage of raw identifiers
        leakage_checks = [
            "Bruce Wayne", "Victoria Rd", "Rozelle", "NSW 2039",
            "0412", "345-678", "9876.5432", "bwayne@wayne-enterprises.co.uk",
            "4532-0151-1283-0366", "P.O. Box 450", "Sydney NSW 2001"
        ]
        for term in leakage_checks:
            assert term not in scrubbed, f"Critical PII leak detected: '{term}' in '{scrubbed}'"


# -------------------------------------------------------------------------
# 2. Memory Conflict Resolution Tests (Contradictory Pricing & DELETE)
# -------------------------------------------------------------------------

class TestMemoryConflictResolution:
    """Verify semantic conflict resolution: UPDATE on contradictory pricing, DELETE on obsolescence."""

    @pytest.mark.asyncio
    async def test_contradictory_pricing_triggers_update(self, adversarial_test_db):
        """Contradictory price quote ($100 vs $120) must trigger UPDATE, not NOOP."""
        session, t1_id, _, p1_id, _ = adversarial_test_db

        query = "How much does a 60-minute deep tissue massage cost?"
        old_resp = "Our 60-minute deep tissue massage is $100."
        vec = generate_deterministic_embedding(query)

        # Pre-seed initial memory with old $100 price
        initial_mem = CuratedMemory(
            tenant_id=t1_id,
            provider_id=p1_id,
            category="pricing",
            user_query=query,
            ideal_response=old_resp,
            embedding=vec,
            confidence_score=1.0,
            last_verified_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(initial_mem)
        await session.commit()
        await session.refresh(initial_mem)
        initial_id = initial_mem.id

        # New conversation with updated $120 price
        new_resp = "Our 60-minute deep tissue massage is $120."
        transcript = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": new_resp},
        ]

        decisions = await curate_conversation(
            tenant_id=t1_id,
            transcript=transcript,
            db=session,
            provider_id=p1_id,
        )

        assert len(decisions) == 1
        decision = decisions[0]
        assert decision.action == "UPDATE", f"Expected UPDATE but got {decision.action} ({decision.rationale})"
        assert decision.target_memory_id == initial_id
        assert "$120" in decision.ideal_response

        # Check database: record was updated in place, no duplicate record created
        await session.refresh(initial_mem)
        assert initial_mem.ideal_response == new_resp
        assert "$120" in initial_mem.ideal_response

        # Count total memories for tenant 1
        stmt = select(CuratedMemory).where(CuratedMemory.tenant_id == t1_id)
        res = await session.execute(stmt)
        total_mems = res.scalars().all()
        assert len(total_mems) == 1, "Duplicate memory row created instead of updating in-place!"

    @pytest.mark.asyncio
    async def test_discontinued_service_triggers_delete(self, adversarial_test_db):
        """Obsolescence/cancellation statement must trigger DELETE and remove memory from DB."""
        session, t1_id, _, p1_id, _ = adversarial_test_db

        query = "Do you offer acupuncture treatments?"
        old_resp = "Yes, acupuncture treatments are available on Tuesdays and Thursdays."
        vec = generate_deterministic_embedding(query)

        # Pre-seed active memory
        existing_mem = CuratedMemory(
            tenant_id=t1_id,
            provider_id=p1_id,
            category="service_info",
            user_query=query,
            ideal_response=old_resp,
            embedding=vec,
            confidence_score=1.0,
            last_verified_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(existing_mem)
        await session.commit()
        await session.refresh(existing_mem)
        target_id = existing_mem.id

        # New conversation indicates service is discontinued
        discontinued_resp = "We no longer offer acupuncture treatments at our clinic."
        transcript = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": discontinued_resp},
        ]

        decisions = await curate_conversation(
            tenant_id=t1_id,
            transcript=transcript,
            db=session,
            provider_id=p1_id,
        )

        assert len(decisions) == 1
        decision = decisions[0]
        assert decision.action == "DELETE", f"Expected DELETE but got {decision.action} ({decision.rationale})"
        assert decision.target_memory_id == target_id

        # Check database: row was deleted
        db_mem = await session.get(CuratedMemory, target_id)
        assert db_mem is None, "CuratedMemory record was not deleted from database!"

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_in_curation(self, adversarial_test_db):
        """Tenant 2 must NOT be able to find, update, or delete Tenant 1's memories."""
        session, t1_id, t2_id, p1_id, p2_id = adversarial_test_db

        query = "What is the fee for an initial consultation?"
        t1_resp = "Tenant 1 consultation fee is $150."
        vec = generate_deterministic_embedding(query)

        t1_mem = CuratedMemory(
            tenant_id=t1_id,
            provider_id=p1_id,
            category="pricing",
            user_query=query,
            ideal_response=t1_resp,
            embedding=vec,
            confidence_score=1.0,
            last_verified_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(t1_mem)
        await session.commit()
        await session.refresh(t1_mem)
        t1_mem_id = t1_mem.id

        # Tenant 2 has a conversation on identical topic
        t2_transcript = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": "Tenant 2 consultation fee is $200."},
        ]

        # Running curation for Tenant 2 should ADD a new record for Tenant 2, NOT update Tenant 1
        decisions_t2 = await curate_conversation(
            tenant_id=t2_id,
            transcript=t2_transcript,
            db=session,
            provider_id=p2_id,
        )

        assert len(decisions_t2) == 1
        assert decisions_t2[0].action == "ADD"
        assert decisions_t2[0].target_memory_id != t1_mem_id

        # Verify Tenant 1 memory remained completely uncorrupted
        refreshed_t1 = await session.get(CuratedMemory, t1_mem_id)
        assert refreshed_t1 is not None
        assert refreshed_t1.ideal_response == t1_resp
        assert refreshed_t1.tenant_id == t1_id


# -------------------------------------------------------------------------
# 3. Zero Leakage End-to-End Database Ingestion Test
# -------------------------------------------------------------------------

class TestZeroLeakageCuratedMemory:
    """Verify that end-to-end conversation curation persists ZERO raw PII to the database."""

    @pytest.mark.asyncio
    async def test_zero_leakage_end_to_end_ingestion(self, adversarial_test_db):
        session, t1_id, _, p1_id, _ = adversarial_test_db

        # Heavy PII transcript
        raw_customer_name = "Jonathan Higgins"
        raw_phone = "0423 888 999"
        raw_email = "higgins.j@estate-security.com.au"
        raw_card = "4532 0151 1283 0366"
        raw_address = "Level 3, 50 Carrington Street, Sydney NSW 2000"

        transcript = [
            {
                "role": "user",
                "content": (
                    f"Hello, my name is {raw_customer_name}. I reside at {raw_address}. "
                    f"My contact number is {raw_phone} and email {raw_email}. "
                    f"Can you explain your late cancellation policy if I already paid with card {raw_card}?"
                ),
                "sender_name": raw_customer_name,
            },
            {
                "role": "assistant",
                "content": (
                    f"Hello {raw_customer_name}, cancellations made less than 24 hours in advance "
                    f"incur a 50% fee charged to your card. Confirmation will be sent to {raw_email}."
                ),
            },
        ]

        decisions = await curate_conversation(
            tenant_id=t1_id,
            transcript=transcript,
            db=session,
            provider_id=p1_id,
        )

        assert len(decisions) == 1
        assert decisions[0].action == "ADD"
        saved_id = decisions[0].target_memory_id
        assert saved_id is not None

        # Fetch directly from database and audit raw columns
        persisted_memory = await session.get(CuratedMemory, saved_id)
        assert persisted_memory is not None

        stored_query = persisted_memory.user_query
        stored_response = persisted_memory.ideal_response

        # Check for zero leakage of raw sensitive data
        forbidden_pii = [
            raw_customer_name,
            "0423",
            "888 999",
            raw_email,
            "4532",
            "1283 0366",
            "50 Carrington",
            "Sydney NSW 2000",
        ]

        for pii in forbidden_pii:
            assert pii not in stored_query, f"LEAK DETECTED in stored user_query: '{pii}' found in '{stored_query}'"
            assert pii not in stored_response, f"LEAK DETECTED in stored ideal_response: '{pii}' found in '{stored_response}'"

        # Check expected redactions
        assert "[NAME]" in stored_query
        assert "[PHONE]" in stored_query
        assert "[EMAIL]" in stored_query
        assert "[ADDRESS]" in stored_query
        assert "[CREDIT_CARD]" in stored_query
        assert "[NAME]" in stored_response
        assert "[EMAIL]" in stored_response
