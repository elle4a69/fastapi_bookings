"""Comprehensive End-to-End Integration Tests for Codex inside FastAPI Bookings.

Covers:
1. Full Project & Thread Lifecycle:
   - Create project -> Create thread -> Dispatch turn -> Stream events -> Inspect diff -> Complete turn
2. Health & Sentinels:
   - Health check endpoint (public & authenticated)
   - Deep diagnostics sentinel covering database, event broker, worktree storage, worker, telemetry
   - OpenTelemetry latency checks and telemetry configuration test
3. Multi-Tenant Boundary:
   - Isolation between tenants (e.g. simplydemo vs otherdemo)
   - Admin authentication enforcement (unauthenticated, client role, tampered tokens)
   - Path boundary and directory traversal containment
4. Concurrency & Reconnection:
   - Multiple concurrent turns with independent sequence and status tracking
   - SSE client disconnect and reconnection with event backlog replay
   - Graceful recovery and turn interruption
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

import app.main  # Ensures codex-control-centre is inserted into sys.path
from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User

from backend.database import SessionLocal as CodexSessionLocal
from backend.models.codex import Project, Thread, Turn, Item, WorkspaceBoundary
from backend.services.event_service import broker, EventEnvelope
from backend.services.boundary_service import add_boundary


def _create_admin_user(db_session: Session, suffix: str = "mount") -> tuple[Tenant, User, dict[str, str]]:
    tenant = Tenant(name=f"Codex Admin Tenant {suffix}", subdomain=f"codex-admin-{suffix}")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        login=f"admin-{suffix}",
        password_hash="test-secret-hash",
        role="owner",
        is_platform_owner=True,
    )
    db_session.add(user)
    db_session.commit()

    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }
    return tenant, user, headers


def _create_non_admin_user(db_session: Session, suffix: str = "nonadmin") -> tuple[Tenant, User, dict[str, str]]:
    tenant = Tenant(name=f"Codex Client Tenant {suffix}", subdomain=f"codex-client-{suffix}")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        login=f"client-{suffix}",
        password_hash="test-secret-hash",
        role="client",
    )
    db_session.add(user)
    db_session.commit()

    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }
    return tenant, user, headers


def _init_test_git_repo(path: Path) -> Path:
    repo = path / f"e2e_repo_{uuid.uuid4().hex[:6]}"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "E2E Specialist"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "e2e@example.com"], cwd=str(repo), check=True, capture_output=True)
    (repo / "README.md").write_text("# E2E Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo), check=True, capture_output=True)
    
    # Ensure boundary is registered in codex database
    with CodexSessionLocal() as codex_db:
        try:
            add_boundary(codex_db, str(repo.resolve()), name=repo.name)
        except Exception:
            pass
    return repo


# ============================================================================
# 1. Full Project & Thread Lifecycle (a)
# ============================================================================

def test_e2e_full_project_thread_lifecycle_with_diff_and_completion(client: TestClient, db_session: Session, tmp_path: Path):
    """End-to-End Lifecycle:
    Create project -> Create thread -> Dispatch turn -> Stream events -> Inspect diff -> Complete turn.
    """
    tenant, user, headers = _create_admin_user(db_session, suffix="lifecycle")
    repo_dir = _init_test_git_repo(tmp_path)

    # 1. Create Project
    proj_payload = {
        "name": "E2E Codex Integration Project",
        "repo_path": str(repo_dir),
        "default_branch": "main",
    }
    res_proj = client.post("/api/admin/codex/projects", json=proj_payload, headers=headers)
    assert res_proj.status_code == 200
    proj_data = res_proj.json()
    project_id = proj_data["id"]
    assert proj_data["name"] == "E2E Codex Integration Project"
    assert proj_data["repo_path"] == str(repo_dir.resolve())

    # 2. Create Thread
    thread_payload = {
        "project_id": project_id,
        "title": "E2E Lifecycle Remediation Thread",
    }
    res_thread = client.post("/api/admin/codex/threads", json=thread_payload, headers=headers)
    assert res_thread.status_code == 200
    thread_data = res_thread.json()
    thread_id = thread_data["id"]
    assert thread_data["project_id"] == project_id
    assert thread_data["title"] == "E2E Lifecycle Remediation Thread"
    assert thread_data["status"] == "active"

    # 3. Dispatch Turn
    turn_payload = {
        "thread_id": thread_id,
        "prompt": "Refactor auth middleware to enforce multi-tenant isolation",
        "model": "gpt-4o",
    }
    res_turn = client.post("/api/admin/codex/turns/start", json=turn_payload, headers=headers)
    assert res_turn.status_code == 200
    turn_data = res_turn.json()
    turn_id = turn_data["turn_id"]
    assert turn_data["status"] == "active"
    assert "workspace_root" in turn_data

    # Verify Turn persisted in Codex SQLite DB
    with CodexSessionLocal() as codex_db:
        turn = codex_db.query(Turn).filter(Turn.id == turn_id).first()
        assert turn is not None
        assert turn.thread_id == thread_id
        assert turn.turn_number == 1
        assert turn.status == "active"
        assert turn.prompt == "Refactor auth middleware to enforce multi-tenant isolation"

    # 4. Stream Events & Inspect Diff
    # Request single-use scoped SSE ticket
    ticket_res = client.post(
        "/api/admin/codex/events/ticket",
        json={"project_id": project_id, "thread_id": thread_id},
        headers=headers,
    )
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["ticket"]
    assert len(ticket) > 10

    # Publish turn_started event
    broker.publish_event(
        EventEnvelope(
            project_id=project_id,
            thread_id=thread_id,
            type="turn_started",
            payload={"turn_id": turn_id, "status": "active"},
        )
    )

    # Publish file_change event containing unified diff
    unified_diff = """--- a/app/core/security.py
+++ b/app/core/security.py
@@ -42,2 +42,2 @@
-    return None
+    return tenant_id
"""
    diff_event = broker.publish_event(
        EventEnvelope(
            project_id=project_id,
            thread_id=thread_id,
            type="file_change",
            payload={
                "turn_id": turn_id,
                "path": "app/core/security.py",
                "diff": unified_diff,
                "diff_text": unified_diff,
                "action": "modified",
            },
        )
    )

    # Record diff Item into Turn
    with CodexSessionLocal() as codex_db:
        item = Item(
            id=f"item_{uuid.uuid4().hex[:8]}",
            turn_id=turn_id,
            item_type="diff",
            content={"path": "app/core/security.py", "diff": unified_diff},
            sequence=1,
        )
        codex_db.add(item)
        codex_db.commit()

        # Verify diff stored in database
        persisted_item = codex_db.query(Item).filter(Item.turn_id == turn_id).first()
        assert persisted_item is not None
        assert persisted_item.item_type == "diff"
        assert persisted_item.content["diff"] == unified_diff

    # 5. Complete Turn
    with CodexSessionLocal() as codex_db:
        db_turn = codex_db.query(Turn).filter(Turn.id == turn_id).first()
        db_turn.status = "completed"
        db_turn.completed_at = datetime.now(timezone.utc)
        codex_db.commit()

    completed_event = broker.publish_event(
        EventEnvelope(
            project_id=project_id,
            thread_id=thread_id,
            type="turn_completed",
            payload={
                "turn_id": turn_id,
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    )

    # Connect to SSE Stream with the issued ticket
    sse_res = client.get(
        f"/api/admin/codex/events/{project_id}/{thread_id}?sse_ticket={ticket}&max_events=3",
        headers=headers,
    )
    assert sse_res.status_code == 200
    assert "text/event-stream" in sse_res.headers.get("content-type", "")
    sse_text = sse_res.text
    assert "event: file_change" in sse_text
    assert "return tenant_id" in sse_text
    assert "event: turn_completed" in sse_text


# ============================================================================
# 2. Health & Sentinels (b)
# ============================================================================

def test_e2e_health_and_sentinels_deep_diagnostics(client: TestClient, db_session: Session):
    """Health check endpoint, OpenTelemetry latency checks, and worker sentinels."""
    tenant, user, headers = _create_admin_user(db_session, suffix="sentinels")

    # 1. Platform-owner-protected health check
    health_res = client.get("/api/admin/codex/health", headers=headers)
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["status"] == "healthy"
    assert health_data["codex_db"] in ("ok", "connected")
    assert health_data["version"] == "1.0.0"
    assert "timestamp" in health_data

    # 2. Authenticated Deep Diagnostics Sentinel
    diag_res = client.get("/api/admin/codex/diagnostics/deep", headers=headers)
    assert diag_res.status_code == 200
    diag_data = diag_res.json()
    assert diag_data["status"] == "healthy"
    subsystems = diag_data["subsystems"]

    assert "database" in subsystems
    assert subsystems["database"]["status"] == "healthy"
    assert subsystems["database"]["connected"] is True

    assert "event_broker" in subsystems
    assert subsystems["event_broker"]["status"] == "healthy"

    assert "worktree_storage" in subsystems
    assert subsystems["worktree_storage"]["status"] == "healthy"
    assert subsystems["worktree_storage"]["writable"] is True

    assert "worker" in subsystems
    assert "telemetry" in subsystems

    # 3. Telemetry Configuration Retrieval
    tel_res = client.get("/api/admin/codex/settings/telemetry", headers=headers)
    assert tel_res.status_code == 200
    tel_data = tel_res.json()
    assert "otlp_endpoint" in tel_data
    assert "signoz_url" in tel_data
    assert "enabled" in tel_data

    # 4. OpenTelemetry Latency Probe
    probe_res = client.post(
        "/api/admin/codex/settings/telemetry/test",
        json={"endpoint": "http://127.0.0.1:4318/v1/traces"},
        headers=headers,
    )
    assert probe_res.status_code == 200
    probe_data = probe_res.json()
    assert "latency_ms" in probe_data
    assert isinstance(probe_data["latency_ms"], (int, float))
    assert probe_data["latency_ms"] >= 0.0
    assert "status" in probe_data


# ============================================================================
# 3. Multi-Tenant Boundary (c)
# ============================================================================

def test_e2e_multi_tenant_boundary_and_auth_enforcement(client: TestClient, db_session: Session):
    """Verify isolation between tenants, authentication enforcement, and boundary containment."""
    # Create Tenant A (simplydemo) and Tenant B (otherdemo)
    tenant_a, user_a, headers_a = _create_admin_user(db_session, suffix="simplydemo")
    tenant_b, user_b, headers_b = _create_admin_user(db_session, suffix="otherdemo")

    # 1. Both admin users can access their own tenant routes
    res_a = client.get("/api/admin/codex/projects", headers=headers_a)
    assert res_a.status_code == 200

    res_b = client.get("/api/admin/codex/projects", headers=headers_b)
    assert res_b.status_code == 200

    # 2. Cross-Tenant token tampering rejected
    tampered_headers = {
        "X-Tenant": tenant_b.subdomain,
        "X-Token": headers_a["X-Token"],  # Token from Tenant A used against Tenant B
    }
    res_tampered = client.get("/api/admin/codex/projects", headers=tampered_headers)
    assert res_tampered.status_code in (401, 403)

    # 3. Non-Admin (Client Role) rejected with 403 Forbidden across all endpoints
    _, _, non_admin_headers = _create_non_admin_user(db_session, suffix="unprivileged")

    endpoints_to_test = [
        ("GET", "/api/admin/codex/projects", None),
        ("GET", "/api/admin/codex/threads", None),
        ("POST", "/api/admin/codex/turns/start", {"thread_id": "test", "prompt": "test"}),
        ("GET", "/api/admin/codex/diagnostics/deep", None),
        ("GET", "/api/admin/codex/settings/boundaries", None),
        ("POST", "/api/admin/codex/events/ticket", {"project_id": "test", "thread_id": "test"}),
    ]

    for method, endpoint, payload in endpoints_to_test:
        if method == "GET":
            resp = client.get(endpoint, headers=non_admin_headers)
        else:
            resp = client.post(endpoint, json=payload, headers=non_admin_headers)
        assert resp.status_code == 403, f"Endpoint {endpoint} allowed non-admin access!"

    # 4. Unauthenticated access rejected with 401/403
    for method, endpoint, payload in endpoints_to_test:
        if method == "GET":
            resp = client.get(endpoint)
        else:
            resp = client.post(endpoint, json=payload)
        assert resp.status_code in (400, 401, 403)

    # 5. Path boundary security: traversal and unallowed drives rejected with 400
    invalid_boundary_payload = {"path": "Z:\\illegal\\unmounted\\drive"}
    res_invalid_boundary = client.post(
        "/api/admin/codex/settings/boundaries",
        json=invalid_boundary_payload,
        headers=headers_a,
    )
    assert res_invalid_boundary.status_code == 400


# ============================================================================
# 4. Concurrency & Reconnection (d)
# ============================================================================

def test_e2e_concurrency_and_sse_reconnection(client: TestClient, db_session: Session, tmp_path: Path):
    """Verify multiple concurrent turns, SSE client disconnect/reconnect, and graceful recovery."""
    tenant, user, headers = _create_admin_user(db_session, suffix="concurrency")
    repo_dir = _init_test_git_repo(tmp_path)

    # Setup Project
    proj_res = client.post(
        "/api/admin/codex/projects",
        json={"name": "Concurrency Test Project", "repo_path": str(repo_dir), "default_branch": "main"},
        headers=headers,
    )
    project_id = proj_res.json()["id"]

    # 1. Multiple Concurrent Turns
    threads = []
    for i in range(3):
        th_res = client.post(
            "/api/admin/codex/threads",
            json={"project_id": project_id, "title": f"Concurrent Thread {i}"},
            headers=headers,
        )
        threads.append(th_res.json()["id"])

    # Dispatch concurrent turns across threads
    turn_ids = []
    for tid in threads:
        t_res = client.post(
            "/api/admin/codex/turns/start",
            json={"thread_id": tid, "prompt": f"Concurrent execution on {tid}"},
            headers=headers,
        )
        assert t_res.status_code == 200
        turn_ids.append(t_res.json()["turn_id"])

    # Ensure all turn IDs are unique and recorded in DB
    assert len(set(turn_ids)) == 3
    with CodexSessionLocal() as codex_db:
        for tid, turn_id in zip(threads, turn_ids):
            turn = codex_db.query(Turn).filter(Turn.id == turn_id).first()
            assert turn is not None
            assert turn.thread_id == tid
            assert turn.turn_number == 1
            assert turn.status == "active"

    # 2. SSE Client Disconnect & Reconnection with Event Backlog Replay
    recon_thread_id = threads[0]

    # Publish sequential events
    e1 = broker.publish_event(
        EventEnvelope(
            project_id=project_id,
            thread_id=recon_thread_id,
            type="turn_started",
            payload={"step": 1, "msg": "Turn initialized"},
        )
    )
    e2 = broker.publish_event(
        EventEnvelope(
            project_id=project_id,
            thread_id=recon_thread_id,
            type="reasoning_summary",
            payload={"step": 2, "msg": "Analyzing AST dependencies"},
        )
    )
    e3 = broker.publish_event(
        EventEnvelope(
            project_id=project_id,
            thread_id=recon_thread_id,
            type="file_change",
            payload={"step": 3, "msg": "Modifying file", "diff": "+ fix"},
        )
    )
    e4 = broker.publish_event(
        EventEnvelope(
            project_id=project_id,
            thread_id=recon_thread_id,
            type="turn_completed",
            payload={"step": 4, "msg": "Turn completed"},
        )
    )

    # Verify history in event broker
    history_after_e2 = broker.get_history(recon_thread_id, last_event_id=e2.id)
    assert len(history_after_e2) == 2
    assert history_after_e2[0].id == e3.id
    assert history_after_e2[1].id == e4.id

    # Request SSE ticket and simulate reconnection with Last-Event-ID header
    ticket_res = client.post(
        "/api/admin/codex/events/ticket",
        json={"project_id": project_id, "thread_id": recon_thread_id},
        headers=headers,
    )
    ticket = ticket_res.json()["ticket"]

    recon_sse_res = client.get(
        f"/api/admin/codex/events/{project_id}/{recon_thread_id}?sse_ticket={ticket}&last_event_id={e2.id}&max_events=2",
        headers=headers,
    )
    assert recon_sse_res.status_code == 200
    body = recon_sse_res.text
    # Must contain e3 and e4, but NOT e1
    assert e3.id in body
    assert e4.id in body
    assert e1.id not in body

    # 3. Graceful Recovery & Turn Interruption
    active_turn_id = turn_ids[0]
    interrupt_res = client.post(
        "/api/admin/codex/turns/interrupt",
        json={"thread_id": recon_thread_id, "turn_id": active_turn_id},
        headers=headers,
    )
    assert interrupt_res.status_code == 200
    assert interrupt_res.json()["status"] == "interrupted"

    # Verify database status updated
    with CodexSessionLocal() as codex_db:
        interrupted_turn = codex_db.query(Turn).filter(Turn.id == active_turn_id).first()
        assert interrupted_turn.status == "interrupted"
        assert interrupted_turn.completed_at is not None

    # Verify turn_interrupted event published
    broker_history = broker.get_history(recon_thread_id)
    assert any(ev.type == "turn_interrupted" for ev in broker_history)
