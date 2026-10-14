"""Tests for Codex Control Centre backend routers mounted directly into FastAPI Bookings."""

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User


def _create_admin_user(db_session: Session, suffix: str = "mount") -> tuple[Tenant, User, dict[str, str]]:
    tenant = Tenant(name=f"Codex Admin Tenant {suffix}", subdomain=f"codex-admin-{suffix}")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        login=f"admin-{suffix}",
        password_hash="test-secret-hash",
        role="owner",
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


def test_unauthenticated_requests_rejected(client: TestClient, db_session: Session):
    """Unauthenticated requests without admin tokens must be rejected with 401/403."""
    tenant = Tenant(name="Unauth Tenant", subdomain="unauth-tenant")
    db_session.add(tenant)
    db_session.commit()

    headers_no_token = {"X-Tenant": tenant.subdomain}

    # Settings boundaries
    res1 = client.get("/api/admin/codex/settings/boundaries", headers=headers_no_token)
    assert res1.status_code in (401, 403)

    # Projects
    res2 = client.get("/api/admin/codex/projects", headers=headers_no_token)
    assert res2.status_code in (401, 403)

    # Threads
    res3 = client.get("/api/admin/codex/threads", headers=headers_no_token)
    assert res3.status_code in (401, 403)

    # Turns
    res4 = client.post(
        "/api/admin/codex/turns/start",
        json={"thread_id": "test", "prompt": "hi"},
        headers=headers_no_token,
    )
    assert res4.status_code in (401, 403)

    # Models
    res5 = client.get("/api/admin/codex/models", headers=headers_no_token)
    assert res5.status_code in (401, 403)

    # Request without any headers rejected (400 Bad Request on tenant, or 401/403)
    res_raw = client.get("/api/admin/codex/settings/boundaries")
    assert res_raw.status_code in (400, 401, 403)


def test_non_admin_requests_rejected(client: TestClient, db_session: Session):
    """Requests with non-admin/client role credentials must be rejected with 403 Forbidden."""
    _, _, headers = _create_non_admin_user(db_session)

    res1 = client.get("/api/admin/codex/settings/boundaries", headers=headers)
    assert res1.status_code == 403

    res2 = client.get("/api/admin/codex/projects", headers=headers)
    assert res2.status_code == 403


def test_get_codex_settings_boundaries(client: TestClient, db_session: Session):
    """GET /api/admin/codex/settings/boundaries returns 200 OK with allowed boundaries."""
    _, _, headers = _create_admin_user(db_session, suffix="boundaries")

    res = client.get("/api/admin/codex/settings/boundaries", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check boundary item structure
    boundary = data[0]
    assert "id" in boundary
    assert "path" in boundary
    assert "is_default" in boundary


def test_get_codex_projects(client: TestClient, db_session: Session):
    """GET /api/admin/codex/projects returns 200 OK with projects list."""
    _, _, headers = _create_admin_user(db_session, suffix="projects")

    res = client.get("/api/admin/codex/projects", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_get_codex_models(client: TestClient, db_session: Session):
    """GET /api/admin/codex/models returns 200 OK with registered model catalog."""
    _, _, headers = _create_admin_user(db_session, suffix="models")

    res = client.get("/api/admin/codex/models", headers=headers)
    assert res.status_code == 200
    payload = res.json()
    assert "data" in payload
    assert isinstance(payload["data"], list)
    assert len(payload["data"]) > 0

    model_ids = [m["id"] for m in payload["data"]]
    assert "gpt-4o" in model_ids


def test_get_codex_threads(client: TestClient, db_session: Session):
    """GET /api/admin/codex/threads returns 200 OK with thread list."""
    _, _, headers = _create_admin_user(db_session, suffix="threads")

    res = client.get("/api/admin/codex/threads", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_get_codex_health_unauthenticated(client: TestClient):
    """GET /api/admin/codex/health returns 200 OK without authentication."""
    res = client.get("/api/admin/codex/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data.get("version") == "1.0.0"
    assert "codex_db" in data


def test_get_codex_health_authenticated(client: TestClient, db_session: Session):
    """GET /api/admin/codex/health returns 200 OK with admin headers."""
    _, _, headers = _create_admin_user(db_session, suffix="health")
    res = client.get("/api/admin/codex/health", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_get_codex_diagnostics_deep(client: TestClient, db_session: Session):
    """GET /api/admin/codex/diagnostics/deep requires auth and returns diagnostics when authenticated."""
    # Unauthenticated rejected
    res_unauth = client.get("/api/admin/codex/diagnostics/deep")
    assert res_unauth.status_code in (401, 403)

    # Authenticated with admin user
    _, _, headers = _create_admin_user(db_session, suffix="diagdeep")
    res = client.get("/api/admin/codex/diagnostics/deep", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "subsystems" in data


def test_post_codex_projects(client: TestClient, db_session: Session):
    """POST /api/admin/codex/projects creates or updates a project."""
    _, _, headers = _create_admin_user(db_session, suffix="postproj")
    from backend.config import settings as codex_settings

    payload = {
        "name": "Mounted Audit Project",
        "repo_path": str(codex_settings.repo_root),
        "default_branch": "main",
    }
    res = client.post("/api/admin/codex/projects", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["name"] == "Mounted Audit Project"
    assert data["default_branch"] == "main"


def test_post_codex_threads(client: TestClient, db_session: Session):
    """POST /api/admin/codex/threads creates a new execution thread."""
    _, _, headers = _create_admin_user(db_session, suffix="postthread")

    payload = {
        "project_id": "default",
        "title": "Audit Thread 1",
    }
    res = client.post("/api/admin/codex/threads", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["title"] == "Audit Thread 1"
    assert data["status"] == "active"


def test_post_codex_turns_start(client: TestClient, db_session: Session):
    """POST /api/admin/codex/turns/start initializes a turn, binds worktree sandbox, and logs record."""
    _, _, headers = _create_admin_user(db_session, suffix="postturns")

    # 1. Create a thread
    thread_res = client.post(
        "/api/admin/codex/threads",
        json={"project_id": "default", "title": "Turn Execution Thread"},
        headers=headers,
    )
    assert thread_res.status_code == 200
    thread_id = thread_res.json()["id"]

    # 2. Start a turn
    turn_payload = {
        "thread_id": thread_id,
        "prompt": "Inspect codebase architecture and status",
    }
    turn_res = client.post("/api/admin/codex/turns/start", json=turn_payload, headers=headers)
    assert turn_res.status_code == 200
    data = turn_res.json()
    assert "turn_id" in data
    assert data["status"] == "active"
    assert "workspace_root" in data


def test_get_codex_settings_telemetry(client: TestClient, db_session: Session):
    """GET /api/admin/codex/settings/telemetry returns telemetry connectivity and settings."""
    _, _, headers = _create_admin_user(db_session, suffix="telemetry")

    res = client.get("/api/admin/codex/settings/telemetry", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "signoz_url" in data
    assert "otlp_endpoint" in data
    assert "enabled" in data


def test_get_codex_events_stream_and_ticket(client: TestClient, db_session: Session):
    """Mints an SSE ticket and verifies GET /api/admin/codex/events/stream connects cleanly."""
    _, _, headers = _create_admin_user(db_session, suffix="eventsstream")

    # 1. Mint single-use ticket
    ticket_res = client.post(
        "/api/admin/codex/events/ticket",
        json={"project_id": "default", "thread_id": "th_stream_test"},
        headers=headers,
    )
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["ticket"]
    assert ticket

    # 2. Connect with ticket via query parameter on stream route using streaming context manager
    with client.stream(
        "GET",
        f"/api/admin/codex/events/stream?project_id=default&thread_id=th_stream_test&sse_ticket={ticket}&max_events=1",
    ) as stream_res:
        # The endpoint accepts ticket and sets media type text/event-stream
        assert stream_res.status_code == 200
        assert stream_res.headers.get("content-type", "").startswith("text/event-stream")

    # 3. Stream without authentication is rejected
    unauth_stream = client.get("/api/admin/codex/events/stream")
    assert unauth_stream.status_code == 401


def test_get_codex_worktrees_and_governance(client: TestClient, db_session: Session):
    """Verifies worktrees and governance routes mounted under /api/admin."""
    _, _, headers = _create_admin_user(db_session, suffix="worktreesgov")
    from backend.config import settings as codex_settings

    # Worktrees listing
    wt_res = client.get(
        f"/api/admin/codex/worktrees?repo_path={codex_settings.repo_root}",
        headers=headers,
    )
    assert wt_res.status_code == 200
    assert isinstance(wt_res.json(), list)

    # Governance pending approvals
    gov_res = client.get("/api/admin/codex/governance/approvals/pending", headers=headers)
    assert gov_res.status_code == 200
    assert isinstance(gov_res.json(), list)


