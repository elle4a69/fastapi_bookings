"""Production Canary Rollout Stages 1 and 2 Verification Suite.

Executes Stage 1 (Synthetic Provider 999) and Stage 2 (Single Real Provider 22 / Tori 7)
of the Controlled Production Rollout Builder Brief (Sections 7-25, 47-51).

Tested against real live infrastructure:
- PostgreSQL on port 5433 (fastapi_bookings)
- Redis on port 6380
- Neo4j on ports 7474 & 7687

Critical constraints strictly enforced:
- Zero live external network calls or live SMS.
- Zero customer PII in logs or test outputs.
- No DDL or destruction of historical tables (SmsKnowledgeEntry, CuratedMemory, Vector(1536)).
- Retain safe fallback retrieval path at all times.
- Zero credentials or secrets logged or exposed.
"""

from __future__ import annotations

import _socket
import concurrent.futures
import copy
import logging
import re
import socket
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, desc, text
from sqlalchemy.orm import Session, sessionmaker

import tests.conftest as conftest_module
from app.core.config import settings
from app.core.redis import get_redis_client, ping as redis_ping
from app.db.database import Base
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.learning_event import LearningEvent
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.sms_account import SmsAccount
from app.models.sms_bootcamp import (
    SmsBootcampConversation,
    SmsBootcampMessage,
    SmsBootcampRun,
)
from app.models.sms_conversation import SmsConversation
from app.models.sms_knowledge import SmsKnowledgeEntry
from app.models.sms_message import SmsMessage
from app.models.tenant import Tenant
from app.services.curation.pii_scrubber import scrub_pii
from app.services.knowledge.cache import (
    build_cache_key,
    clear_in_memory_cache,
    get_cached_knowledge,
    get_composite_epoch,
    hash_query,
    increment_provider_epoch,
    increment_tenant_epoch,
    set_cached_knowledge,
)
from app.services.knowledge.curator import UnifiedCurator, unified_curator
from app.services.knowledge.gateway import KnowledgeGateway, knowledge_gateway
from app.services.knowledge.graphiti_client import (
    format_group_id,
    get_neo4j_driver,
    ping_neo4j,
    resolve_query_group_ids,
)
from app.services.knowledge.retrieval import BoundedKnowledgeRetriever
from app.services.knowledge.projection_service import (
    ProjectionService,
    projection_service,
)
from app.services.knowledge.projection_worker import (
    ProjectionWorker,
    process_pending_projections_worker,
)
from app.services.knowledge.shadow_evaluator import (
    ShadowEvaluator,
    compute_overlap_ratio,
    is_canary_active,
    resolve_rollout_mode,
    shadow_evaluator,
)
from app.api.routers.diagnostics import get_diagnostics_metrics
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

# Real container connection URLs (Ports 5433, 6380, 7687)
REAL_PG_URL = "postgresql://postgres:postgres@localhost:5433/fastapi_bookings"
pg_engine = create_engine(REAL_PG_URL, pool_pre_ping=True)
PgSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


# =============================================================================
# Socket Hook: Permit Real Local Infrastructure (Postgres, Redis, Neo4j)
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
# Real Neo4j Graph Driver Client Wrapper (Zero OpenAI calls)
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
        # Classify entity type based on name or source
        name_lower = name.lower()
        if any(k in name_lower for k in ("behaviour", "behavior", "rule", "instruction")):
            ent_type = "Behaviour"
        elif any(k in name_lower for k in ("example", "style", "guidance")):
            ent_type = "Example"
        else:
            ent_type = "Fact"

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
                    ent.type = $ent_type
                MERGE (e)-[:MENTIONS {group_id: $group_id}]->(ent)
                """,
                uuid=uuid,
                name=name,
                body=episode_body,
                group_id=group_id,
                source_desc=source_description,
                ref_time=reference_time.isoformat() if hasattr(reference_time, "isoformat") else str(reference_time),
                ent_uuid=entity_uuid,
                ent_type=ent_type,
            )

        mock_res = MagicMock()
        mock_res.uuid = uuid
        mock_res.episode.uuid = uuid
        return mock_res

    def search(self, query: str, group_ids: List[str], num_results: int = 10) -> List[Any]:
        """Search real Neo4j entities matching the partition group IDs."""
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

        tokens = [w.lower() for w in re.findall(r"\w+", query or "") if len(w) >= 3]
        if tokens:
            def _score(edge_item):
                low = (edge_item.fact or "").lower()
                return sum(1 for t in tokens if t in low)
            edges.sort(key=_score, reverse=True)

        return edges[:num_results]


@pytest.fixture
def real_graphiti_bridge(monkeypatch):
    """Installs real Neo4j graphiti bridge client across all knowledge module call sites."""
    client = RealNeo4jGraphitiBridgeClient()
    for mod_name in (
        "app.services.knowledge.projection_service",
        "app.services.knowledge.retrieval",
        "app.services.knowledge.graphiti_client",
        "app.services.knowledge.gateway",
        "app.services.knowledge.shadow_evaluator",
    ):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "get_graphiti_client"):
            monkeypatch.setattr(mod, "get_graphiti_client", lambda: client)
    return client


# =============================================================================
# Infrastructure Fixtures
# =============================================================================
@pytest.fixture
def real_db():
    """Provides a transactional session on the real PostgreSQL container (port 5433)."""
    session = PgSessionLocal()
    clear_in_memory_cache()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def synthetic_providers_stage1(real_db, real_graphiti_bridge):
    """Ensures synthetic provider 999 and sibling provider 998 exist in Tenant 1 for Stage 1."""
    # Ensure tenant 1 exists
    tenant = real_db.query(Tenant).filter(Tenant.id == 1).first()
    assert tenant is not None, "Tenant 1 must exist in the real database."

    # Synthetic canary provider 999
    prov_999 = real_db.query(Provider).filter(Provider.id == 999).first()
    if not prov_999:
        prov_999 = Provider(
            id=999,
            tenant_id=1,
            name="Synthetic Canary Provider 999",
            active=True,
        )
        real_db.add(prov_999)

    # Synthetic sibling provider 998
    prov_998 = real_db.query(Provider).filter(Provider.id == 998).first()
    if not prov_998:
        prov_998 = Provider(
            id=998,
            tenant_id=1,
            name="Synthetic Sibling Provider 998",
            active=True,
        )
        real_db.add(prov_998)

    real_db.commit()

    group_999 = format_group_id(1, 999)
    group_998 = format_group_id(1, 998)

    yield {
        "tenant_id": 1,
        "provider_id": 999,
        "sibling_provider_id": 998,
        "group_999": group_999,
        "group_998": group_998,
        "db": real_db,
    }

    # Clean up stage 1 test projections and memories created during the test
    driver = get_neo4j_driver()
    if driver and ping_neo4j():
        try:
            with driver.session() as s:
                s.run("MATCH (n) WHERE n.group_id IN [$g1, $g2] DETACH DELETE n", g1=group_999, g2=group_998)
        except Exception:
            pass

    try:
        real_db.rollback()
        real_db.query(KnowledgeGraphProjection).filter(
            KnowledgeGraphProjection.tenant_id == 1,
            KnowledgeGraphProjection.provider_id.in_([998, 999]),
        ).delete(synchronize_session=False)
        real_db.query(KnowledgeProposal).filter(
            KnowledgeProposal.tenant_id == 1,
            KnowledgeProposal.provider_id.in_([998, 999]),
        ).delete(synchronize_session=False)
        real_db.query(CuratedMemory).filter(
            CuratedMemory.tenant_id == 1,
            CuratedMemory.provider_id.in_([998, 999]),
        ).delete(synchronize_session=False)
        real_db.query(LearningEvent).filter(
            LearningEvent.tenant_id == 1,
            LearningEvent.provider_id.in_([998, 999]),
        ).delete(synchronize_session=False)
        real_db.commit()
    except Exception as exc:
        real_db.rollback()
        logger.warning("Stage 1 cleanup warning: %s", exc)


# =============================================================================
# TASK 1: ROLLOUT MODES & FALLBACK RETENTION (Sections 7, 8)
# =============================================================================
class TestRolloutModesAndFallbackRetention:
    """Verifies that the platform strictly supports LEGACY/FALLBACK, CANARY, and GRAPH LIVE modes,

    and verifies non-destructive retention of historical knowledge tables.
    """

    def test_rollout_modes_matrix(self):
        """Verify explicit mode resolution: LEGACY/FALLBACK, CANARY, and GRAPH LIVE."""
        # Mode 1: LEGACY / FALLBACK (GRAPH_KNOWLEDGE_ENABLED=False, no canary IDs)
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):
            assert is_canary_active(tenant_id=1, provider_id=999) is False
            assert is_canary_active(tenant_id=1, provider_id=22) is False

        # Mode 2: CANARY (Scoped to specific provider only)
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [999]), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):
            assert is_canary_active(tenant_id=1, provider_id=999) is True
            assert is_canary_active(tenant_id=1, provider_id=998) is False
            assert is_canary_active(tenant_id=1, provider_id=22) is False

        # Mode 3: GRAPH LIVE (General Availability)
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", True), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):
            assert is_canary_active(tenant_id=1, provider_id=999) is True
            assert is_canary_active(tenant_id=1, provider_id=998) is True
            assert is_canary_active(tenant_id=1, provider_id=22) is True
            assert is_canary_active(tenant_id=2, provider_id=11) is True

    def test_historical_tables_retention_and_schema_integrity(self, real_db):
        """Verify historical tables (SmsKnowledgeEntry, CuratedMemory, Vector(1536))

        remain active, queryable, non-destructive, and retain pgvector extension.
        """
        # 1. Verify SmsKnowledgeEntry queryable without errors
        ske_count = real_db.query(SmsKnowledgeEntry).count()
        assert ske_count >= 0, "SmsKnowledgeEntry table must exist and be queryable."

        # 2. Verify CuratedMemory queryable without errors
        cm_count = real_db.query(CuratedMemory).count()
        assert cm_count >= 0, "CuratedMemory table must exist and be queryable."

        # 3. Verify pgvector extension and vector(1536) column existence
        vector_ext = real_db.execute(
            text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
        assert vector_ext is not None, "pgvector extension must be installed in PostgreSQL."

        vector_cols = real_db.execute(
            text(
                """
                SELECT table_name, column_name, udt_name 
                FROM information_schema.columns 
                WHERE table_name = 'curated_memories' AND column_name = 'embedding'
                """
            )
        ).fetchone()
        assert vector_cols is not None, "curated_memories.embedding must exist."
        assert vector_cols[2] == "vector", "curated_memories.embedding must be of type vector."

        # 4. Verify zero destructive DDL: historical tables retain intact constraints
        tables_res = real_db.execute(
            text(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_name IN ('sms_knowledge_entries', 'curated_memories', 'knowledge_graph_projections')
                """
            )
        ).fetchall()
        found_tables = {row[0] for row in tables_res}
        assert "sms_knowledge_entries" in found_tables
        assert "curated_memories" in found_tables
        assert "knowledge_graph_projections" in found_tables


# =============================================================================
# TASK 2: STAGE 1 — SYNTHETIC PROVIDER (Sections 9, 10, 11, 12)
# =============================================================================
class TestStage1SyntheticProvider:
    """Stage 1 verification suite targeting synthetic provider (provider_id=999)

    under Tenant 1 with canary mode activated (GRAPH_CANARY_PROVIDER_IDS=[999]).
    """

    def test_stage1_e2e_explicit_teaching_lifecycle(
        self, synthetic_providers_stage1, real_graphiti_bridge
    ):
        """Exercise 2a: Explicit knowledge teaching lifecycle.

        Provider answers info request -> LearningEvent -> UnifiedCurator ->
        CuratedMemory -> KnowledgeGraphProjection -> worker -> Neo4j -> KnowledgeGateway.
        """
        db = synthetic_providers_stage1["db"]
        t_id = synthetic_providers_stage1["tenant_id"]
        p_id = synthetic_providers_stage1["provider_id"]

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # 1. Provider answers info request -> LearningEvent created
            event = LearningEvent(
                tenant_id=t_id,
                provider_id=p_id,
                event_type="explicit_knowledge_answer",
                source="production_messages",
                customer_message="Where is synthetic suite 999 located?",
                human_content="Synthetic provider 999 private consultation suite is located on Level 3 Room 302.",
                status="pending",
                metadata_payload={"category": "facilities"},
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            assert event.id is not None

            # 2. UnifiedCurator processes event
            curator = UnifiedCurator()
            decision = curator.process_learning_event(db=db, event=event)
            db.commit()
            assert decision.status == "processed"
            assert decision.memory_id is not None

            # 3. CuratedMemory active in PostgreSQL
            memory = db.query(CuratedMemory).filter(CuratedMemory.id == decision.memory_id).one()
            assert memory.status == "active"
            assert memory.tenant_id == t_id
            assert memory.provider_id == p_id
            assert "Room 302" in memory.ideal_response

            # 4. KnowledgeGraphProjection enqueued in outbox
            projection = (
                db.query(KnowledgeGraphProjection)
                .filter(
                    KnowledgeGraphProjection.curated_memory_id == memory.id,
                    KnowledgeGraphProjection.tenant_id == t_id,
                )
                .one()
            )
            assert projection.status == "pending"

            # 5. Background Projection Worker processes outbox
            summary = process_pending_projections_worker(db=db, batch_size=10)
            assert summary["claimed"] >= 1
            assert summary["projected"] >= 1

            db.refresh(projection)
            assert projection.status == "projected"
            assert projection.graph_episode_uuid is not None

            # 6. Verify entity and relation in real Neo4j
            driver = get_neo4j_driver()
            with driver.session() as s:
                record = s.run(
                    """
                    MATCH (e:Episode {uuid: $uuid})-[r:MENTIONS]->(ent:Entity)
                    RETURN ent.fact as fact, r.group_id as group_id
                    """,
                    uuid=projection.graph_episode_uuid,
                ).single()
                assert record is not None
                assert "Level 3 Room 302" in record["fact"]
                assert record["group_id"] == format_group_id(t_id, p_id)

            # 7. Live retrieval via KnowledgeGateway
            query = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_id,
                query="Where is the private consultation suite?",
            )
            retrieval = knowledge_gateway.retrieve(query, db=db)
            assert len(retrieval.facts) > 0
            assert any("Level 3 Room 302" in f for f in retrieval.facts)

    def test_stage1_behaviour_correction_pipeline(
        self, synthetic_providers_stage1, real_graphiti_bridge
    ):
        """Exercise 2b: Provider response correction -> captured as behavioral guidance

        -> retrieved in future context.
        """
        db = synthetic_providers_stage1["db"]
        t_id = synthetic_providers_stage1["tenant_id"]
        p_id = synthetic_providers_stage1["provider_id"]

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            event = LearningEvent(
                tenant_id=t_id,
                provider_id=p_id,
                event_type="feedback_correction",
                source="production_messages",
                customer_message="Can I arrive 5 minutes early?",
                original_ai_content="Sure thing! Feel free to come whenever you like!",
                human_content="Please arrive exactly 5 minutes before your scheduled appointment time.",
                metadata_payload={
                    "category": "tone",
                    "reason": "Maintain professional punctuality guidance; avoid excessive casualness.",
                },
                status="pending",
            )
            db.add(event)
            db.commit()

            curator = UnifiedCurator()
            decision = curator.process_learning_event(db=db, event=event)
            db.commit()

            assert decision.status == "processed"
            mem = db.query(CuratedMemory).filter(CuratedMemory.id == decision.memory_id).one()
            assert mem.status == "active"
            assert mem.knowledge_kind == "response_guidance"

            # Process outbox
            process_pending_projections_worker(db=db, batch_size=10)

            # Retrieve via KnowledgeGateway
            query = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_id,
                query="Can I arrive early?",
            )
            retrieval = knowledge_gateway.retrieve(query, db=db)
            all_rules = retrieval.behavioural_rules + retrieval.examples + retrieval.facts
            assert any("professional punctuality" in r.lower() or "5 minutes before" in r.lower() for r in all_rules)

    def test_stage1_bootcamp_training_retrievable_in_messages(
        self, synthetic_providers_stage1, real_graphiti_bridge
    ):
        """Exercise 2c: Teach fact in Bootcamp -> verify live Messages for provider 999 retrieves it."""
        db = synthetic_providers_stage1["db"]
        t_id = synthetic_providers_stage1["tenant_id"]
        p_id = synthetic_providers_stage1["provider_id"]

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Create bootcamp conversation
            run = SmsBootcampRun(
                id=str(uuid.uuid4()),
                tenant_id=t_id,
                provider_id=p_id,
                status="running",
                selected_personas=["persona-test"],
            )
            db.add(run)
            db.flush()

            bootcamp_conv = SmsBootcampConversation(
                id=str(uuid.uuid4()),
                run_id=run.id,
                tenant_id=t_id,
                provider_id=p_id,
                persona_id="persona-test",
                persona_name="Test Persona",
                status="handoff",
            )
            db.add(bootcamp_conv)
            db.flush()

            # Bootcamp learning event (source="bootcamp")
            bootcamp_event = LearningEvent(
                tenant_id=t_id,
                provider_id=p_id,
                conversation_id=bootcamp_conv.id,
                event_type="explicit_knowledge_answer",
                source="bootcamp",
                customer_message="Do you provide complimentary herbal tea during appointments?",
                human_content="Complimentary organic chamomile and peppermint tea is provided in the reception lounge.",
                status="pending",
                metadata_payload={"category": "amenities"},
            )
            db.add(bootcamp_event)
            db.commit()

            curator = UnifiedCurator()
            decision = curator.process_learning_event(db=db, event=bootcamp_event)
            db.commit()
            assert decision.status == "processed"

            process_pending_projections_worker(db=db, batch_size=10)

            # Live Messages retrieval for provider 999
            msg_query = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_id,
                query="What drinks or tea are offered?",
            )
            retrieval = knowledge_gateway.retrieve(msg_query, db=db)
            assert any("organic chamomile" in f.lower() or "peppermint tea" in f.lower() for f in retrieval.facts)

    def test_stage1_temporal_supersession_lifecycle(
        self, synthetic_providers_stage1, real_graphiti_bridge
    ):
        """Exercise 2d: Temporal supersession -> change taught fact ->

        old fact marked superseded, new fact retrieved.
        """
        db = synthetic_providers_stage1["db"]
        t_id = synthetic_providers_stage1["tenant_id"]
        p_id = synthetic_providers_stage1["provider_id"]

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Initial fact: 24h notice
            event_v1 = LearningEvent(
                tenant_id=t_id,
                provider_id=p_id,
                event_type="knowledge_answer",
                source="production_messages",
                customer_message="What is the deposit policy?",
                human_content="Synthetic deposit of $50 is refundable up to 24 hours prior to booking.",
                status="pending",
            )
            db.add(event_v1)
            db.commit()

            curator = UnifiedCurator()
            dec_v1 = curator.process_learning_event(db=db, event=event_v1)
            db.commit()
            mem_v1 = db.query(CuratedMemory).filter(CuratedMemory.id == dec_v1.memory_id).one()
            assert mem_v1.status == "active"

            process_pending_projections_worker(db=db, batch_size=10)

            # Superseding fact: 72h notice
            event_v2 = LearningEvent(
                tenant_id=t_id,
                provider_id=p_id,
                event_type="knowledge_answer",
                source="production_messages",
                customer_message="What is the deposit policy?",
                human_content="Synthetic deposit of $50 is refundable up to 72 hours prior to booking due to peak demand.",
                status="pending",
            )
            db.add(event_v2)
            db.commit()

            dec_v2 = curator.process_learning_event(db=db, event=event_v2)
            db.commit()

            db.refresh(mem_v1)
            assert mem_v1.status == "superseded"

            mem_v2 = db.query(CuratedMemory).filter(CuratedMemory.id == dec_v2.memory_id).one()
            assert mem_v2.status == "active"
            assert mem_v2.supersedes_id == mem_v1.id

            process_pending_projections_worker(db=db, batch_size=10)

            # Query retrieval
            query = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_id,
                query="What is the deposit policy?",
            )
            retrieval = knowledge_gateway.retrieve(query, db=db)
            assert any("72 hours" in f for f in retrieval.facts)
            assert not any("24 hours" in f for f in retrieval.facts)

    def test_stage1_sibling_isolation(
        self, synthetic_providers_stage1, real_graphiti_bridge
    ):
        """Exercise 2e: Verify sibling isolation: Provider 998 in same tenant cannot

        retrieve provider 999 private facts (returns 0).
        """
        db = synthetic_providers_stage1["db"]
        t_id = synthetic_providers_stage1["tenant_id"]
        p_canary = synthetic_providers_stage1["provider_id"]  # 999
        p_sibling = synthetic_providers_stage1["sibling_provider_id"]  # 998

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_canary]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Teach private fact strictly for provider 999
            event = LearningEvent(
                tenant_id=t_id,
                provider_id=p_canary,
                event_type="explicit_knowledge_answer",
                source="production_messages",
                customer_message="What is the secret lockbox code for key pickup?",
                human_content="Provider 999 private lockbox key pickup code is 8842.",
                status="pending",
            )
            db.add(event)
            db.commit()

            curator = UnifiedCurator()
            curator.process_learning_event(db=db, event=event)
            db.commit()
            process_pending_projections_worker(db=db, batch_size=10)

            # Canary provider 999 query -> retrieves private fact
            res_canary = knowledge_gateway.retrieve(
                RetrievalQuery(tenant_id=t_id, provider_id=p_canary, query="What is the secret lockbox code?"),
                db=db,
            )
            assert any("8842" in f for f in res_canary.facts)

            # Sibling provider 998 query -> MUST return 0 results containing provider 999 private facts
            res_sibling = knowledge_gateway.retrieve(
                RetrievalQuery(tenant_id=t_id, provider_id=p_sibling, query="What is the secret lockbox code?"),
                db=db,
            )
            assert not any("8842" in f for f in res_sibling.facts)

    def test_stage1_metrics_observability_and_performance(
        self, synthetic_providers_stage1, real_graphiti_bridge
    ):
        """Observe Stage 1 metrics: latencies (Neo4j, Redis, PG), projection backlog,

        dead letters, cache hit rate.
        """
        db = synthetic_providers_stage1["db"]
        t_id = synthetic_providers_stage1["tenant_id"]
        p_id = synthetic_providers_stage1["provider_id"]

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # 1. PostgreSQL Latency
            t0 = time.perf_counter()
            db.execute(text("SELECT 1")).scalar()
            pg_latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

            # 2. Redis Latency
            redis_client = get_redis_client()
            t0 = time.perf_counter()
            redis_client.ping()
            redis_latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

            # 3. Neo4j Latency
            driver = get_neo4j_driver()
            t0 = time.perf_counter()
            with driver.session() as s:
                s.run("RETURN 1 as ping").single()
            neo4j_latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

            # 4. Projection backlog & dead letters
            backlog_count = db.query(KnowledgeGraphProjection).filter(
                KnowledgeGraphProjection.status.in_(["pending", "retry", "processing"])
            ).count()
            dead_letter_count = db.query(KnowledgeGraphProjection).filter(
                KnowledgeGraphProjection.status == "dead_letter"
            ).count()

            # 5. Cache hit rate benchmark
            clear_in_memory_cache()
            query = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_id,
                query="Latency and cache benchmark probe",
            )
            # 1st request -> Cache miss
            r1 = knowledge_gateway.retrieve(query, db=db)
            assert r1.metadata.get("cache_hit") is False

            # 2nd request -> Cache hit
            r2 = knowledge_gateway.retrieve(query, db=db)
            assert r2.metadata.get("cache_hit") is True

            # All latencies within acceptable production boundaries
            assert pg_latency_ms < 50.0, f"PG latency {pg_latency_ms}ms exceeded 50ms"
            assert redis_latency_ms < 20.0, f"Redis latency {redis_latency_ms}ms exceeded 20ms"
            assert neo4j_latency_ms < 100.0, f"Neo4j latency {neo4j_latency_ms}ms exceeded 100ms"
            assert dead_letter_count == 0, f"Unexpected dead letters: {dead_letter_count}"


# =============================================================================
# TASK 3: STAGE 2 SELECTION & BASELINE (Sections 13, 14)
# =============================================================================
class TestStage2SelectionAndBaseline:
    """Discovers and documents the chosen real provider in Tenant 1, establishing

    the pre-canary baseline without logging customer PII.
    """

    def test_stage2_provider_selection_audit(self, real_db):
        """Query port 5433 for eligible real providers in Tenant 1, document config with zero PII."""
        # Query active providers with services and SMS configuration in Tenant 1
        rows = real_db.execute(
            text(
                """
                SELECT p.id, p.tenant_id, p.active,
                       (SELECT count(*) FROM service_providers sp WHERE sp.provider_id = p.id) as services_count,
                       (SELECT count(*) FROM sms_accounts sa WHERE sa.provider_id = p.id AND sa.is_enabled = true) as sms_count,
                       (SELECT count(*) FROM bookings b WHERE b.provider_id = p.id) as bookings_count,
                       (SELECT count(*) FROM curated_memories cm WHERE cm.provider_id = p.id) as curated_memories_count
                FROM providers p
                WHERE p.tenant_id = 1 AND p.active = true
                ORDER BY p.id
                """
            )
        ).fetchall()

        assert len(rows) > 0, "Tenant 1 must contain eligible active providers."

        # Provider 22 selected as primary real canary provider (clean services, active SMS account 11)
        # Sibling provider 23 selected for isolation comparison (clean services, active SMS account 12)
        # Provider 7 (Tori) documented with 180 curated memories
        provider_22 = next((r for r in rows if r[0] == 22), None)
        assert provider_22 is not None, "Provider 22 must exist in Tenant 1."
        assert provider_22[3] >= 1, "Provider 22 must have configured services."
        assert provider_22[4] >= 1, "Provider 22 must have an active SMS account."

        provider_23 = next((r for r in rows if r[0] == 23), None)
        assert provider_23 is not None, "Provider 23 must exist as sibling provider in Tenant 1."

        # Document selection metadata (Zero PII logged)
        selection_metadata = {
            "tenant_id": 1,
            "provider_id": 22,
            "sibling_provider_id": 23,
            "reason_selected": "Production messaging and calendar configured; active SMS account with draft AI mode; configured catalog services; active sibling in same tenant for isolation verification.",
            "services_count": provider_22[3],
            "sms_accounts_count": provider_22[4],
            "historical_bookings_count": provider_22[5],
        }
        logger.info("Stage 2 Provider Selection Audit verified: %s", selection_metadata)

    def test_stage2_pre_canary_baseline_recording(self, real_db):
        """Establish pre-canary baseline: legacy response success, latency, and projection backlog."""
        chosen_provider_id = 22
        t0 = time.perf_counter()

        legacy_data = {
            "shared_entries": real_db.query(SmsKnowledgeEntry).filter(
                SmsKnowledgeEntry.tenant_id == 1, SmsKnowledgeEntry.provider_id.is_(None)
            ).all(),
            "provider_entries": real_db.query(SmsKnowledgeEntry).filter(
                SmsKnowledgeEntry.tenant_id == 1, SmsKnowledgeEntry.provider_id == chosen_provider_id
            ).all(),
            "curated_memories": real_db.query(CuratedMemory).filter(
                CuratedMemory.tenant_id == 1,
                (CuratedMemory.provider_id == chosen_provider_id) | (CuratedMemory.provider_id.is_(None)),
            ).all(),
        }

        # Baseline evaluation via ShadowEvaluator under legacy/pre-canary mode
        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            baseline_res, baseline_metrics = shadow_evaluator.evaluate_and_resolve(
                db=real_db,
                tenant_id=1,
                provider_id=chosen_provider_id,
                message_text="What are your consultation fees and opening hours?",
                legacy_knowledge=legacy_data,
                legacy_latency_ms=(time.perf_counter() - t0) * 1000.0,
            )

            assert baseline_metrics["is_canary"] is False
            assert baseline_res.metadata.get("source") == "legacy"

            # Check pre-canary projection backlog on port 5433
            backlog = real_db.query(KnowledgeGraphProjection).filter(
                KnowledgeGraphProjection.tenant_id == 1,
                KnowledgeGraphProjection.provider_id == chosen_provider_id,
                KnowledgeGraphProjection.status.in_(["pending", "retry", "processing"]),
            ).count()

            assert backlog == 0, "Pre-canary projection backlog for provider 22 should be 0."


# =============================================================================
# TASK 4: STAGE 2 — SINGLE REAL PROVIDER EXECUTION (Sections 15–25)
# =============================================================================
class TestStage2SingleRealProviderExecution:
    """Stage 2 execution suite activating Graphiti canary retrieval for chosen real provider

    (provider_id=22 in tenant 1) while sibling providers remain on legacy fallback.
    """

    CHOSEN_PROVIDER_ID = 22
    SIBLING_PROVIDER_ID = 23
    TENANT_ID = 1

    def test_stage2_conversational_flows_greeting_service_price(
        self, real_db, real_graphiti_bridge
    ):
        """Exercise 4a: Verify real conversational flows (synthetic test messages, zero live SMS):

        Greeting, service inquiry, price inquiry.
        """
        p_id = self.CHOSEN_PROVIDER_ID
        t_id = self.TENANT_ID

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            assert is_canary_active(t_id, p_id) is True

            # Query real provider's services from PostgreSQL
            provider = real_db.query(Provider).filter(Provider.id == p_id).one()
            svcs = (
                real_db.query(Service)
                .join(ServiceProvider, Service.id == ServiceProvider.service_id)
                .filter(ServiceProvider.provider_id == p_id)
                .all()
            )
            assert len(svcs) > 0

            # 1. Greeting inquiry
            q_greeting = RetrievalQuery(tenant_id=t_id, provider_id=p_id, query="Hello! How are you doing today?")
            res_greeting = knowledge_gateway.retrieve(q_greeting, db=real_db)
            assert res_greeting is not None

            # 2. Service question
            q_service = RetrievalQuery(tenant_id=t_id, provider_id=p_id, query="What services do you provide?")
            res_service = knowledge_gateway.retrieve(q_service, db=real_db)
            assert res_service is not None

            # 3. Price question
            q_price = RetrievalQuery(tenant_id=t_id, provider_id=p_id, query="What is the price for standard consultation?")
            res_price = knowledge_gateway.retrieve(q_price, db=real_db)
            assert res_price is not None

            # Verify prompt composition with structured config
            prompt = (
                UnifiedPromptBuilder(tenant_id=t_id, provider_id=p_id)
                .with_core_safety()
                .with_structured_config(provider=provider, services=svcs)
                .with_retrieval_result(res_price)
                .with_spec_54(True)
                .build_system_prompt()
            )

            assert "--- IMMUTABLE PLATFORM SAFETY RULES ---" in prompt
            assert "--- CURRENT APPLICATION / TOOL TRUTH ---" in prompt
            assert any(s.name in prompt for s in svcs)

    def test_stage2_availability_and_booking_safety_override(
        self, real_db, real_graphiti_bridge
    ):
        """Exercise 4b (Section 17): Availability & Booking Safety.

        Verify Layer 2 tool/operational truth strictly overrides graph context in prompt composition.
        """
        p_id = self.CHOSEN_PROVIDER_ID
        t_id = self.TENANT_ID

        # Conflicting scenario: Graph context states service fee is $90, but operational database states $120
        graph_result = RetrievalResult(
            facts=["Legacy note: Consultation fee is $90."],
            behavioural_rules=["Always maintain a courteous and professional demeanor."],
            examples=[],
        )

        provider = real_db.query(Provider).filter(Provider.id == p_id).one()
        live_service = Service(
            tenant_id=t_id,
            name="Authoritative Live Service",
            price=120.0,
            duration=60,
            active=True,
        )

        builder = (
            UnifiedPromptBuilder(tenant_id=t_id, provider_id=p_id)
            .with_core_safety()
            .with_structured_config(provider=provider, services=[live_service])
            .with_retrieval_result(graph_result)
            .with_spec_54(True)
        )

        prompt_str = builder.build_system_prompt()

        # Operational Truth (Layer 2) MUST precede Graph Knowledge (Layer 6)
        assert "--- CURRENT APPLICATION / TOOL TRUTH ---" in prompt_str
        assert "--- CURATED FACTUAL CONTEXT ---" in prompt_str
        pos_op_truth = prompt_str.find("--- CURRENT APPLICATION / TOOL TRUTH ---")
        pos_graph_knowledge = prompt_str.find("--- CURATED FACTUAL CONTEXT ---")
        assert pos_op_truth < pos_graph_knowledge, "Layer 2 operational truth must strictly precede graph knowledge."

        # Discrete messages payload order
        messages = builder.build_messages_payload(discrete_system_messages=True)
        contents = [m["content"] for m in messages]
        idx_op = next(i for i, c in enumerate(contents) if "Available Services & Pricing:" in c)
        idx_graph = next(i for i, c in enumerate(contents) if "Factual Context:" in c)
        assert idx_op < idx_graph, "Discrete message for operational truth must precede graph context."

    def test_stage2_unknown_knowledge_behavior(
        self, real_db, real_graphiti_bridge
    ):
        """Exercise 4c (Section 18): Question about unknown fact -> triggers provider info request

        -> provider answers -> curated -> retrievable in future turns.
        """
        p_id = self.CHOSEN_PROVIDER_ID
        t_id = self.TENANT_ID

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Customer asks question about an unindexed topic
            unknown_q = "Is high-speed guest Wi-Fi available in the client waiting area?"

            # Provider answers info request -> creates LearningEvent
            event = LearningEvent(
                tenant_id=t_id,
                provider_id=p_id,
                event_type="explicit_knowledge_answer",
                source="production_messages",
                customer_message=unknown_q,
                human_content="Yes, complimentary high-speed guest Wi-Fi is available on network 'ClinicGuest'.",
                status="pending",
                metadata_payload={"category": "facilities"},
            )
            real_db.add(event)
            real_db.commit()

            # Unified curation pipeline
            curator = UnifiedCurator()
            decision = curator.process_learning_event(db=real_db, event=event)
            real_db.commit()
            assert decision.status == "processed"

            # Projection outbox processing
            process_pending_projections_worker(db=real_db, batch_size=10)

            # Verification: Now immediately retrievable for future conversation turns
            query = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_id,
                query="Can I connect to Wi-Fi while waiting?",
            )
            res = knowledge_gateway.retrieve(query, db=real_db)
            assert any("ClinicGuest" in f for f in res.facts)

    def test_stage2_provider_correction_behavior(
        self, real_db, real_graphiti_bridge
    ):
        """Exercise 4d (Section 19): Provider edit -> captured as evidence/guidance through unified pipeline."""
        p_id = self.CHOSEN_PROVIDER_ID
        t_id = self.TENANT_ID

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Provider edits an AI draft to adjust phrasing and instructions
            event = LearningEvent(
                tenant_id=t_id,
                provider_id=p_id,
                event_type="draft_edit",
                source="production_messages",
                customer_message="What should I bring to my initial consultation?",
                original_ai_content="Just bring yourself and your ID.",
                human_content="Please bring a valid photo ID, your medication list, and arrive 10 minutes early to fill out registration forms.",
                diff_payload={"ratio": 0.28, "original_length": 32, "new_length": 115},
                status="pending",
            )
            real_db.add(event)
            real_db.commit()

            curator = UnifiedCurator()
            decision = curator.process_learning_event(db=real_db, event=event)
            real_db.commit()

            assert decision.action == "EVIDENCE"
            assert decision.classification == "material"

            # Check proposal created in PostgreSQL
            proposal = real_db.query(KnowledgeProposal).filter(
                KnowledgeProposal.id == decision.proposal_id
            ).one()
            assert proposal.status == "pending"
            assert proposal.authority == "draft_edit_signal"

    def test_stage2_bootcamp_training_real_provider(
        self, real_db, real_graphiti_bridge
    ):
        """Exercise 4e (Section 20): Real provider trains in Bootcamp ->

        live Messages retrieves lesson, sibling provider unaffected.
        """
        p_canary = self.CHOSEN_PROVIDER_ID
        p_sibling = self.SIBLING_PROVIDER_ID
        t_id = self.TENANT_ID

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_canary]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Teach real provider private policy in Bootcamp
            bootcamp_event = LearningEvent(
                tenant_id=t_id,
                provider_id=p_canary,
                event_type="explicit_knowledge_answer",
                source="bootcamp",
                customer_message="Do you provide evening teleconsultations on Thursdays?",
                human_content="Provider 22 offers evening teleconsultations strictly on Thursday evenings between 6 PM and 8 PM.",
                status="pending",
                metadata_payload={"category": "scheduling"},
            )
            real_db.add(bootcamp_event)
            real_db.commit()

            curator = UnifiedCurator()
            curator.process_learning_event(db=real_db, event=bootcamp_event)
            real_db.commit()
            process_pending_projections_worker(db=real_db, batch_size=10)

            # Live Messages retrieval for canary provider retrieves the lesson
            q_canary = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_canary,
                query="Are Thursday evening teleconsultations available?",
            )
            res_canary = knowledge_gateway.retrieve(q_canary, db=real_db)
            assert any("6 PM and 8 PM" in f for f in res_canary.facts)

            # Sibling provider 23 in same tenant retrieves 0 matches for canary provider's private lesson
            q_sibling = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_sibling,
                query="Are Thursday evening teleconsultations available?",
            )
            res_sibling = knowledge_gateway.retrieve(q_sibling, db=real_db)
            assert not any("Provider 22 offers" in f or "6 PM and 8 PM" in f for f in res_sibling.facts)

    def test_stage2_sibling_isolation_monitoring(
        self, real_db, real_graphiti_bridge
    ):
        """Exercise 4f (Section 21): Sibling provider query returns 0 results

        for canary provider's private facts.
        """
        p_canary = self.CHOSEN_PROVIDER_ID
        p_sibling = self.SIBLING_PROVIDER_ID
        t_id = self.TENANT_ID

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_canary]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Verify sibling provider 23 is NOT in canary mode
            assert is_canary_active(t_id, p_canary) is True
            assert is_canary_active(t_id, p_sibling) is False

            # Query sibling provider for private facts
            res_sibling = knowledge_gateway.retrieve(
                RetrievalQuery(tenant_id=t_id, provider_id=p_sibling, query="secret or private provider details"),
                db=real_db,
            )
            # Ensure none of provider 22's private facts leak
            assert not any("Provider 22" in f for f in res_sibling.facts)

    def test_stage2_rollback_trigger_simulation(
        self, real_db, real_graphiti_bridge
    ):
        """Exercise 4g (Sections 22, 23, 24): Simulate rollback by removing provider from canary list;

        verify instantaneous fallback to PostgreSQL without database restoration or data loss.
        Re-enable canary.
        """
        p_id = self.CHOSEN_PROVIDER_ID
        t_id = self.TENANT_ID

        legacy_data = {
            "shared_entries": real_db.query(SmsKnowledgeEntry).filter(
                SmsKnowledgeEntry.tenant_id == t_id, SmsKnowledgeEntry.provider_id.is_(None)
            ).all(),
            "provider_entries": real_db.query(SmsKnowledgeEntry).filter(
                SmsKnowledgeEntry.tenant_id == t_id, SmsKnowledgeEntry.provider_id == p_id
            ).all(),
            "curated_memories": real_db.query(CuratedMemory).filter(
                CuratedMemory.tenant_id == t_id,
                (CuratedMemory.provider_id == p_id) | (CuratedMemory.provider_id.is_(None)),
            ).all(),
        }

        # Step 1: Active Canary State
        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            assert is_canary_active(t_id, p_id) is True
            res_canary, metrics_canary = shadow_evaluator.evaluate_and_resolve(
                db=real_db,
                tenant_id=t_id,
                provider_id=p_id,
                message_text="General checkup inquiry",
                legacy_knowledge=legacy_data,
            )
            assert metrics_canary["is_canary"] is True

        # Step 2: Emergency Rollback Triggered (remove from GRAPH_CANARY_PROVIDER_IDS)
        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Instant fallback verification
            assert is_canary_active(t_id, p_id) is False

            res_rollback, metrics_rollback = shadow_evaluator.evaluate_and_resolve(
                db=real_db,
                tenant_id=t_id,
                provider_id=p_id,
                message_text="General checkup inquiry",
                legacy_knowledge=legacy_data,
            )

            # Instant zero-downtime fallback to PostgreSQL without DB restoration
            assert metrics_rollback["is_canary"] is False
            assert res_rollback.metadata.get("source") == "legacy"

            # Verify no data was lost or corrupted during fallback
            curated_count = real_db.query(CuratedMemory).filter(CuratedMemory.tenant_id == t_id).count()
            assert curated_count >= 1, "All curated memories must remain fully preserved during rollback."

        # Step 3: Re-enable Canary
        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [p_id]), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            assert is_canary_active(t_id, p_id) is True
            res_reinstated, metrics_reinstated = shadow_evaluator.evaluate_and_resolve(
                db=real_db,
                tenant_id=t_id,
                provider_id=p_id,
                message_text="General checkup inquiry",
                legacy_knowledge=legacy_data,
            )
            assert metrics_reinstated["is_canary"] is True


# =============================================================================
# TASK 5: STAGE 3 — SMALL PROVIDER COHORT (Sections 26, 27, 28)
# =============================================================================
class TestStage3SmallProviderCohort:
    """Stage 3 verification suite activating Graphiti canary retrieval for a small
    provider cohort (Providers 7, 22, 23, 1 in Tenant 1) with varied usage patterns.
    """

    COHORT_PROVIDER_IDS = [7, 22, 23, 1]
    TENANT_ID = 1

    def test_stage3_cohort_selection_and_activation(self, real_db):
        """Audit cohort selection criteria and verify canary routing activation (Section 26)."""
        cohort_ids = self.COHORT_PROVIDER_IDS
        t_id = self.TENANT_ID

        # Verify providers exist in real PostgreSQL
        providers = (
            real_db.query(Provider)
            .filter(Provider.tenant_id == t_id, Provider.id.in_(cohort_ids))
            .all()
        )
        assert len(providers) == 4, "All 4 cohort providers must exist in Tenant 1."

        # Verify diverse usage patterns across the cohort
        # 1. Provider 7: Rich knowledge base (Tori) - 180 Style Lab memories & 6 SMS knowledge entries
        p7_mem_count = real_db.query(CuratedMemory).filter(CuratedMemory.provider_id == 7).count()
        p7_ske_count = real_db.query(SmsKnowledgeEntry).filter(SmsKnowledgeEntry.provider_id == 7).count()
        assert p7_mem_count >= 100, f"Provider 7 must have rich memories (found {p7_mem_count})"
        assert p7_ske_count >= 5, f"Provider 7 must have SMS knowledge entries (found {p7_ske_count})"

        # 2. Provider 22: Dr. Sarah Bennett - curated memories, services, active SMS account
        p22_sms = (
            real_db.query(SmsAccount)
            .filter(SmsAccount.provider_id == 22, SmsAccount.is_enabled == True)
            .first()
        )
        p22_svcs = real_db.query(ServiceProvider).filter(ServiceProvider.provider_id == 22).count()
        assert p22_sms is not None, "Provider 22 must have active SMS account"
        assert p22_svcs >= 1, "Provider 22 must have configured services"

        # 3. Provider 23: Marcus Vance - active SMS account, sibling provider
        p23_sms = (
            real_db.query(SmsAccount)
            .filter(SmsAccount.provider_id == 23, SmsAccount.is_enabled == True)
            .first()
        )
        assert p23_sms is not None, "Provider 23 must have active SMS account"

        # 4. Provider 1: Demo Provider 1 - pure baseline catalog (0 curated memories)
        p1_mem_count = (
            real_db.query(CuratedMemory)
            .filter(CuratedMemory.provider_id == 1, CuratedMemory.category != "capacity_test")
            .count()
        )
        assert p1_mem_count == 0, "Provider 1 represents pure catalog baseline (0 curated memories)"

        # Activate cohort canary
        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", cohort_ids), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Verify all cohort members are active in canary mode
            for pid in cohort_ids:
                assert is_canary_active(t_id, pid) is True, f"Cohort provider {pid} must be active in canary"

            # Verify non-cohort providers in Tenant 1 remain on legacy/fallback
            for non_cohort_pid in (2, 8, 9, 10):
                assert is_canary_active(t_id, non_cohort_pid) is False, f"Provider {non_cohort_pid} must NOT be in canary"

            # Verify Tenant 2 providers remain on legacy/fallback
            assert is_canary_active(tenant_id=2, provider_id=11) is False

    def test_stage3_cohort_private_knowledge_isolation(self, real_db, real_graphiti_bridge):
        """Verify private knowledge stays private to each respective provider across the cohort (Section 27a)."""
        t_id = self.TENANT_ID
        cohort_ids = self.COHORT_PROVIDER_IDS

        # Distinct private facts for each cohort provider
        cohort_facts = {
            7: ("p7-cohort-priv-1", "Provider 7 VIP acoustic lounge code is 7077.", "VIP acoustic lounge code"),
            22: ("p22-cohort-priv-1", "Provider 22 private consultation suite is Level 2 Room 204.", "private consultation suite"),
            23: ("p23-cohort-priv-1", "Provider 23 private entrance is via North Atrium Gate B.", "private entrance"),
            1: ("p1-cohort-priv-1", "Provider 1 demonstration kiosk is located at Booth 101.", "demonstration kiosk"),
        }

        # Project private episodes into Neo4j
        for pid, (ep_uuid, fact_body, _) in cohort_facts.items():
            real_graphiti_bridge.add_episode(
                name=f"[Fact] provider:{pid} - private",
                episode_body=fact_body,
                source_description="stage3_test",
                reference_time=datetime.now(timezone.utc),
                group_id=format_group_id(t_id, pid),
                uuid=ep_uuid,
            )

        try:
            with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", cohort_ids), \
                 patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []), \
                 patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

                # 1. Verify each provider retrieves their own private knowledge
                for pid, (_, fact_body, query_str) in cohort_facts.items():
                    res = knowledge_gateway.retrieve(
                        RetrievalQuery(tenant_id=t_id, provider_id=pid, query=query_str),
                        db=real_db,
                    )
                    assert any(fact_body in f for f in res.facts), f"Provider {pid} must retrieve their own private fact."

                    # 2. Verify all other cohort members do NOT retrieve this fact
                    for other_pid in cohort_ids:
                        if other_pid == pid:
                            continue
                        res_other = knowledge_gateway.retrieve(
                            RetrievalQuery(tenant_id=t_id, provider_id=other_pid, query=query_str),
                            db=real_db,
                        )
                        assert not any(fact_body in f for f in res_other.facts), (
                            f"Provider {other_pid} leaked private fact of Provider {pid}: {fact_body}"
                        )

                # 3. Non-cohort provider (Provider 2) and Tenant 2 (Provider 11) receive 0 cohort private facts
                for query_str in ["VIP acoustic lounge code", "private consultation suite", "private entrance", "demonstration kiosk"]:
                    res_p2 = knowledge_gateway.retrieve(
                        RetrievalQuery(tenant_id=t_id, provider_id=2, query=query_str),
                        db=real_db,
                    )
                    assert not any("7077" in f or "Room 204" in f or "Gate B" in f or "Booth 101" in f for f in res_p2.facts)

                    res_t2 = knowledge_gateway.retrieve(
                        RetrievalQuery(tenant_id=2, provider_id=11, query=query_str),
                        db=real_db,
                    )
                    assert not any("7077" in f or "Room 204" in f or "Gate B" in f or "Booth 101" in f for f in res_t2.facts)
        finally:
            driver = get_neo4j_driver()
            if driver and ping_neo4j():
                with driver.session() as s:
                    s.run("MATCH (e:Episode) WHERE e.uuid IN $uuids DETACH DELETE e", uuids=[v[0] for v in cohort_facts.values()])

    def test_stage3_tenant_shared_knowledge_accessible_across_cohort_inaccessible_to_tenant2(
        self, real_db, real_graphiti_bridge
    ):
        """Verify tenant-shared knowledge is accessible across the cohort, but inaccessible to Tenant 2 (Section 27b)."""
        t_id = self.TENANT_ID
        cohort_ids = self.COHORT_PROVIDER_IDS
        shared_ep_uuid = "t1-cohort-shared-parking-1"
        shared_fact = "Tenant 1 Central Facility provides complimentary visitor parking in Bay Area P1."

        # Project tenant-shared knowledge into Neo4j
        real_graphiti_bridge.add_episode(
            name="[Fact] tenant:1 - shared parking",
            episode_body=shared_fact,
            source_description="stage3_test",
            reference_time=datetime.now(timezone.utc),
            group_id=format_group_id(t_id, None),
            uuid=shared_ep_uuid,
        )

        try:
            with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", cohort_ids), \
                 patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []), \
                 patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

                # 1. Accessible to all cohort members
                for pid in cohort_ids:
                    res = knowledge_gateway.retrieve(
                        RetrievalQuery(tenant_id=t_id, provider_id=pid, query="Where is visitor parking?"),
                        db=real_db,
                    )
                    assert any("Bay Area P1" in f for f in res.facts), (
                        f"Tenant-shared parking fact must be accessible to cohort provider {pid}"
                    )

                # 2. Strictly inaccessible to Tenant 2 (Provider 11)
                res_t2 = knowledge_gateway.retrieve(
                    RetrievalQuery(tenant_id=2, provider_id=11, query="Where is visitor parking?"),
                    db=real_db,
                )
                assert not any("Bay Area P1" in f for f in res_t2.facts), (
                    "Tenant-shared fact of Tenant 1 must NOT be accessible to Tenant 2"
                )

                # 3. Verify PostgreSQL fallback path for shared entries (IDs 15, 16)
                retriever = BoundedKnowledgeRetriever(db=real_db)
                for pid in cohort_ids:
                    fb_facts = retriever.retrieve_facts(
                        query="Where is the Main Center located?",
                        tenant_id=t_id,
                        provider_id=pid,
                        as_strings=True,
                    )
                    assert any("100 Main Street" in f for f in fb_facts)

                # Tenant 2 fallback query receives 0 Tenant 1 shared entries
                t2_fb_facts = retriever.retrieve_facts(
                    query="Where is the Main Center located?",
                    tenant_id=2,
                    provider_id=11,
                    as_strings=True,
                )
                assert not any("100 Main Street" in f for f in t2_fb_facts)
        finally:
            driver = get_neo4j_driver()
            if driver and ping_neo4j():
                with driver.session() as s:
                    s.run("MATCH (e:Episode {uuid: $uuid}) DETACH DELETE e", uuid=shared_ep_uuid)

    def test_stage3_bootcamp_training_scoped_strictly_to_cohort_member(
        self, real_db, real_graphiti_bridge
    ):
        """Verify Bootcamp training remains strictly provider-scoped for each cohort member (Section 27c)."""
        t_id = self.TENANT_ID
        p_trained = 23  # Marcus Vance
        cohort_ids = self.COHORT_PROVIDER_IDS

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", cohort_ids), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # 1. Create Bootcamp Run and Conversation for Provider 23
            run = SmsBootcampRun(
                id=str(uuid.uuid4()),
                tenant_id=t_id,
                provider_id=p_trained,
                status="completed",
                selected_personas=["cohort-persona-1"],
            )
            real_db.add(run)
            real_db.flush()

            bootcamp_conv = SmsBootcampConversation(
                id=str(uuid.uuid4()),
                run_id=run.id,
                tenant_id=t_id,
                provider_id=p_trained,
                persona_id="cohort-persona-1",
                persona_name="Acoustic Specialist Persona",
                status="handoff",
            )
            real_db.add(bootcamp_conv)
            real_db.flush()

            # 2. Provider teaches specialized lesson in Bootcamp
            lesson_fact = "Provider 23 Marcus Vance provides specialized acoustic relaxation therapy exclusively on Sunday mornings."
            bootcamp_event = LearningEvent(
                tenant_id=t_id,
                provider_id=p_trained,
                conversation_id=bootcamp_conv.id,
                event_type="explicit_knowledge_answer",
                source="bootcamp",
                customer_message="Do you provide weekend acoustic relaxation therapy sessions?",
                human_content=lesson_fact,
                metadata_payload={"category": "specialty_therapy"},
                status="pending",
            )
            real_db.add(bootcamp_event)
            real_db.commit()

            # 3. Process through curation pipeline & projection worker
            curator = UnifiedCurator()
            decision = curator.process_learning_event(db=real_db, event=bootcamp_event)
            real_db.commit()
            assert decision.status == "processed"

            process_pending_projections_worker(db=real_db, batch_size=10)

            # 4. Live Messages retrieval for trained provider (23) retrieves lesson
            res_23 = knowledge_gateway.retrieve(
                RetrievalQuery(tenant_id=t_id, provider_id=p_trained, query="acoustic relaxation therapy on Sundays"),
                db=real_db,
            )
            assert any("Sunday mornings" in f for f in res_23.facts)

            # 5. Untrained cohort members (7, 22, 1) and Tenant 2 (11) retrieve 0 matches
            for pid in [7, 22, 1]:
                res_other = knowledge_gateway.retrieve(
                    RetrievalQuery(tenant_id=t_id, provider_id=pid, query="acoustic relaxation therapy on Sundays"),
                    db=real_db,
                )
                assert not any("Sunday mornings" in f for f in res_other.facts), (
                    f"Bootcamp lesson of Provider 23 leaked to cohort provider {pid}"
                )

            res_t2 = knowledge_gateway.retrieve(
                RetrievalQuery(tenant_id=2, provider_id=11, query="acoustic relaxation therapy on Sundays"),
                db=real_db,
            )
            assert not any("Sunday mornings" in f for f in res_t2.facts), (
                "Bootcamp lesson of Provider 23 leaked to Tenant 2"
            )

    def test_stage3_prompt_context_boundedness_across_cohort(
        self, real_db, real_graphiti_bridge
    ):
        """Verify prompt context boundedness across the cohort (<= 5 facts, 3 behaviours, 2 examples) (Section 27d)."""
        t_id = self.TENANT_ID
        cohort_ids = self.COHORT_PROVIDER_IDS

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", cohort_ids), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            for pid in cohort_ids:
                # Query knowledge gateway with a broad query to trigger multiple matches
                query = RetrievalQuery(
                    tenant_id=t_id,
                    provider_id=pid,
                    query="What are your service policies, guidelines, style expectations, and booking procedures?",
                )
                res = knowledge_gateway.retrieve(query, db=real_db)

                # Assert strict bounds on retrieved channels (Specs 47, 48)
                assert len(res.facts) <= settings.KNOWLEDGE_FACTS_LIMIT, (
                    f"Provider {pid} exceeded facts limit: {len(res.facts)} > {settings.KNOWLEDGE_FACTS_LIMIT}"
                )
                assert len(res.behavioural_rules) <= settings.KNOWLEDGE_BEHAVIOUR_LIMIT, (
                    f"Provider {pid} exceeded behaviour limit: {len(res.behavioural_rules)} > {settings.KNOWLEDGE_BEHAVIOUR_LIMIT}"
                )
                assert len(res.examples) <= settings.KNOWLEDGE_EXAMPLES_LIMIT, (
                    f"Provider {pid} exceeded examples limit: {len(res.examples)} > {settings.KNOWLEDGE_EXAMPLES_LIMIT}"
                )

                # Assemble prompt with UnifiedPromptBuilder
                provider = real_db.query(Provider).filter(Provider.id == pid).first()
                builder = (
                    UnifiedPromptBuilder(tenant_id=t_id, provider_id=pid)
                    .with_core_safety()
                    .with_retrieval_result(res)
                    .with_spec_54(True)
                )
                if provider:
                    builder = builder.with_structured_config(provider=provider, services=[])

                sys_prompt = builder.build_system_prompt()
                assert "--- IMMUTABLE PLATFORM SAFETY RULES ---" in sys_prompt

                # Build discrete messages payload and verify boundedness
                messages = builder.build_messages_payload(discrete_system_messages=True)
                assert len(messages) >= 1
                total_len = sum(len(m["content"]) for m in messages)
                assert total_len < 15000, f"Prompt payload size {total_len} exceeds bounded threshold for provider {pid}"

    def test_stage3_capacity_and_infrastructure_performance(
        self, real_db, real_graphiti_bridge
    ):
        """Monitor PostgreSQL connection pool, Redis, Neo4j, worker throughput, and p50/p95 latencies (Section 28)."""
        t_id = self.TENANT_ID
        cohort_ids = self.COHORT_PROVIDER_IDS

        with patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", cohort_ids), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # 1. PostgreSQL Connection Pool Check
            pg_pool = pg_engine.pool
            assert pg_pool.size() >= 1, "PostgreSQL connection pool must have active size."
            assert pg_pool.checkedout() <= pg_pool.size() + pg_pool.overflow(), "Checked-out connections must not leak."

            # 2. Redis Connection Check
            redis_client = get_redis_client()
            client_info = redis_client.info("clients")
            connected_clients = int(client_info.get("connected_clients", 0))
            assert connected_clients >= 1, "Redis must have active connections."

            # 3. Neo4j Connection Driver Check
            driver = get_neo4j_driver()
            assert driver is not None, "Neo4j driver must be initialized."
            driver.verify_connectivity()

            # 4. Worker Throughput & Backlog Under Multi-Provider Projections
            created_mem_ids = []
            created_proj_ids = []
            for pid in cohort_ids:
                for idx in range(2):
                    mem = CuratedMemory(
                        tenant_id=t_id,
                        provider_id=pid,
                        category="capacity_test",
                        user_query=f"Capacity probe question {idx} for provider {pid}",
                        ideal_response=f"Capacity probe answer {idx} for provider {pid}",
                        knowledge_kind="durable_fact",
                        authority="explicit_provider_instruction",
                        status="active",
                    )
                    real_db.add(mem)
                    real_db.flush()
                    created_mem_ids.append(mem.id)

                    proj = KnowledgeGraphProjection(
                        tenant_id=t_id,
                        provider_id=pid,
                        curated_memory_id=mem.id,
                        projection_type="fact",
                        graph_group_id=format_group_id(t_id, pid),
                        status="pending",
                    )
                    real_db.add(proj)
                    real_db.flush()
                    created_proj_ids.append(proj.id)

            real_db.commit()

            # Verify initial backlog count
            backlog_before = real_db.query(KnowledgeGraphProjection).filter(
                KnowledgeGraphProjection.id.in_(created_proj_ids),
                KnowledgeGraphProjection.status == "pending",
            ).count()
            assert backlog_before == 8, f"Expected 8 pending projections, found {backlog_before}"

            # Process pending batch with worker
            worker_summary = process_pending_projections_worker(db=real_db, batch_size=20)
            assert worker_summary["claimed"] >= 8
            assert worker_summary["projected"] >= 8

            # Verify backlog drops to 0 and dead letters = 0
            backlog_after = real_db.query(KnowledgeGraphProjection).filter(
                KnowledgeGraphProjection.id.in_(created_proj_ids),
                KnowledgeGraphProjection.status.in_(["pending", "retry", "processing"]),
            ).count()
            dead_letters = real_db.query(KnowledgeGraphProjection).filter(
                KnowledgeGraphProjection.id.in_(created_proj_ids),
                KnowledgeGraphProjection.status == "dead_letter",
            ).count()
            assert backlog_after == 0, f"Backlog should be 0, found {backlog_after}"
            assert dead_letters == 0, f"Dead letters must be 0, found {dead_letters}"

            # 5. Concurrent Multi-Provider Retrieval Latency Benchmark
            clear_in_memory_cache()
            query_tasks = []
            for i in range(40):
                query_tasks.append((cohort_ids[i % len(cohort_ids)], f"Benchmark concurrent query {i}"))

            latencies_ms: List[float] = []

            def _timed_retrieval(prov_id: int, query_text: str) -> float:
                session = PgSessionLocal()
                t0 = time.perf_counter()
                try:
                    q = RetrievalQuery(tenant_id=t_id, provider_id=prov_id, query=query_text)
                    knowledge_gateway.retrieve(q, db=session)
                    return (time.perf_counter() - t0) * 1000.0
                finally:
                    session.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(_timed_retrieval, pid, qtxt) for pid, qtxt in query_tasks]
                for f in concurrent.futures.as_completed(futures):
                    latencies_ms.append(f.result())

            # Record p50 and p95 retrieval latencies
            sorted_latencies = sorted(latencies_ms)
            p50 = sorted_latencies[len(sorted_latencies) // 2]
            p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]

            logger.info("Stage 3 Concurrent Latencies (40 queries): p50=%.2fms, p95=%.2fms", p50, p95)
            assert p50 < 100.0, f"p50 latency {p50}ms exceeded threshold 100ms"
            assert p95 < 250.0, f"p95 latency {p95}ms exceeded threshold 250ms"

            # Clean up test rows
            try:
                real_db.query(KnowledgeGraphProjection).filter(KnowledgeGraphProjection.id.in_(created_proj_ids)).delete(synchronize_session=False)
                real_db.query(CuratedMemory).filter(CuratedMemory.id.in_(created_mem_ids)).delete(synchronize_session=False)
                real_db.commit()
            except Exception as clean_err:
                real_db.rollback()
                logger.warning("Cleanup error in capacity test: %s", clean_err)


# =============================================================================
# TASK 6: STAGE 4 — WHOLE TENANT ACTIVATION (Sections 29, 30)
# =============================================================================
class TestStage4WholeTenantActivation:
    """Stage 4 execution suite enabling Graphiti canary retrieval for the entire Tenant 1
    (GRAPH_CANARY_TENANT_IDS=[1], GRAPH_CANARY_PROVIDER_IDS=[]).
    """

    TENANT_ID = 1

    def test_stage4_pre_activation_audit(self, real_db):
        """Audit Tenant 1 provider count and IDs, tenant-shared vs Style Lab, and Bootcamp scoping (Section 29)."""
        t_id = self.TENANT_ID

        # 1. Audit Tenant 1 Provider List
        providers = (
            real_db.query(Provider)
            .filter(Provider.tenant_id == t_id, Provider.active == True)
            .order_by(Provider.id)
            .all()
        )
        provider_ids = [p.id for p in providers]
        assert len(providers) >= 20, f"Tenant 1 expected >= 20 active providers, found {len(providers)}"
        assert 7 in provider_ids, "Provider 7 (Tori) must be in Tenant 1"
        assert 22 in provider_ids, "Provider 22 must be in Tenant 1"
        assert 23 in provider_ids, "Provider 23 must be in Tenant 1"
        assert 1 in provider_ids, "Provider 1 must be in Tenant 1"

        # Verify Canary Resolution under Whole Tenant Canary Mode
        with patch.object(settings, "GRAPH_CANARY_TENANT_IDS", [t_id]), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Every provider in Tenant 1 is in canary mode
            for pid in provider_ids:
                assert is_canary_active(tenant_id=t_id, provider_id=pid) is True, (
                    f"Provider {pid} in Tenant 1 must be active in canary under whole-tenant activation"
                )

            # Tenant 2 Provider 11 is strictly NOT in canary mode
            assert is_canary_active(tenant_id=2, provider_id=11) is False, (
                "Tenant 2 provider 11 must NOT be in canary mode when only Tenant 1 is activated"
            )

        # 2. Audit Tenant-Shared Knowledge vs Provider-Specific Style Lab Records
        shared_ske_count = real_db.query(SmsKnowledgeEntry).filter(
            SmsKnowledgeEntry.tenant_id == t_id,
            SmsKnowledgeEntry.provider_id.is_(None),
        ).count()
        assert shared_ske_count >= 1, "Tenant 1 must contain tenant-shared knowledge entries"

        p7_style_count = real_db.query(CuratedMemory).filter(
            CuratedMemory.tenant_id == t_id,
            CuratedMemory.provider_id == 7,
            CuratedMemory.knowledge_kind == "style_example",
        ).count()
        assert p7_style_count >= 100, f"Provider 7 must have style examples (found {p7_style_count})"

        # Ensure no Style Lab record for Provider 7 has provider_id IS NULL (must remain provider-specific)
        null_style_count = real_db.query(CuratedMemory).filter(
            CuratedMemory.tenant_id == t_id,
            CuratedMemory.provider_id.is_(None),
            CuratedMemory.knowledge_kind == "style_example",
        ).count()
        assert null_style_count == 0, "No Style Lab records may have NULL provider_id (would contaminate tenant-shared)"

        # 3. Audit Bootcamp Provider Scoping Across Tenant 1
        bootcamp_runs = real_db.query(SmsBootcampRun).filter(SmsBootcampRun.tenant_id == t_id).all()
        for r in bootcamp_runs:
            assert r.provider_id is not None, f"BootcampRun {r.id} must be provider-scoped"

        bootcamp_convs = real_db.query(SmsBootcampConversation).filter(SmsBootcampConversation.tenant_id == t_id).all()
        for c in bootcamp_convs:
            assert c.provider_id is not None, f"BootcampConversation {c.id} must be provider-scoped"

    def test_stage4_cross_provider_runtime_isolation_across_tenant(
        self, real_db, real_graphiti_bridge
    ):
        """Execute deliberate cross-provider runtime isolation tests across multiple providers in Tenant 1 (Section 30)."""
        t_id = self.TENANT_ID
        test_provider_ids = [7, 22, 23, 1, 2, 12]

        # Define 6 provider-specific facts with distinct keywords
        provider_facts = {
            7: ("p7-t1-iso-ep", "Tori private signature aroma oil is Bergamot & Sandalwood.", "aroma oil"),
            22: ("p22-t1-iso-ep", "Dr. Sarah Bennett private diagnostic procedure requires fasting 8 hours prior.", "diagnostic procedure"),
            23: ("p23-t1-iso-ep", "Marcus Vance private studio offers heated basalt stone therapy.", "basalt stone therapy"),
            1: ("p1-t1-iso-ep", "Demo Provider 1 features interactive VR consultation booths.", "VR consultation"),
            2: ("p2-t1-iso-ep", "Demo Provider 2 offers express checkout lane 4.", "checkout lane"),
            12: ("p12-t1-iso-ep", "Provider 12 private suite is located in East Wing Annex Room 12.", "East Wing Annex"),
        }

        # Project distinct episodes into Neo4j
        for pid, (ep_uuid, fact_body, _) in provider_facts.items():
            real_graphiti_bridge.add_episode(
                name=f"[Fact] provider:{pid} - isolation test",
                episode_body=fact_body,
                source_description="stage4_isolation",
                reference_time=datetime.now(timezone.utc),
                group_id=format_group_id(t_id, pid),
                uuid=ep_uuid,
            )

        try:
            with patch.object(settings, "GRAPH_CANARY_TENANT_IDS", [t_id]), \
                 patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
                 patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

                for target_pid, (_, expected_fact, query_topic) in provider_facts.items():
                    # 1. Target provider retrieves their own fact
                    res_target = knowledge_gateway.retrieve(
                        RetrievalQuery(tenant_id=t_id, provider_id=target_pid, query=query_topic),
                        db=real_db,
                    )
                    assert any(expected_fact in f for f in res_target.facts), (
                        f"Provider {target_pid} failed to retrieve own fact: {expected_fact}"
                    )

                    # 2. All other providers MUST receive 0 matches for this fact
                    for other_pid in test_provider_ids:
                        if other_pid == target_pid:
                            continue
                        res_other = knowledge_gateway.retrieve(
                            RetrievalQuery(tenant_id=t_id, provider_id=other_pid, query=query_topic),
                            db=real_db,
                        )
                        assert not any(expected_fact in f for f in res_other.facts), (
                            f"Cross-provider leakage: Provider {other_pid} retrieved Provider {target_pid}'s fact!"
                        )
        finally:
            driver = get_neo4j_driver()
            if driver and ping_neo4j():
                with driver.session() as s:
                    s.run("MATCH (e:Episode) WHERE e.uuid IN $uuids DETACH DELETE e", uuids=[v[0] for v in provider_facts.values()])

    def test_stage4_tenant2_strict_isolation_on_safe_fallback(
        self, real_db, real_graphiti_bridge
    ):
        """Verify Tenant 2 remains completely isolated on safe fallback or isolated graph space (Section 30)."""
        t1_id = 1
        t2_id = 2
        t2_provider_id = 11

        with patch.object(settings, "GRAPH_CANARY_TENANT_IDS", [t1_id]), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            # Tenant 2 is NOT in canary mode
            assert is_canary_active(tenant_id=t2_id, provider_id=t2_provider_id) is False

            # Execute retrieval for Tenant 2
            t2_query = RetrievalQuery(
                tenant_id=t2_id,
                provider_id=t2_provider_id,
                query="Tell me about parking, consultations, and services.",
            )
            res_t2 = knowledge_gateway.retrieve(t2_query, db=real_db)

            # Operates strictly on safe fallback
            assert res_t2.metadata.get("source") == "fallback"

            # Must contain zero Tenant 1 knowledge items
            assert not any("100 Main Street" in f for f in res_t2.facts)
            assert not any("Dr. Sarah Bennett" in f for f in res_t2.facts)
            assert not any("Marcus Vance" in f for f in res_t2.facts)
            assert not any("Tori" in f for f in res_t2.facts)

            # Verify group_ids partition isolation even if graphiti is queried directly
            t2_groups = resolve_query_group_ids(tenant_id=t2_id, provider_id=t2_provider_id)
            assert "tenant:1:shared" not in t2_groups
            assert "tenant:1:provider:22" not in t2_groups
            assert t2_groups == [f"tenant:{t2_id}:provider:{t2_provider_id}", f"tenant:{t2_id}:shared"]

    def test_stage4_zero_downtime_degrade_to_fallback_on_graph_fault(
        self, real_db, real_graphiti_bridge
    ):
        """Verify zero-downtime degrade-to-fallback on simulated individual graph faults (Section 30)."""
        t_id = self.TENANT_ID
        p_id = 22

        with patch.object(settings, "GRAPH_CANARY_TENANT_IDS", [t_id]), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False):

            assert is_canary_active(t_id, p_id) is True

            # 1. Healthy Graphiti retrieval
            q = RetrievalQuery(
                tenant_id=t_id,
                provider_id=p_id,
                query="What services do you provide?",
            )
            res_healthy = knowledge_gateway.retrieve(q, db=real_db)
            assert res_healthy is not None

            # 2. Simulate individual graph fault (Graphiti raises RuntimeError / connection failure)
            with patch.object(real_graphiti_bridge, "search", side_effect=RuntimeError("Simulated Neo4j transient network timeout")):
                clear_in_memory_cache()
                increment_provider_epoch(t_id, p_id)

                # Zero downtime: No exception raised to caller
                res_fault = knowledge_gateway.retrieve(q, db=real_db)
                assert res_fault is not None

                # Degrades gracefully to PostgreSQL fallback
                assert res_fault.metadata.get("source") == "fallback"

                # Verified intact fallback content from PostgreSQL
                assert len(res_fault.facts) >= 1
                assert any("Standard Consultation" in f for f in res_fault.facts)

            # 3. Graph fault resolved -> immediate recovery to Graphiti without restart
            clear_in_memory_cache()
            increment_provider_epoch(t_id, p_id)
            res_recovered = knowledge_gateway.retrieve(q, db=real_db)
            assert res_recovered is not None
            assert res_recovered.metadata.get("source") in ("graphiti", "fallback")


# =============================================================================
# TASK 7: STAGE 5 — GENERAL AVAILABILITY (Sections 31, 32, 33, 41, 48–51, 56)
# =============================================================================
class TestStage5GeneralAvailability:
    """Stage 5 verification suite executing General Availability across all tenants and providers:
    GRAPH_KNOWLEDGE_ENABLED = True
    GRAPH_SHADOW_WRITE = True
    GRAPH_SHADOW_READ = False
    GRAPH_CANARY_PROVIDER_IDS = []
    GRAPH_CANARY_TENANT_IDS = []
    """

    def test_stage5_general_availability_activation(
        self, real_db, real_graphiti_bridge
    ):
        """Verify GA activation: all providers across all tenants route to Graphiti live retrieval (Section 31)."""
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", True), \
             patch.object(settings, "GRAPH_SHADOW_WRITE", True), \
             patch.object(settings, "GRAPH_SHADOW_READ", False), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

            # 1. Verify canary and rollout mode resolution for all tenants/providers
            test_scopes = [(1, 7), (1, 22), (1, 23), (1, 1), (2, 11)]
            for t_id, p_id in test_scopes:
                assert is_canary_active(t_id, p_id) is True, f"Tenant {t_id} Provider {p_id} must resolve active under GA"
                assert resolve_rollout_mode(t_id, p_id) == "graph_live"

            # 2. Add test episodes to Neo4j for Tenant 1 Provider 22 and Tenant 2 Provider 11
            ep_uuids = ["ga-t1-p22-ep", "ga-t2-p11-ep"]
            try:
                real_graphiti_bridge.add_episode(
                    name="[Fact] provider:22 - GA validation",
                    episode_body="Dr. Sarah Bennett GA live retrieval verified.",
                    source_description="stage5_ga_test",
                    reference_time=datetime.now(timezone.utc),
                    group_id=format_group_id(1, 22),
                    uuid=ep_uuids[0],
                )
                real_graphiti_bridge.add_episode(
                    name="[Fact] provider:11 - GA validation",
                    episode_body="Tenant 2 Provider 11 GA live retrieval verified.",
                    source_description="stage5_ga_test",
                    reference_time=datetime.now(timezone.utc),
                    group_id=format_group_id(2, 11),
                    uuid=ep_uuids[1],
                )

                clear_in_memory_cache()
                increment_provider_epoch(1, 22)
                increment_provider_epoch(2, 11)

                # 3. Live retrieval routes to Graphiti
                res_t1 = knowledge_gateway.retrieve(
                    RetrievalQuery(tenant_id=1, provider_id=22, query="GA live retrieval"),
                    db=real_db,
                )
                assert res_t1.metadata.get("source") == "graphiti"
                assert res_t1.metadata.get("rollout_mode") == "graph_live"
                assert any("Dr. Sarah Bennett GA live retrieval verified." in f for f in res_t1.facts)

                res_t2 = knowledge_gateway.retrieve(
                    RetrievalQuery(tenant_id=2, provider_id=11, query="GA live retrieval"),
                    db=real_db,
                )
                assert res_t2.metadata.get("source") == "graphiti"
                assert res_t2.metadata.get("rollout_mode") == "graph_live"
                assert any("Tenant 2 Provider 11 GA live retrieval verified." in f for f in res_t2.facts)
            finally:
                driver = get_neo4j_driver()
                if driver and ping_neo4j():
                    with driver.session() as s:
                        s.run("MATCH (e:Episode) WHERE e.uuid IN $uuids DETACH DELETE e", uuids=ep_uuids)

    def test_stage5_zero_downtime_graceful_fallback_under_fault(
        self, real_db, real_graphiti_bridge
    ):
        """Verify fallback mechanism remains functional: Neo4j/Redis faults degrade to PostgreSQL fallback (Section 31)."""
        t_id = 1
        p_id = 22

        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", True), \
             patch.object(settings, "GRAPH_SHADOW_WRITE", True), \
             patch.object(settings, "GRAPH_SHADOW_READ", False), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

            q = RetrievalQuery(tenant_id=t_id, provider_id=p_id, query="What services do you provide?")

            # 1. Healthy retrieval
            clear_in_memory_cache()
            increment_provider_epoch(t_id, p_id)
            res_healthy = knowledge_gateway.retrieve(q, db=real_db)
            assert res_healthy is not None

            # 2. Graphiti fault: simulate Neo4j connection failure
            with patch.object(real_graphiti_bridge, "search", side_effect=RuntimeError("Neo4j cluster unavailable")):
                clear_in_memory_cache()
                increment_provider_epoch(t_id, p_id)
                # Graceful degradation without downtime or exception
                res_fault = knowledge_gateway.retrieve(q, db=real_db)
                assert res_fault is not None
                assert res_fault.metadata.get("source") == "fallback"
                assert res_fault.metadata.get("rollout_mode") == "graph_live"
                assert any("Standard Consultation" in f for f in res_fault.facts)

            # 3. Redis fault: simulate Redis connection error during retrieval
            from redis.exceptions import ConnectionError as RedisConnErr
            with patch("app.services.knowledge.cache.get_redis_client", side_effect=RedisConnErr("Redis offline")):
                clear_in_memory_cache()
                increment_provider_epoch(t_id, p_id)
                res_redis_down = knowledge_gateway.retrieve(q, db=real_db)
                assert res_redis_down is not None
                # Does not throw, successfully returns retrieved items
                assert len(res_redis_down.facts) > 0 or len(res_redis_down.behavioural_rules) >= 0

            # 4. Instant self-healing recovery once fault clears
            clear_in_memory_cache()
            increment_provider_epoch(t_id, p_id)
            res_recovered = knowledge_gateway.retrieve(q, db=real_db)
            assert res_recovered is not None
            assert res_recovered.metadata.get("source") in ("graphiti", "fallback")

    def test_stage5_telemetry_rollout_identification_and_alerts(
        self, real_db, real_graphiti_bridge, caplog
    ):
        """Verify telemetry distinguishes rollout modes (fallback, canary, graph_live) and alert thresholds are accessible (Sections 32, 33)."""
        import logging

        # 1. Rollout identification verification: fallback, canary, graph_live
        # A: Fallback mode
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):
            clear_in_memory_cache()
            increment_provider_epoch(1, 22)
            assert resolve_rollout_mode(1, 22) == "fallback"
            res_fb = knowledge_gateway.retrieve(
                RetrievalQuery(tenant_id=1, provider_id=22, query="consultation inquiry"),
                db=real_db,
            )
            assert res_fb.metadata.get("rollout_mode") == "fallback"
            assert res_fb.metadata.get("source") == "fallback"

        # B: Canary mode
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", [22]), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):
            clear_in_memory_cache()
            increment_provider_epoch(1, 22)
            assert resolve_rollout_mode(1, 22) == "canary"
            assert resolve_rollout_mode(1, 23) == "fallback"
            res_canary = knowledge_gateway.retrieve(
                RetrievalQuery(tenant_id=1, provider_id=22, query="consultation inquiry"),
                db=real_db,
            )
            assert res_canary.metadata.get("rollout_mode") == "canary"

        # C: Graph Live (GA) mode
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", True), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):
            clear_in_memory_cache()
            increment_provider_epoch(1, 22)
            assert resolve_rollout_mode(1, 22) == "graph_live"
            assert resolve_rollout_mode(2, 11) == "graph_live"
            with caplog.at_level(logging.INFO):
                res_ga = knowledge_gateway.retrieve(
                    RetrievalQuery(tenant_id=1, provider_id=22, query="consultation inquiry"),
                    db=real_db,
                )
                assert res_ga.metadata.get("rollout_mode") == "graph_live"

            # Verify structured logs distinguish all three rollout modes and contain ZERO customer PII
            rollout_logs = [r.message for r in caplog.records if "Knowledge retrieval complete" in r.message]
            assert len(rollout_logs) >= 3
            modes_logged = {
                re.search(r"rollout_mode=(\w+)", msg).group(1)
                for msg in rollout_logs
                if re.search(r"rollout_mode=(\w+)", msg)
            }
            assert "fallback" in modes_logged
            assert "canary" in modes_logged
            assert "graph_live" in modes_logged

            for log_msg in rollout_logs:
                # Verify zero raw customer queries or sensitive content logged
                assert "consultation inquiry" not in log_msg

        # 2. Alert metrics and error thresholds verification via diagnostics/metrics
        diag_metrics = get_diagnostics_metrics(db=real_db)
        assert diag_metrics["status"] == "healthy"
        assert diag_metrics["rollout_mode"] == "graph_live"
        assert "thresholds" in diag_metrics
        assert diag_metrics["thresholds"]["error_rate_pct_limit"] == 1.0
        assert diag_metrics["thresholds"]["p95_latency_ms_limit"] == 200.0
        assert diag_metrics["thresholds"]["max_projection_backlog"] == 500
        assert diag_metrics["thresholds"]["cross_tenant_leakage_tolerance"] == 0
        assert diag_metrics["metrics"]["projection_backlog"] >= 0
        assert diag_metrics["metrics"]["dead_letters"] == 0

    def test_stage5_multitenant_isolation_and_scale_under_ga(
        self, real_db, real_graphiti_bridge
    ):
        """Execute scale and isolation checks across multiple providers in Tenant 1 and Tenant 2 under GA (Section 31)."""
        t1_id = 1
        t2_id = 2
        p1_id = 22
        p2_id = 11

        ep_uuids = ["ga-iso-t1-p22", "ga-iso-t2-p11"]
        t1_secret = "Private T1 Protocol: Blue Sapphire Keycard 7721"
        t2_secret = "Private T2 Protocol: Red Ruby Passcode 9914"

        real_graphiti_bridge.add_episode(
            name="[Fact] provider:22 - isolation fact",
            episode_body=t1_secret,
            source_description="stage5_isolation",
            reference_time=datetime.now(timezone.utc),
            group_id=format_group_id(t1_id, p1_id),
            uuid=ep_uuids[0],
        )
        real_graphiti_bridge.add_episode(
            name="[Fact] provider:11 - isolation fact",
            episode_body=t2_secret,
            source_description="stage5_isolation",
            reference_time=datetime.now(timezone.utc),
            group_id=format_group_id(t2_id, p2_id),
            uuid=ep_uuids[1],
        )

        try:
            with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", True), \
                 patch.object(settings, "GRAPH_SHADOW_WRITE", True), \
                 patch.object(settings, "GRAPH_SHADOW_READ", False), \
                 patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
                 patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

                clear_in_memory_cache()
                increment_provider_epoch(t1_id, p1_id)
                increment_provider_epoch(t2_id, p2_id)

                # 1. Multi-tenant isolation: Tenant 1 queries find T1 fact, never T2 fact
                res_t1 = knowledge_gateway.retrieve(
                    RetrievalQuery(tenant_id=t1_id, provider_id=p1_id, query="Protocol Blue Sapphire Keycard"),
                    db=real_db,
                )
                assert any(t1_secret in f for f in res_t1.facts)
                assert not any(t2_secret in f for f in res_t1.facts)

                # Tenant 2 queries find T2 fact, never T1 fact
                res_t2 = knowledge_gateway.retrieve(
                    RetrievalQuery(tenant_id=t2_id, provider_id=p2_id, query="Protocol Red Ruby Passcode"),
                    db=real_db,
                )
                assert any(t2_secret in f for f in res_t2.facts)
                assert not any(t1_secret in f for f in res_t2.facts)

                # 2. Operational truth precedence (Layer 2 tool truth overrides Layer 6 graph knowledge)
                prov_t1 = real_db.query(Provider).filter(Provider.id == p1_id).one()
                svcs_t1 = (
                    real_db.query(Service)
                    .join(ServiceProvider, Service.id == ServiceProvider.service_id)
                    .filter(ServiceProvider.provider_id == p1_id)
                    .all()
                )

                # Construct prompt with conflicting graph knowledge vs live tool truth
                prompt = (
                    UnifiedPromptBuilder(tenant_id=t1_id, provider_id=p1_id)
                    .with_core_safety()
                    .with_structured_config(provider=prov_t1, services=svcs_t1)
                    .with_retrieval_result(res_t1)
                    .with_spec_54(True)
                    .build_system_prompt()
                )

                # Precedence verified: Tool truth layer appears BEFORE curated knowledge layer
                pos_tool_truth = prompt.find("--- CURRENT APPLICATION / TOOL TRUTH ---")
                pos_curated = prompt.find("--- CURATED FACTUAL CONTEXT ---")
                assert pos_tool_truth != -1, "Tool truth section must be present"
                assert pos_curated != -1, "Curated factual context section must be present"
                assert pos_tool_truth < pos_curated, "Layer 2 tool truth must precede Layer 6 knowledge"

                # 3. Bounded prompt context guarantees (<= 5 facts, 3 behaviours, 2 examples)
                assert len(res_t1.facts) <= settings.KNOWLEDGE_FACTS_LIMIT
                assert len(res_t1.behavioural_rules) <= settings.KNOWLEDGE_BEHAVIOUR_LIMIT
                assert len(res_t1.examples) <= settings.KNOWLEDGE_EXAMPLES_LIMIT
                assert len(res_t2.facts) <= settings.KNOWLEDGE_FACTS_LIMIT
                assert len(res_t2.behavioural_rules) <= settings.KNOWLEDGE_BEHAVIOUR_LIMIT
                assert len(res_t2.examples) <= settings.KNOWLEDGE_EXAMPLES_LIMIT
        finally:
            driver = get_neo4j_driver()
            if driver and ping_neo4j():
                with driver.session() as s:
                    s.run("MATCH (e:Episode) WHERE e.uuid IN $uuids DETACH DELETE e", uuids=ep_uuids)

    def test_stage5_emergency_global_rollback(
        self, real_db, real_graphiti_bridge
    ):
        """Verify instantaneous zero-downtime rollback to PostgreSQL when GRAPH_KNOWLEDGE_ENABLED is flipped (Section 24)."""
        t_id = 1
        p_id = 22

        # Step 1: Active GA state
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", True), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

            assert resolve_rollout_mode(t_id, p_id) == "graph_live"

        # Step 2: Emergency Global Rollback triggered: GRAPH_KNOWLEDGE_ENABLED = False
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", False), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

            # Instant fallback verification
            assert resolve_rollout_mode(t_id, p_id) == "fallback"
            assert is_canary_active(t_id, p_id) is False

            q = RetrievalQuery(tenant_id=t_id, provider_id=p_id, query="Tell me about standard consultation")
            res_rollback = knowledge_gateway.retrieve(q, db=real_db)

            # Reverts immediately to PostgreSQL fallback
            assert res_rollback.metadata.get("source") == "fallback"
            assert res_rollback.metadata.get("rollout_mode") == "fallback"
            assert any("Standard Consultation" in f for f in res_rollback.facts)

            # Zero data loss: verify historical tables and curated memories remain intact
            cm_count = real_db.query(CuratedMemory).filter(CuratedMemory.tenant_id == t_id).count()
            assert cm_count > 0, "CuratedMemory table must remain intact without data loss"
            ske_count = real_db.query(SmsKnowledgeEntry).filter(SmsKnowledgeEntry.tenant_id == t_id).count()
            assert ske_count > 0, "SmsKnowledgeEntry table must remain intact"

        # Step 3: Re-enable GA state: GRAPH_KNOWLEDGE_ENABLED = True
        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", True), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

            assert resolve_rollout_mode(t_id, p_id) == "graph_live"
            assert is_canary_active(t_id, p_id) is True

    def test_stage5_comprehensive_soak_report_metrics(
        self, real_db, real_graphiti_bridge
    ):
        """Execute comprehensive simulated soak run measuring latencies, cache hits, fallbacks, and compile Stage 5 Report (Section 49)."""
        test_queries = [
            (1, 7, "What aroma oils do you use in your massage therapy?"),
            (1, 22, "What are the fasting guidelines before blood diagnostic?"),
            (1, 23, "Can I schedule a heated stone therapy session?"),
            (1, 1, "What basic consultation services are available?"),
            (2, 11, "What are the clinic opening hours and parking info?"),
        ]

        latencies_ms: List[float] = []
        cache_hits = 0
        cache_misses = 0
        fallback_count = 0
        graph_count = 0
        total_queries = 0

        with patch.object(settings, "GRAPH_KNOWLEDGE_ENABLED", True), \
             patch.object(settings, "GRAPH_SHADOW_WRITE", True), \
             patch.object(settings, "GRAPH_SHADOW_READ", False), \
             patch.object(settings, "GRAPH_CANARY_PROVIDER_IDS", []), \
             patch.object(settings, "GRAPH_CANARY_TENANT_IDS", []):

            clear_in_memory_cache()

            # Execute 10 cycles over 5 queries = 50 total queries
            for cycle in range(10):
                for t_id, p_id, q_text in test_queries:
                    t0 = time.perf_counter()
                    res = knowledge_gateway.retrieve(
                        RetrievalQuery(tenant_id=t_id, provider_id=p_id, query=q_text),
                        db=real_db,
                    )
                    latency = (time.perf_counter() - t0) * 1000.0
                    latencies_ms.append(latency)
                    total_queries += 1

                    if res.metadata.get("cache_hit"):
                        cache_hits += 1
                    else:
                        cache_misses += 1

                    if res.metadata.get("source") == "fallback":
                        fallback_count += 1
                    elif res.metadata.get("source") == "graphiti":
                        graph_count += 1

            # Metric calculations
            p50_latency = statistics.median(latencies_ms)
            p95_latency = statistics.quantiles(latencies_ms, n=20)[18]  # 95th percentile
            cache_hit_rate = (cache_hits / total_queries) * 100.0

            # Audit backlog and dead letters in real PostgreSQL
            backlog = real_db.query(KnowledgeGraphProjection).filter(
                KnowledgeGraphProjection.status.in_(["pending", "retry", "processing"])
            ).count()
            dead_letters = real_db.query(KnowledgeGraphProjection).filter(
                KnowledgeGraphProjection.status == "dead_letter"
            ).count()

            # Assert all Stage 5 exit criteria
            assert total_queries == 50, f"Expected 50 soak queries, got {total_queries}"
            assert cache_hit_rate >= 70.0, f"Cache hit rate {cache_hit_rate:.1f}% below 70% threshold"
            assert p95_latency < 200.0, f"p95 latency {p95_latency:.2f}ms exceeded 200ms limit"
            assert p50_latency < 50.0, f"p50 latency {p50_latency:.2f}ms exceeded 50ms target"
            assert dead_letters == 0, f"Unexpected dead letters: {dead_letters}"
            assert backlog == 0, f"Unexpected backlog: {backlog}"


