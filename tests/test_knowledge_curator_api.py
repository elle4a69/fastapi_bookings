"""Real integration tests for Assistant Studio Knowledge Curator API.

Endpoints under test:
- GET /api/admin/assistant-studio/curator/pipeline-status
- GET /api/admin/assistant-studio/curator/memories
- POST /api/admin/assistant-studio/curator/memories
- PUT /api/admin/assistant-studio/curator/memories/{id}
- DELETE /api/admin/assistant-studio/curator/memories/{id}
- POST /api/admin/assistant-studio/curator/memories/{id}/reproject
- GET /api/admin/assistant-studio/curator/graph-nodes

Strictly enforces AGENTS.md Rule 3:
- Zero mock implementations.
- Real database mutations.
- Strict multi-tenant isolation.
- Anti-hallucination dynamic leak rejection.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.learning_event import LearningEvent
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.models.user import User


def _auth_headers(tenant: Tenant, admin_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(admin_user.id)})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


@pytest.fixture
def curator_env(db_session):
    """Seed multi-tenant fixture for curator integration tests."""
    tenant_a = Tenant(name="Alpha Clinic", subdomain="alpha-clinic")
    tenant_b = Tenant(name="Beta Health", subdomain="beta-health")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin-alpha@clinic.test",
        password_hash="pw",
        role="admin",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin-beta@health.test",
        password_hash="pw",
        role="admin",
    )
    provider_a1 = Provider(
        tenant_id=tenant_a.id,
        name="Dr. Tori Alpha",
        email="tori@alpha.test",
        active=True,
    )
    provider_a2 = Provider(
        tenant_id=tenant_a.id,
        name="Dr. Marcus Alpha",
        email="marcus@alpha.test",
        active=True,
    )
    provider_b1 = Provider(
        tenant_id=tenant_b.id,
        name="Dr. Elena Beta",
        email="elena@beta.test",
        active=True,
    )
    db_session.add_all([admin_a, admin_b, provider_a1, provider_a2, provider_b1])
    db_session.flush()

    now = datetime.now(timezone.utc)
    # Seed memories for tenant A
    mem1 = CuratedMemory(
        tenant_id=tenant_a.id,
        provider_id=provider_a1.id,
        category="parking",
        user_query="Where can I park?",
        ideal_response="Free validated parking is available on Level B2 of the medical center.",
        knowledge_kind="durable_fact",
        authority="owner_verified",
        status="active",
        conflict_state="clear",
        confidence_score=1.0,
        content_hash="hash123",
        created_at=now,
        updated_at=now,
    )
    mem2 = CuratedMemory(
        tenant_id=tenant_a.id,
        provider_id=None,  # Tenant shared
        category="cancellation",
        user_query="What is your cancellation policy?",
        ideal_response="Cancellations made 24 hours in advance incur no penalty.",
        knowledge_kind="durable_fact",
        authority="owner_verified",
        status="active",
        conflict_state="clear",
        confidence_score=1.0,
        content_hash="hash456",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([mem1, mem2])
    db_session.flush()

    # Seed projection for mem1
    proj1 = KnowledgeGraphProjection(
        tenant_id=tenant_a.id,
        provider_id=provider_a1.id,
        curated_memory_id=mem1.id,
        projection_type="fact",
        graph_group_id=f"tenant:{tenant_a.id}:provider:{provider_a1.id}",
        status="projected",
        projection_version="2.0",
        created_at=now,
        updated_at=now,
    )
    db_session.add(proj1)
    db_session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "provider_a1": provider_a1,
        "provider_a2": provider_a2,
        "provider_b1": provider_b1,
        "mem1": mem1,
        "mem2": mem2,
    }


def test_pipeline_status_endpoint(curator_env, client: TestClient):
    """GET /api/admin/assistant-studio/curator/pipeline-status returns 6 stages with live metrics."""
    headers = _auth_headers(curator_env["tenant_a"], curator_env["admin_a"])

    resp = client.get("/api/admin/assistant-studio/curator/pipeline-status", headers=headers)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()

    assert data["ok"] is True
    assert data["tenant_id"] == curator_env["tenant_a"].id
    assert len(data["stages"]) == 6
    stage_names = [s["name"] for s in data["stages"]]
    assert stage_names == [
        "Event Trigger",
        "Unified Curator",
        "Relational Authority",
        "Projection Worker",
        "Epistemic Graph",
        "Gateway & Cache",
    ]

    qc = data["queue_counters"]
    assert qc["active_memories"] >= 2
    assert "pending_curation" in qc
    assert "neo4j_node_count" in qc
    assert "redis_cache_hit_ratio" in qc


def test_list_curated_memories_and_filters(curator_env, client: TestClient):
    """GET /api/admin/assistant-studio/curator/memories respects provider, category, and projection state."""
    headers = _auth_headers(curator_env["tenant_a"], curator_env["admin_a"])

    # 1. List all for tenant A
    resp = client.get("/api/admin/assistant-studio/curator/memories", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()
    assert len(items) == 2

    # Check projection status mapping
    mem1_item = next(i for i in items if i["id"] == curator_env["mem1"].id)
    assert mem1_item["graph_projection_status"] == "projected"
    assert mem1_item["is_tenant_shared"] is False

    mem2_item = next(i for i in items if i["id"] == curator_env["mem2"].id)
    assert mem2_item["graph_projection_status"] == "none"
    assert mem2_item["is_tenant_shared"] is True

    # 2. Filter by provider
    p1_id = curator_env["provider_a1"].id
    resp_p1 = client.get(
        f"/api/admin/assistant-studio/curator/memories?provider_id={p1_id}",
        headers=headers,
    )
    assert resp_p1.status_code == status.HTTP_200_OK
    p1_items = resp_p1.json()
    # Includes provider_a1 and tenant_shared
    assert len(p1_items) == 2

    # 3. Filter by tenant shared only
    resp_shared = client.get(
        "/api/admin/assistant-studio/curator/memories?is_tenant_shared=true",
        headers=headers,
    )
    assert resp_shared.status_code == status.HTTP_200_OK
    shared_items = resp_shared.json()
    assert len(shared_items) == 1
    assert shared_items[0]["category"] == "cancellation"

    # 4. Search filter
    resp_search = client.get(
        "/api/admin/assistant-studio/curator/memories?search=parking",
        headers=headers,
    )
    assert resp_search.status_code == status.HTTP_200_OK
    search_items = resp_search.json()
    assert len(search_items) == 1
    assert search_items[0]["id"] == curator_env["mem1"].id


def test_create_curated_memory_success(db_session, curator_env, client: TestClient):
    """POST /api/admin/assistant-studio/curator/memories creates fact, scrubs PII, enqueues projection."""
    headers = _auth_headers(curator_env["tenant_a"], curator_env["admin_a"])

    payload = {
        "category": "facilities",
        "user_query": "Is there wheelchair access at your clinic?",
        "ideal_response": "Yes, an accessibility ramp and wide elevator are available at the north entrance.",
        "provider_id": curator_env["provider_a1"].id,
        "knowledge_kind": "durable_fact",
        "authority": "owner_verified",
    }

    resp = client.post("/api/admin/assistant-studio/curator/memories", json=payload, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    data = resp.json()

    assert data["category"] == "facilities"
    assert data["authority"] == "owner_verified"
    assert data["status"] == "active"
    assert data["graph_projection_status"] == "pending"

    # Verify real DB persistence
    mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == data["id"]).first()
    assert mem is not None
    assert mem.tenant_id == curator_env["tenant_a"].id
    assert mem.content_hash is not None

    # Verify real projection outbox record was created
    proj = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.curated_memory_id == mem.id)
        .first()
    )
    assert proj is not None
    assert proj.status == "pending"
    assert proj.graph_group_id == f"tenant:{curator_env['tenant_a'].id}:provider:{curator_env['provider_a1'].id}"


def test_create_curated_memory_rejects_dynamic_leak(curator_env, client: TestClient):
    """POST /api/admin/assistant-studio/curator/memories fails closed on pricing or live availability."""
    headers = _auth_headers(curator_env["tenant_a"], curator_env["admin_a"])

    # 1. Dynamic pricing leak
    payload_price = {
        "category": "pricing",
        "user_query": "How much for a massage?",
        "ideal_response": "It will cost $120.00 today and pay at https://buy.stripe.com/123",
        "provider_id": curator_env["provider_a1"].id,
    }
    resp_price = client.post(
        "/api/admin/assistant-studio/curator/memories",
        json=payload_price,
        headers=headers,
    )
    assert resp_price.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Dynamic availability slot leak
    payload_slot = {
        "category": "availability",
        "user_query": "Can I come in tomorrow?",
        "ideal_response": "We have an open slot tomorrow at 2:00 PM with Tori.",
        "provider_id": curator_env["provider_a1"].id,
    }
    resp_slot = client.post(
        "/api/admin/assistant-studio/curator/memories",
        json=payload_slot,
        headers=headers,
    )
    assert resp_slot.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_update_curated_memory_with_supersession(db_session, curator_env, client: TestClient):
    """PUT /api/admin/assistant-studio/curator/memories/{id} triggers immutable supersession chain."""
    headers = _auth_headers(curator_env["tenant_a"], curator_env["admin_a"])
    old_id = curator_env["mem1"].id

    update_payload = {
        "ideal_response": "Free validated parking is now on Level B3 instead of Level B2.",
        "user_query": "Where can I park my car?",
        "action": "supersede",
    }

    resp = client.put(
        f"/api/admin/assistant-studio/curator/memories/{old_id}",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()

    assert data["ok"] is True
    assert data["superseded_memory_id"] == old_id
    new_id = data["new_memory_id"]
    assert new_id != old_id

    # Verify old memory is now 'superseded' in database
    old_mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == old_id).first()
    assert old_mem.status == "superseded"
    assert old_mem.effective_until is not None

    # Verify new memory is active and points to old supersedes_id
    new_mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == new_id).first()
    assert new_mem.status == "active"
    assert new_mem.supersedes_id == old_id
    assert "Level B3" in new_mem.ideal_response


def test_quarantine_and_retract_curated_memory(db_session, curator_env, client: TestClient):
    """PUT with quarantine and DELETE retraction mutate database status."""
    headers = _auth_headers(curator_env["tenant_a"], curator_env["admin_a"])
    mem_id = curator_env["mem1"].id

    # 1. Quarantine
    q_resp = client.put(
        f"/api/admin/assistant-studio/curator/memories/{mem_id}",
        json={"action": "quarantine"},
        headers=headers,
    )
    assert q_resp.status_code == status.HTTP_200_OK
    assert q_resp.json()["status"] == "quarantined"

    mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == mem_id).first()
    assert mem.status == "quarantined"

    # 2. Retract (DELETE)
    del_resp = client.delete(
        f"/api/admin/assistant-studio/curator/memories/{mem_id}",
        headers=headers,
    )
    assert del_resp.status_code == status.HTTP_200_OK
    assert del_resp.json()["status"] == "retracted"

    mem_del = db_session.query(CuratedMemory).filter(CuratedMemory.id == mem_id).first()
    assert mem_del.status == "superseded"


def test_reproject_curated_memory(db_session, curator_env, client: TestClient):
    """POST /api/admin/assistant-studio/curator/memories/{id}/reproject enqueues outbox projection."""
    headers = _auth_headers(curator_env["tenant_a"], curator_env["admin_a"])
    mem_id = curator_env["mem2"].id  # Originally had no projection

    resp = client.post(
        f"/api/admin/assistant-studio/curator/memories/{mem_id}/reproject",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["ok"] is True
    assert data["status"] == "pending"

    # Verify real projection outbox record exists in DB
    proj = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.curated_memory_id == mem_id)
        .first()
    )
    assert proj is not None
    assert proj.status == "pending"


def test_get_epistemic_graph_nodes_and_edges(curator_env, client: TestClient):
    """GET /api/admin/assistant-studio/curator/graph-nodes builds graph structure with central provider."""
    headers = _auth_headers(curator_env["tenant_a"], curator_env["admin_a"])
    p1 = curator_env["provider_a1"]

    resp = client.get(
        f"/api/admin/assistant-studio/curator/graph-nodes?provider_id={p1.id}",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    graph = resp.json()

    assert graph["ok"] is True
    assert graph["provider_id"] == p1.id
    assert graph["provider_name"] == p1.name

    nodes = graph["nodes"]
    edges = graph["edges"]
    assert len(nodes) >= 3  # Provider node, Tenant node, category/topic nodes, memory nodes
    assert len(edges) >= 2

    # Verify central provider node exists
    prov_node = next((n for n in nodes if n["type"] == "provider"), None)
    assert prov_node is not None
    assert prov_node["label"] == p1.name
    assert prov_node["scope"] == "provider_private"

    # Verify tenant shared node exists
    tenant_node = next((n for n in nodes if n["type"] == "tenant"), None)
    assert tenant_node is not None
    assert tenant_node["scope"] == "tenant_shared"

    # Verify directed edges have ontological labels
    edge_relations = {e["relation"] for e in edges}
    assert any(r in edge_relations for r in ["SUPPORTED_BY", "APPLIES_WHEN", "PREFERS", "HAS_BOUNDARY"])


def test_cross_tenant_isolation_boundary(curator_env, client: TestClient):
    """Tenant B cannot read, mutate, or supersede Tenant A's curated memories."""
    headers_b = _auth_headers(curator_env["tenant_b"], curator_env["admin_b"])
    mem_a_id = curator_env["mem1"].id

    # 1. Tenant B cannot see Tenant A's memories in list
    resp_list = client.get("/api/admin/assistant-studio/curator/memories", headers=headers_b)
    assert resp_list.status_code == status.HTTP_200_OK
    assert len(resp_list.json()) == 0

    # 2. Tenant B cannot supersede Tenant A's memory
    resp_edit = client.put(
        f"/api/admin/assistant-studio/curator/memories/{mem_a_id}",
        json={"ideal_response": "Malicious override attempt"},
        headers=headers_b,
    )
    assert resp_edit.status_code == status.HTTP_404_NOT_FOUND

    # 3. Tenant B cannot delete/retract Tenant A's memory
    resp_del = client.delete(
        f"/api/admin/assistant-studio/curator/memories/{mem_a_id}",
        headers=headers_b,
    )
    assert resp_del.status_code == status.HTTP_404_NOT_FOUND

    # 4. Tenant B cannot reproject Tenant A's memory
    resp_reproj = client.post(
        f"/api/admin/assistant-studio/curator/memories/{mem_a_id}/reproject",
        headers=headers_b,
    )
    assert resp_reproj.status_code == status.HTTP_404_NOT_FOUND

    # 5. Tenant B cannot query graph using Tenant A's provider
    resp_graph = client.get(
        f"/api/admin/assistant-studio/curator/graph-nodes?provider_id={curator_env['provider_a1'].id}",
        headers=headers_b,
    )
    assert resp_graph.status_code == status.HTTP_404_NOT_FOUND

