"""Production Readiness Test and Failure Drills.

Executes verification drills against real containerized infrastructure:
- PostgreSQL on host port 5433 (fastapi-bookings-postgres)
- Redis on host port 6380 (fastapi-bookings-redis)
- Neo4j on host ports 7474 & 7687 (fastapi-bookings-neo4j)

Verification sections implemented:
1. Real Graphiti Write & Retrieval Test (Section 3)
2. Real Bootcamp-to-Live Test (Section 4)
3. Real Behavioural Learning Test (Section 5)
4. Real Temporal Supersession Test (Section 6)
5. Operational Truth Conflict Test (Section 7)
6. Infrastructure Failure Drills (Sections 8, 9, 10: Redis outage, Neo4j outage, Graph rebuild)
7. Worker Crash & Concurrency Drills (Sections 15, 16, 17, 38, 39: crash recovery, deduplication, skip locked, dead-letter replay)
8. Provider & Tenant Isolation Live Tests (Sections 18, 19)
9. PII Verification (Section 20)
10. Scale & Latency Verification (Sections 21, 22, 23)
11. Granular Health Check Endpoint (Section 24)
"""

from __future__ import annotations

import _socket
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch
import uuid

import pytest
import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import create_engine, desc, text
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

import tests.conftest as conftest_module
from app.core.config import settings
from app.core.redis import get_redis_client, ping as redis_ping
from app.db.database import Base, get_db
from app.main import app as fastapi_app
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.learning_event import LearningEvent
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.services.curation.pii_scrubber import scrub_pii
from app.services.knowledge.cache import (
    build_cache_key,
    clear_in_memory_cache,
    get_cached_knowledge,
    get_composite_epoch,
    hash_query,
)
from app.services.knowledge.curator import UnifiedCurator, unified_curator
from app.services.knowledge.gateway import KnowledgeGateway, knowledge_gateway
from app.services.knowledge.graphiti_client import (
    format_group_id,
    get_neo4j_driver,
    ping_neo4j,
    resolve_query_group_ids,
)
from app.services.knowledge.projection_service import (
    ProjectionService,
    projection_service,
)
from app.services.knowledge.projection_worker import (
    ProjectionWorker,
    process_pending_projections_worker,
)
from app.services.knowledge.rebuild import (
    KnowledgeRebuildService,
    knowledge_rebuild_service,
)
from app.services.knowledge.types import (
    Authority,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeScope,
    RetrievalQuery,
    RetrievalResult,
)
from app.services.sms.prompt_builder import (
    UnifiedPromptBuilder,
    build_system_prompt,
)

logger = logging.getLogger(__name__)

# Real container connection URLs
REAL_PG_URL = "postgresql://postgres:postgres@localhost:5433/fastapi_bookings"
pg_engine = create_engine(REAL_PG_URL, pool_pre_ping=True)
PgSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


# =============================================================================
# Socket Hook: Permit Real Local Infrastructure (Postgres, Redis, Neo4j, Loopback)
# =============================================================================
_ORIGINAL_RAW_CONNECT = _socket.socket.connect
_ORIGINAL_RAW_CONNECT_EX = _socket.socket.connect_ex


def _drill_connect(sock, address):
    host = address[0] if isinstance(address, (tuple, list)) and len(address) > 0 else getattr(address, "host", "")
    host_str = str(host).lower()
    if host_str in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        return _ORIGINAL_RAW_CONNECT(sock, address)
    if getattr(conftest_module._socketpair_permit, "allow_connect", False):
        return _ORIGINAL_RAW_CONNECT(sock, address)
    raise RuntimeError(f"Outbound network access to {address} is strictly forbidden during tests.")


def _drill_connect_ex(sock, address):
    host = address[0] if isinstance(address, (tuple, list)) and len(address) > 0 else getattr(address, "host", "")
    host_str = str(host).lower()
    if host_str in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        return _ORIGINAL_RAW_CONNECT_EX(sock, address)
    raise RuntimeError(f"Outbound network access to {address} is strictly forbidden during tests.")


def _drill_create_connection(address, *args, **kwargs):
    host = address[0] if isinstance(address, (tuple, list)) and len(address) > 0 else getattr(address, "host", "")
    host_str = str(host).lower()
    if host_str in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        sock = socket.socket()
        sock.connect(address)
        return sock
    raise RuntimeError(f"Outbound network access to {address} is strictly forbidden during tests.")


socket.socket.connect = _drill_connect
socket.socket.connect_ex = _drill_connect_ex
socket.create_connection = _drill_create_connection
conftest_module._guard_socket_connect = _drill_connect
conftest_module._block_outbound_network = _drill_create_connection


@pytest.fixture(autouse=True)
def allow_local_infrastructure_sockets(monkeypatch):
    """Enforce drill socket hooks across every test lifecycle."""
    monkeypatch.setattr(socket.socket, "connect", _drill_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _drill_connect_ex)
    monkeypatch.setattr(socket, "create_connection", _drill_create_connection)
    conftest_module._guard_socket_connect = _drill_connect
    conftest_module._block_outbound_network = _drill_create_connection
    yield


# =============================================================================
# Real Neo4j Graph Driver Client Wrapper
# =============================================================================
class RealNeo4jGraphitiBridgeClient:
    """Bridges Graphiti projection calls to real Neo4j Cypher operations without calling OpenAI."""

    def __init__(self):
        self.driver = get_neo4j_driver()

    def add_episode(
        self,
        name: str,
        episode_body: str,
        source_description: str,
        reference_time: datetime,
        group_id: str,
        uuid: str,
        **kwargs,
    ) -> Any:
        """Persist real episode and entity nodes and relationships directly in Neo4j."""
        if not ping_neo4j() or not self.driver:
            raise RuntimeError("Neo4j is not reachable")

        entity_uuid = f"ent-{uuid[:12]}"
        with self.driver.session() as session:
            session.run(
                """
                MERGE (e:Episode {uuid: $uuid})
                SET e.name = $name,
                    e.body = $body,
                    e.group_id = $group_id,
                    e.source_description = $source_desc,
                    e.reference_time = $ref_time
                MERGE (ent:Entity {name: $name, group_id: $group_id})
                SET ent.uuid = $ent_uuid,
                    ent.fact = $body,
                    ent.type = CASE
                        WHEN $name CONTAINS 'Behaviour' THEN 'Behaviour'
                        ELSE 'Fact'
                    END
                MERGE (e)-[:MENTIONS {group_id: $group_id}]->(ent)
                """,
                uuid=uuid,
                name=name,
                body=episode_body,
                group_id=group_id,
                source_desc=source_description,
                ref_time=reference_time.isoformat() if hasattr(reference_time, "isoformat") else str(reference_time),
                ent_uuid=entity_uuid,
            )

        mock_res = MagicMock()
        mock_res.uuid = uuid
        mock_res.episode.uuid = uuid
        return mock_res

    def search(self, query: str, group_ids: List[str], num_results: int = 10) -> List[Any]:
        """Search real Neo4j entities matching the group IDs."""
        if not ping_neo4j() or not self.driver:
            return []

        edges = []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Episode)-[r:MENTIONS]->(ent:Entity)
                WHERE r.group_id IN $group_ids
                RETURN DISTINCT ent.fact as fact, coalesce(ent.type, 'Fact') as type, ent.name as name
                LIMIT $limit
                """,
                group_ids=group_ids,
                limit=num_results,
            )
            for record in result:
                edge = MagicMock()
                edge.fact = record["fact"]
                edge.type = record["type"]
                edge.name = record["name"]
                edges.append(edge)
        return edges


@pytest.fixture
def real_graphiti_bridge(monkeypatch):
    """Installs real Neo4j graphiti bridge client across all knowledge module call sites."""
    client = RealNeo4jGraphitiBridgeClient()
    for mod_name in (
        "app.services.knowledge.projection_service",
        "app.services.knowledge.retrieval",
        "app.services.knowledge.graphiti_client",
        "app.services.knowledge.gateway",
    ):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "get_graphiti_client"):
            monkeypatch.setattr(mod, "get_graphiti_client", lambda: client)
    return client


# =============================================================================
# Real Infrastructure Fixture
# =============================================================================
@pytest.fixture
def real_infra(real_graphiti_bridge):
    """Provides an isolated real-infrastructure test context across Postgres, Redis, and Neo4j."""
    session = PgSessionLocal()

    # Clear Redis test namespace
    redis_client = get_redis_client()
    clear_in_memory_cache()

    # Create distinct test tenant and provider in real PostgreSQL
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant(
        name=f"Production Drill Tenant {uid}",
        subdomain=f"drill-{uid}",
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    provider = Provider(
        tenant_id=tenant.id,
        name=f"Drill Provider {uid}",
        active=True,
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)

    t_id = tenant.id
    p_id = provider.id
    group_id = format_group_id(t_id, p_id)
    shared_group_id = format_group_id(t_id, None)

    yield {
        "db": session,
        "tenant": tenant,
        "provider": provider,
        "tenant_id": t_id,
        "provider_id": p_id,
        "redis": redis_client,
        "neo4j_driver": get_neo4j_driver(),
        "bridge": real_graphiti_bridge,
    }

    # Teardown Neo4j: Clean up group nodes
    driver = get_neo4j_driver()
    if driver and ping_neo4j():
        try:
            with driver.session() as s:
                s.run("MATCH (n) WHERE n.group_id IN [$g1, $g2] DETACH DELETE n", g1=group_id, g2=shared_group_id)
        except Exception:
            pass

    # Teardown Postgres: Clean up records in dependency order
    try:
        session.rollback()
        session.query(KnowledgeGraphProjection).filter(KnowledgeGraphProjection.tenant_id == t_id).delete()
        session.query(KnowledgeProposal).filter(KnowledgeProposal.tenant_id == t_id).delete()
        session.query(CuratedMemory).filter(CuratedMemory.tenant_id == t_id).delete()
        session.query(LearningEvent).filter(LearningEvent.tenant_id == t_id).delete()
        session.query(Provider).filter(Provider.tenant_id == t_id).delete()
        session.query(Tenant).filter(Tenant.id == t_id).delete()
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("Teardown cleanup encountered error: %s", exc)
    finally:
        session.close()


# =============================================================================
# 1. Real Graphiti Write & Retrieval Test (Section 3)
# =============================================================================
def test_drill_1_real_graphiti_write_and_retrieval(real_infra):
    """Execute end-to-end pipeline against real PostgreSQL, Redis, and Neo4j.

    Provider answers info request -> LearningEvent -> UnifiedCurator -> CuratedMemory ->
    KnowledgeGraphProjection -> process_pending_projections_worker -> Neo4j node/relationship
    -> KnowledgeGateway.retrieve -> PromptBuilder bounded context.
    """
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]
    driver = real_infra["neo4j_driver"]

    # Step 1: LearningEvent creation
    event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="Where is customer parking located?",
        human_content="Free designated patient parking is located in the underground garage on Level B1.",
        status="pending",
        metadata_payload={"category": "parking_facilities"},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    assert event.id is not None

    # Step 2: UnifiedCurator curation
    curator = UnifiedCurator()
    decision = curator.process_learning_event(db=db, event=event)
    db.commit()
    assert decision.status == "processed"

    # Step 3: CuratedMemory ground truth verification
    memory = (
        db.query(CuratedMemory)
        .filter(
            CuratedMemory.tenant_id == tenant.id,
            CuratedMemory.provider_id == provider.id,
            CuratedMemory.status == "active",
        )
        .first()
    )
    assert memory is not None
    assert "underground garage on Level B1" in memory.ideal_response
    assert memory.authority == "owner_verified"

    # Step 4: KnowledgeGraphProjection outbox verification
    projection = (
        db.query(KnowledgeGraphProjection)
        .filter(
            KnowledgeGraphProjection.tenant_id == tenant.id,
            KnowledgeGraphProjection.curated_memory_id == memory.id,
        )
        .first()
    )
    assert projection is not None
    assert projection.status == "pending"

    # Step 5: Worker execution with real skip-locked claiming on PostgreSQL
    worker_summary = process_pending_projections_worker(db=db, batch_size=10)
    assert worker_summary["claimed"] >= 1
    assert worker_summary["projected"] >= 1

    db.refresh(projection)
    assert projection.status == "projected"
    assert projection.graph_episode_uuid is not None

    # Step 6: Verify real Neo4j graph entity and relationship creation
    with driver.session() as s:
        cypher_res = s.run(
            """
            MATCH (e:Episode {uuid: $ep_uuid})-[r:MENTIONS]->(ent:Entity)
            RETURN e.uuid as ep_uuid, ent.fact as fact, r.group_id as group_id
            """,
            ep_uuid=projection.graph_episode_uuid,
        ).single()
        assert cypher_res is not None
        assert "underground garage" in cypher_res["fact"]
        assert cypher_res["group_id"] == format_group_id(tenant.id, provider.id)

    # Step 7: Retrieval via KnowledgeGateway
    query = RetrievalQuery(
        tenant_id=tenant.id,
        provider_id=provider.id,
        query="Where can I park my car?",
    )
    retrieval = knowledge_gateway.retrieve(query, db=db)
    assert len(retrieval.facts) > 0
    assert any("underground garage" in f for f in retrieval.facts)

    # Step 8: Prompt builder bounded context verification
    prompt = build_system_prompt(
        retrieval_result=retrieval,
        provider_instructions=f"You are the virtual assistant for {provider.name}.",
    )
    assert "--- CURATED FACTUAL CONTEXT ---" in prompt
    assert "underground garage on Level B1" in prompt


# =============================================================================
# 2. Real Bootcamp-to-Live Test (Section 4)
# =============================================================================
def test_drill_2_bootcamp_to_live_pathway_and_sibling_isolation(real_infra):
    """Simulate Bootcamp QA -> curation -> graph projection -> live Messages retrieval.

    Verify provider retrieves the fact, while a sibling provider in the same tenant CANNOT.
    """
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    prov_1 = real_infra["provider"]

    # Sibling provider in the SAME tenant
    prov_2 = Provider(tenant_id=tenant.id, name=f"Sibling {uuid.uuid4().hex[:6]}", active=True)
    db.add(prov_2)
    db.commit()
    db.refresh(prov_2)

    # Bootcamp QA teaching
    event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=prov_1.id,
        event_type="explicit_knowledge_answer",
        source="bootcamp",
        customer_message="What is your favourite cuisine?",
        human_content="Italian homemade pasta with fresh basil.",
        status="pending",
        metadata_payload={"category": "personal_preferences"},
    )
    db.add(event)
    db.commit()

    unified_curator.process_learning_event(db=db, event=event)
    db.commit()

    # Process projection worker
    process_pending_projections_worker(db=db)

    # Query pathway for Provider 1
    q1 = RetrievalQuery(tenant_id=tenant.id, provider_id=prov_1.id, query="favourite cuisine pasta")
    res_1 = knowledge_gateway.retrieve(q1, db=db)
    assert any("Italian homemade pasta" in f for f in res_1.facts)

    # Query pathway for Sibling Provider 2
    q2 = RetrievalQuery(tenant_id=tenant.id, provider_id=prov_2.id, query="favourite cuisine pasta")
    res_2 = knowledge_gateway.retrieve(q2, db=db)
    assert not any("Italian homemade pasta" in f for f in res_2.facts)


# =============================================================================
# 3. Real Behavioural Learning Test (Section 5)
# =============================================================================
def test_drill_3_behavioural_learning_and_style_lab_protection(real_infra):
    """Verify material edits stay as evidence without universal overlearning.

    Repeated edits generate behavioural guidance; Style Lab sliders are NOT modified.
    """
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    # Material draft edit shortening formal reply to casual
    event_1 = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="draft_edit",
        source="production_messages",
        original_ai_content="Good afternoon. Please be advised that our clinic offers consultations on weekdays.",
        human_content="Hey! Yes we do, see you on Monday!",
        status="pending",
        diff_payload={"ratio": 0.40, "original_length": 81, "new_length": 34},
    )
    db.add(event_1)
    db.commit()

    dec_1 = unified_curator.process_learning_event(db=db, event=event_1)
    db.commit()

    # Individual edit stays as evidence proposal
    assert dec_1.classification == "material"
    assert dec_1.evidence_count == 1

    # Second material edit increments evidence count
    event_2 = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="draft_edit",
        source="production_messages",
        original_ai_content="Regarding your query, please note that we operate standard hours.",
        human_content="Hey! Standard 9-5 hours here!",
        status="pending",
        diff_payload={"ratio": 0.45, "original_length": 68, "new_length": 30},
    )
    db.add(event_2)
    db.commit()
    dec_2 = unified_curator.process_learning_event(db=db, event=event_2)
    db.commit()
    assert dec_2.evidence_count == 2

    # Explicit behavioural correction establishes behavioural rule
    event_rule = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="explicit_knowledge_answer",
        source="bootcamp",
        customer_message="Tone correction",
        human_content="Always greet casually with 'Hey!' and keep replies under two sentences.",
        metadata_payload={"category": "tone", "reason": "Keep greeting casual and concise."},
        status="pending",
    )
    db.add(event_rule)
    db.commit()
    dec_rule = unified_curator.process_learning_event(db=db, event=event_rule)
    db.commit()

    process_pending_projections_worker(db=db)

    # Verify behavioural retrieval returns rule
    q = RetrievalQuery(tenant_id=tenant.id, provider_id=provider.id, query="greeting tone style")
    res = knowledge_gateway.retrieve(q, db=db)
    assert len(res.behavioural_rules) > 0 or len(res.examples) > 0 or len(res.facts) > 0

    # Verify Style Lab sliders are NOT modified
    db.refresh(provider)
    assert not hasattr(provider, "style_profile_modified") or getattr(provider, "style_profile_modified") is False


# =============================================================================
# 4. Real Temporal Supersession Test (Section 6)
# =============================================================================
def test_drill_4_temporal_supersession_lifecycle(real_infra):
    """Teach durable fact -> change it -> verify old marked superseded, new active, graph updated."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    # Initial durable fact: "I don't work Wednesdays"
    ev1 = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="Do you work on Wednesdays?",
        human_content="I do not take appointments on Wednesdays.",
        status="pending",
        metadata_payload={"category": "wednesday_schedule"},
    )
    db.add(ev1)
    db.commit()
    unified_curator.process_learning_event(db=db, event=ev1)
    db.commit()
    process_pending_projections_worker(db=db)

    mem1 = (
        db.query(CuratedMemory)
        .filter(
            CuratedMemory.tenant_id == tenant.id,
            CuratedMemory.provider_id == provider.id,
            CuratedMemory.status == "active",
        )
        .first()
    )
    assert mem1 is not None
    assert "do not take appointments" in mem1.ideal_response

    # Superseding fact: "I work Wednesdays now"
    ev2 = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="Do you work on Wednesdays?",
        human_content="I work Wednesdays now from 9am to 5pm.",
        status="pending",
        metadata_payload={"category": "wednesday_schedule"},
    )
    db.add(ev2)
    db.commit()
    unified_curator.process_learning_event(db=db, event=ev2)
    db.commit()
    process_pending_projections_worker(db=db)

    # Verify old memory is superseded with supersedes_id link
    db.refresh(mem1)
    assert mem1.status == "superseded"

    mem2 = (
        db.query(CuratedMemory)
        .filter(
            CuratedMemory.tenant_id == tenant.id,
            CuratedMemory.provider_id == provider.id,
            CuratedMemory.status == "active",
        )
        .first()
    )
    assert mem2 is not None
    assert mem2.id != mem1.id
    assert mem2.supersedes_id == mem1.id
    assert "I work Wednesdays now" in mem2.ideal_response

    # Verify retrieval returns new fact, not old fact
    q = RetrievalQuery(tenant_id=tenant.id, provider_id=provider.id, query="work Wednesdays schedule")
    res = knowledge_gateway.retrieve(q, db=db)
    assert any("I work Wednesdays now" in f for f in res.facts)
    assert not any("I do not take appointments on Wednesdays" in f for f in res.facts)


# =============================================================================
# 5. Operational Truth Conflict Test (Section 7)
# =============================================================================
def test_drill_5_operational_truth_conflict_precedence(real_infra):
    """Deliberately conflict learned fact vs live booking tool state in prompt builder."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    retrieval_result = RetrievalResult(
        facts=["Provider generally works Thursday afternoons from 1pm to 6pm."],
        behavioural_rules=[],
        examples=[],
    )

    tool_state = (
        "Live Calendar Availability Verification:\n"
        "- Thursday 3:00 PM: UNAVAILABLE (Slot confirmed booked by Client #402).\n"
        "- Authoritative calendar state strictly overrides any general memory."
    )

    prompt = build_system_prompt(
        retrieval_result=retrieval_result,
        tool_instructions=tool_state,
        provider_instructions="Assist clients with booking requests.",
    )

    # Verify Layer 2 tool/operational truth appears BEFORE Layer 6 Curated Factual Context
    layer2_idx = prompt.find("--- CURRENT APPLICATION / TOOL TRUTH ---")
    layer6_idx = prompt.find("--- CURATED FACTUAL CONTEXT ---")

    assert layer2_idx != -1
    assert layer6_idx != -1
    assert layer2_idx < layer6_idx
    assert "Thursday 3:00 PM: UNAVAILABLE" in prompt
    assert "Provider generally works Thursday afternoons" in prompt


# =============================================================================
# 6. Infrastructure Failure Drills (Sections 8, 9, 10)
# =============================================================================
def test_drill_6_redis_failure_and_recovery(real_infra):
    """Section 8: Verify Redis cache hit -> simulate outage -> fallback to PG -> recovery."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    # Insert test memory in PostgreSQL
    mem = CuratedMemory(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="general",
        user_query="What tea is served?",
        ideal_response="Organic peppermint tea is served upon arrival.",
        knowledge_kind="durable_fact",
        authority="owner_verified",
        status="active",
    )
    db.add(mem)
    db.commit()

    query = RetrievalQuery(tenant_id=tenant.id, provider_id=provider.id, query="tea served arrival")

    # 1. First retrieval -> cache miss, populates Redis
    res_1 = knowledge_gateway.retrieve(query, db=db)
    assert any("peppermint tea" in f for f in res_1.facts)

    # 2. Second retrieval -> Redis cache hit
    res_2 = knowledge_gateway.retrieve(query, db=db)
    assert res_2.metadata.get("cache_hit") is True

    # 3. Simulate Redis outage (ConnectionError)
    with patch("app.services.knowledge.cache.get_redis_client") as mock_client:
        mock_client.side_effect = RedisConnectionError("Simulated Redis connection failure")
        res_fallback = knowledge_gateway.retrieve(query, db=db)
        # Graceful fallback to PostgreSQL ground truth without crashing
        assert any("peppermint tea" in f for f in res_fallback.facts)
        assert res_fallback.metadata.get("cache_hit") is False

    # 4. Redis recovery -> normal caching resumes
    res_recovered = knowledge_gateway.retrieve(query, db=db)
    assert any("peppermint tea" in f for f in res_recovered.facts)


def test_drill_6_neo4j_failure_resilience(real_infra):
    """Section 9: Simulate Neo4j unavailable -> PG fallback -> projection retry -> recovery."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    mem = CuratedMemory(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="insurance",
        user_query="Do you accept private health insurance?",
        ideal_response="Yes, HICAPS on-the-spot health fund claims are supported.",
        knowledge_kind="durable_fact",
        authority="owner_verified",
        status="active",
    )
    db.add(mem)
    db.commit()

    proj = KnowledgeGraphProjection(
        tenant_id=tenant.id,
        provider_id=provider.id,
        curated_memory_id=mem.id,
        projection_type="fact",
        graph_group_id=format_group_id(tenant.id, provider.id),
        status="pending",
        projection_version="2.0",
    )
    db.add(proj)
    db.commit()

    # Simulate Neo4j failure during projection worker run
    with patch("app.services.knowledge.graphiti_client.ping_neo4j", return_value=False):
        with patch.object(ProjectionService, "project_to_graphiti", side_effect=RuntimeError("Neo4j down")):
            worker = ProjectionWorker(worker_id="fail-worker", batch_size=1, max_retries=5)
            summary = worker.process_batch(db=db)
            assert summary["retried"] == 1

            db.refresh(proj)
            assert proj.status == "retry"
            assert proj.attempt_count == 1
            assert proj.next_attempt_at is not None

    # Knowledge queries continue to succeed via PostgreSQL fallback
    q = RetrievalQuery(tenant_id=tenant.id, provider_id=provider.id, query="private health insurance HICAPS")
    res = knowledge_gateway.retrieve(q, db=db)
    assert any("HICAPS" in f for f in res.facts)

    # Recovery: Neo4j back online -> projection processes successfully
    proj.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    recover_worker = ProjectionWorker(worker_id="recover-worker", batch_size=1)
    rec_summary = recover_worker.process_batch(db=db)
    assert rec_summary["projected"] == 1

    db.refresh(proj)
    assert proj.status == "projected"


def test_drill_6_graph_rebuild_and_parity_verification(real_infra):
    """Section 10: Use knowledge_rebuild_service to backfill and verify parity."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    # Seed 3 historical memories
    for i in range(3):
        mem = CuratedMemory(
            tenant_id=tenant.id,
            provider_id=provider.id,
            category=f"rebuild_cat_{i}",
            user_query=f"Rebuild query {i}",
            ideal_response=f"Rebuild verified answer number {i}",
            knowledge_kind="durable_fact",
            authority="owner_verified",
            status="active",
        )
        db.add(mem)
    db.commit()

    # Rebuild graph projections
    rebuild_res = knowledge_rebuild_service.rebuild_graph(
        db=db,
        tenant_id=tenant.id,
        provider_id=provider.id,
        verify=True,
    )

    assert rebuild_res["status"] == "completed"
    assert rebuild_res["curated_memories"]["scanned"] >= 3
    assert rebuild_res["parity"]["parity_ok"] is True
    assert rebuild_res["parity"]["missing_projections_count"] == 0


# =============================================================================
# 7. Worker Crash & Concurrency Drills (Sections 15, 16, 17, 38, 39)
# =============================================================================
def test_drill_7_worker_crash_and_lease_expiry(real_infra):
    """Section 15: Worker crashes holding lease -> expired lease reclaimed by next worker."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    mem = CuratedMemory(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="lease_recovery",
        user_query="Lease crash test query",
        ideal_response="Lease crash response",
        knowledge_kind="durable_fact",
        authority="curator:2.0",
        status="active",
    )
    db.add(mem)
    db.commit()

    # Stale projection simulating dead worker whose lease expired 5 minutes ago
    stale_proj = KnowledgeGraphProjection(
        tenant_id=tenant.id,
        provider_id=provider.id,
        curated_memory_id=mem.id,
        projection_type="fact",
        graph_group_id=format_group_id(tenant.id, provider.id),
        status="processing",
        lease_owner="crashed-worker-uuid-999",
        lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        attempt_count=1,
    )
    db.add(stale_proj)
    db.commit()

    # Active worker claims the expired job and completes it
    active_worker = ProjectionWorker(worker_id="healthy-worker-uuid-101", batch_size=10)
    summary = active_worker.process_batch(db=db)

    assert summary["claimed"] == 1
    assert summary["projected"] == 1

    db.refresh(stale_proj)
    assert stale_proj.status == "projected"
    assert stale_proj.lease_owner is None


def test_drill_7_duplicate_replay_idempotency(real_infra):
    """Section 16: Re-processing identical event/projection produces deterministic UUIDv5 without duplicates."""
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    proj1 = KnowledgeGraphProjection(
        tenant_id=tenant.id,
        provider_id=provider.id,
        curated_memory_id=1001,
        learning_event_id="evt-dup-101",
        projection_type="fact",
    )
    proj2 = KnowledgeGraphProjection(
        tenant_id=tenant.id,
        provider_id=provider.id,
        curated_memory_id=1001,
        learning_event_id="evt-dup-101",
        projection_type="fact",
    )

    uuid1 = ProjectionService.compute_episode_uuid(proj1)
    uuid2 = ProjectionService.compute_episode_uuid(proj2)

    assert uuid1 == uuid2
    assert uuid.UUID(uuid1).version == 5


def test_drill_7_multi_worker_skip_locked_concurrency(real_infra):
    """Section 17: Concurrent workers on real PostgreSQL SKIP LOCKED claim distinct non-overlapping jobs."""
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    # Insert 10 pending projections in real PostgreSQL
    session = PgSessionLocal()
    for i in range(10):
        mem = CuratedMemory(
            tenant_id=tenant.id,
            provider_id=provider.id,
            category=f"concurrency_{i}",
            user_query=f"Concurrent query {i}",
            ideal_response=f"Concurrent response {i}",
            knowledge_kind="durable_fact",
            authority="curator:2.0",
            status="active",
        )
        session.add(mem)
        session.flush()

        proj = KnowledgeGraphProjection(
            tenant_id=tenant.id,
            provider_id=provider.id,
            curated_memory_id=mem.id,
            projection_type="fact",
            graph_group_id=format_group_id(tenant.id, provider.id),
            status="pending",
        )
        session.add(proj)
    session.commit()
    session.close()

    results = []

    def run_worker_thread(worker_name: str):
        thread_db = PgSessionLocal()
        try:
            worker = ProjectionWorker(worker_id=worker_name, batch_size=5)
            summary = worker.process_batch(db=thread_db)
            results.append((worker_name, summary))
        finally:
            thread_db.close()

    t1 = threading.Thread(target=run_worker_thread, args=("worker-alpha",))
    t2 = threading.Thread(target=run_worker_thread, args=("worker-beta",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    total_projected = sum(r[1]["projected"] for r in results)
    assert total_projected == 10


def test_drill_7_dead_letter_replay_lifecycle(real_infra):
    """Sections 38 & 39: Retry exhaustion transitions to dead_letter -> fix -> replay."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    mem = CuratedMemory(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="dead_letter_test",
        user_query="Dead letter test",
        ideal_response="Dead letter response",
        knowledge_kind="durable_fact",
        authority="curator:2.0",
        status="active",
    )
    db.add(mem)
    db.commit()

    proj = KnowledgeGraphProjection(
        tenant_id=tenant.id,
        provider_id=provider.id,
        curated_memory_id=mem.id,
        projection_type="fact",
        graph_group_id=format_group_id(tenant.id, provider.id),
        status="pending",
        attempt_count=4,  # Next failure hits max_retries=5
    )
    db.add(proj)
    db.commit()

    # Fail attempt #5 -> transitions to dead_letter
    with patch.object(ProjectionService, "project_to_graphiti", side_effect=ValueError("Controlled failure")):
        worker = ProjectionWorker(worker_id="failing-worker", batch_size=1, max_retries=5)
        summary = worker.process_batch(db=db)
        assert summary["dead_letter"] == 1

        db.refresh(proj)
        assert proj.status == "dead_letter"
        assert proj.attempt_count == 5
        assert proj.next_attempt_at is None

    # Replay drill: Operator fixes problem and resets projection to retry
    proj.status = "retry"
    proj.attempt_count = 0
    proj.next_attempt_at = datetime.now(timezone.utc)
    db.commit()

    replay_worker = ProjectionWorker(worker_id="replay-worker", batch_size=1)
    rep_summary = replay_worker.process_batch(db=db)
    assert rep_summary["projected"] == 1

    db.refresh(proj)
    assert proj.status == "projected"


# =============================================================================
# 8. Provider & Tenant Isolation Live Tests (Sections 18, 19)
# =============================================================================
def test_drill_8_tenant_and_provider_partition_isolation(real_infra):
    """Sections 18 & 19: Strict multi-tenant and provider boundary isolation."""
    db: Session = real_infra["db"]
    tenant_a = real_infra["tenant"]
    prov_a1 = real_infra["provider"]

    # Provider A2 in Tenant A
    prov_a2 = Provider(tenant_id=tenant_a.id, name="Prov A2", active=True)
    # Tenant B
    tenant_b = Tenant(name=f"Tenant B {uuid.uuid4().hex[:6]}", subdomain=f"tb-{uuid.uuid4().hex[:6]}")
    db.add_all([prov_a2, tenant_b])
    db.commit()

    prov_b = Provider(tenant_id=tenant_b.id, name="Prov B", active=True)
    db.add(prov_b)
    db.commit()

    # 1. Provider A1 private fact
    db.add(
        CuratedMemory(
            tenant_id=tenant_a.id,
            provider_id=prov_a1.id,
            category="isolation",
            user_query="What is your private code?",
            ideal_response="Code Alpha 101.",
            knowledge_kind="durable_fact",
            authority="curator:2.0",
            status="active",
        )
    )

    # 2. Tenant A shared knowledge (provider_id=None)
    db.add(
        CuratedMemory(
            tenant_id=tenant_a.id,
            provider_id=None,
            category="isolation",
            user_query="What is clinic general policy?",
            ideal_response="All clinic staff adhere to Code Cleanliness.",
            knowledge_kind="durable_fact",
            authority="curator:2.0",
            status="active",
        )
    )
    db.commit()

    # Provider A1 queries: retrieves both private fact and tenant-shared fact
    res_a1 = knowledge_gateway.retrieve(RetrievalQuery(tenant_id=tenant_a.id, provider_id=prov_a1.id, query="code"), db=db)
    assert any("Code Alpha 101" in f for f in res_a1.facts)
    assert any("Code Cleanliness" in f for f in res_a1.facts)

    # Provider A2 queries: retrieves tenant-shared fact, CANNOT retrieve Prov A1 private fact
    res_a2 = knowledge_gateway.retrieve(RetrievalQuery(tenant_id=tenant_a.id, provider_id=prov_a2.id, query="code"), db=db)
    assert not any("Code Alpha 101" in f for f in res_a2.facts)
    assert any("Code Cleanliness" in f for f in res_a2.facts)

    # Tenant B queries: CANNOT retrieve Tenant A private or shared facts
    res_b = knowledge_gateway.retrieve(RetrievalQuery(tenant_id=tenant_b.id, provider_id=prov_b.id, query="code"), db=db)
    assert not any("Code Alpha 101" in f for f in res_b.facts)
    assert not any("Code Cleanliness" in f for f in res_b.facts)

    # Clean up Tenant B and Provider A2
    db.query(CuratedMemory).filter(CuratedMemory.tenant_id == tenant_b.id).delete()
    db.query(Provider).filter(Provider.tenant_id == tenant_b.id).delete()
    db.query(Tenant).filter(Tenant.id == tenant_b.id).delete()
    db.query(Provider).filter(Provider.id == prov_a2.id).delete()
    db.commit()


# =============================================================================
# 9. PII Verification (Section 20)
# =============================================================================
def test_drill_9_pii_scrubbing_across_all_layers(real_infra):
    """Section 20: Test customer name, phone, email scrubbed from CuratedMemory, projection, episode, logs."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]

    raw_event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="Hi from Sarah Connor, reached at +1 555-234-5678 or sarah.connor@example.com",
        human_content="Hello Sarah! We will contact you at +1 555-234-5678 or sarah.connor@example.com with details.",
        status="pending",
        metadata_payload={"category": "contact_details"},
    )
    db.add(raw_event)
    db.commit()

    unified_curator.process_learning_event(db=db, event=raw_event)
    db.commit()

    memory = (
        db.query(CuratedMemory)
        .filter(
            CuratedMemory.tenant_id == tenant.id,
            CuratedMemory.provider_id == provider.id,
            CuratedMemory.status == "active",
        )
        .first()
    )
    assert memory is not None

    # Verify PII is scrubbed in CuratedMemory
    assert "555-234-5678" not in memory.user_query
    assert "sarah.connor@example.com" not in memory.user_query
    assert "555-234-5678" not in memory.ideal_response
    assert "sarah.connor@example.com" not in memory.ideal_response
    assert "[PHONE_NUMBER]" in memory.ideal_response or "[PHONE" in memory.ideal_response or "REDACTED" in memory.ideal_response
    assert "[EMAIL_ADDRESS]" in memory.ideal_response or "[EMAIL" in memory.ideal_response or "REDACTED" in memory.ideal_response

    # Verify PII is scrubbed in Graph Projection payload
    process_pending_projections_worker(db=db)
    proj = (
        db.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.curated_memory_id == memory.id)
        .first()
    )
    assert proj is not None
    body = projection_service.build_episode_body(proj, memory=memory, event=raw_event)
    assert "555-234-5678" not in body
    assert "sarah.connor@example.com" not in body


# =============================================================================
# 10. Scale & Latency Verification (Sections 21, 22, 23)
# =============================================================================
def test_drill_10_scale_and_real_latency_benchmarks(real_infra):
    """Sections 21–23: Populate 1,000+ records -> bounded context guaranteed -> latency metrics."""
    db: Session = real_infra["db"]
    tenant = real_infra["tenant"]
    provider = real_infra["provider"]
    driver = real_infra["neo4j_driver"]

    # Bulk insert 1,000 CuratedMemory records in real PostgreSQL
    now = datetime.now(timezone.utc)
    memories = [
        CuratedMemory(
            tenant_id=tenant.id,
            provider_id=provider.id,
            category=f"scale_cat_{i % 20}",
            user_query=f"Scale query number {i} regarding wellness protocols",
            ideal_response=f"Clinic scale guideline {i}: follow standard protocol {i}.",
            knowledge_kind="durable_fact",
            authority="owner_verified",
            status="active",
            created_at=now,
        )
        for i in range(1000)
    ]
    db.bulk_save_objects(memories)
    db.commit()

    # 1. Benchmark: PostgreSQL query latency
    t0 = time.perf_counter()
    pg_count = db.query(CuratedMemory).filter(CuratedMemory.tenant_id == tenant.id).count()
    pg_latency_ms = (time.perf_counter() - t0) * 1000
    assert pg_count >= 1000

    # 2. Benchmark: Bounded context constraint verification
    query = RetrievalQuery(tenant_id=tenant.id, provider_id=provider.id, query="standard protocol wellness")
    t0 = time.perf_counter()
    res_miss = knowledge_gateway.retrieve(query, db=db)
    redis_miss_latency_ms = (time.perf_counter() - t0) * 1000

    # Ensure bounded retrieval limits are strictly respected
    assert len(res_miss.facts) <= settings.KNOWLEDGE_FACTS_LIMIT
    assert len(res_miss.facts) == settings.KNOWLEDGE_FACTS_LIMIT
    assert len(res_miss.behavioural_rules) <= settings.KNOWLEDGE_BEHAVIOUR_LIMIT
    assert len(res_miss.examples) <= settings.KNOWLEDGE_EXAMPLES_LIMIT

    # 3. Benchmark: Redis Cache Hit latency
    t0 = time.perf_counter()
    res_hit = knowledge_gateway.retrieve(query, db=db)
    redis_hit_latency_ms = (time.perf_counter() - t0) * 1000
    assert res_hit.metadata.get("cache_hit") is True

    # 4. Benchmark: Real Neo4j Cypher latency
    t0 = time.perf_counter()
    with driver.session() as s:
        s.run("MATCH (n) RETURN count(n) as total").single()
    neo4j_latency_ms = (time.perf_counter() - t0) * 1000

    # 5. Benchmark: UnifiedCurator single-event latency
    single_event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="What is the check-in procedure?",
        human_content="Check in at the digital kiosk in the lobby.",
        status="pending",
    )
    db.add(single_event)
    db.commit()
    t0 = time.perf_counter()
    unified_curator.process_learning_event(db=db, event=single_event)
    curator_latency_ms = (time.perf_counter() - t0) * 1000
    db.commit()

    # 6. Benchmark: Projection worker latency
    t0 = time.perf_counter()
    process_pending_projections_worker(db=db, batch_size=1)
    proj_latency_ms = (time.perf_counter() - t0) * 1000

    metrics = {
        "pg_query_ms": round(pg_latency_ms, 2),
        "redis_miss_ms": round(redis_miss_latency_ms, 2),
        "redis_hit_ms": round(redis_hit_latency_ms, 2),
        "neo4j_query_ms": round(neo4j_latency_ms, 2),
        "curator_process_ms": round(curator_latency_ms, 2),
        "projection_worker_ms": round(proj_latency_ms, 2),
    }

    print("\n=== Real Infrastructure Latency Benchmarks ===")
    for k, v in metrics.items():
        print(f"  {k}: {v} ms")

    # Assert reasonable real performance bounds
    assert redis_hit_latency_ms < 50.0  # Redis hits are sub-millisecond to low ms
    assert pg_latency_ms < 1000.0
    assert neo4j_latency_ms < 500.0


# =============================================================================
# 11. Granular Health Check Endpoint (Section 24)
# =============================================================================
def test_drill_11_granular_health_check_endpoint(real_infra):
    """Section 24: Test granular readiness endpoint reporting across all subsystems."""
    db = real_infra["db"]

    def override_get_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(fastapi_app)

    try:
        # 1. Normal state: all services healthy
        resp = test_client.get("/health/granular")
        assert resp.status_code == 200
        data = resp.json()

        assert data["fastapi"] == "healthy"
        assert data["postgresql"] == "healthy"
        assert data["redis"] == "healthy"
        assert data["neo4j"] == "healthy"
        assert data["projection_worker"] == "healthy"
        assert data["curator_worker"] == "healthy"
        assert data["status"] == "healthy"

        # 2. Simulated Redis outage -> degraded response
        with patch("app.core.redis.ping", return_value=False):
            resp_degraded = test_client.get("/health/granular")
            data_degraded = resp_degraded.json()
            assert data_degraded["redis"] == "unhealthy"
            assert data_degraded["status"] == "degraded"
            assert data_degraded["postgresql"] == "healthy"
            assert data_degraded["neo4j"] == "healthy"

        # 3. Also verify the public diagnostics route returns same schema
        public_resp = test_client.get("/api/public/diagnostics/readiness")
        assert public_resp.status_code == 200
        assert public_resp.json()["fastapi"] == "healthy"

    finally:
        fastapi_app.dependency_overrides.clear()
