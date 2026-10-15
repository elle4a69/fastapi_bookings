"""Tests for Codex Control Centre backend routers mounted directly into FastAPI Bookings."""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User


def _create_admin_user(
    db_session: Session,
    suffix: str = "mount",
    *,
    role: str = "owner",
    is_platform_owner: bool = True,
) -> tuple[Tenant, User, dict[str, str]]:
    tenant = Tenant(name=f"Codex Admin Tenant {suffix}", subdomain=f"codex-admin-{suffix}")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        login=f"admin-{suffix}",
        password_hash="test-secret-hash",
        role=role,
        is_platform_owner=is_platform_owner,
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


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/admin/codex/projects", None),
        ("get", "/api/admin/codex/diagnostics/deep", None),
        ("get", "/api/admin/codex/health", None),
        (
            "post",
            "/api/admin/codex/events/ticket",
            {"project_id": "default", "thread_id": "ordinary-admin"},
        ),
        (
            "post",
            "/api/admin/codex/events/publish",
            {"project_id": "default", "thread_id": "ordinary-admin", "type": "test"},
        ),
    ],
)
@pytest.mark.parametrize("role", ["owner", "admin", "manager"])
def test_codex_routes_reject_non_platform_owner(
    client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    payload: dict | None,
    role: str,
):
    """Ordinary tenant administrators cannot operate the global cockpit."""
    _, _, headers = _create_admin_user(
        db_session,
        suffix=f"ordinary-{role}-{method}-{path.rsplit('/', 1)[-1]}",
        role=role,
        is_platform_owner=False,
    )
    response = client.request(method.upper(), path, json=payload, headers=headers)
    assert response.status_code == 403


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
    assert model_ids == [
        "gpt-6.1-sol",
        "gpt-6-astra",
        "gpt-6-sol",
        "gpt-6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    ]
    assert all(not model_id.startswith("gpt-4") for model_id in model_ids)
    assert [m["id"] for m in payload["data"] if m["isDefault"]] == ["gpt-6.1-sol"]
    assert payload["data"][0]["supportedReasoningEfforts"][-1]["reasoningEffort"] == "ultra"

    legacy_res = client.get("/api/admin/codex/models/gpt-4o", headers=headers)
    assert legacy_res.status_code == 404


def test_get_codex_plugins_is_admin_scoped_and_uses_mounted_app_server_route(
    client: TestClient,
    db_session: Session,
):
    unauthenticated = client.get("/api/admin/codex/plugins")
    assert unauthenticated.status_code in (400, 401, 403)

    _, _, headers = _create_admin_user(db_session, suffix="plugins")
    worker = AsyncMock()
    worker.running = True
    worker.send_request.return_value = {
        "marketplaces": [],
        "marketplaceLoadErrors": [],
        "featuredPluginIds": [],
    }
    with patch("backend.routers.plugins.worker_manager.get_worker", AsyncMock(return_value=worker)):
        response = client.get("/api/admin/codex/plugins", headers=headers)

    assert response.status_code == 200
    assert response.json()["plugins"] == []


def test_get_codex_skills_is_admin_scoped_and_uses_mounted_rag_route(
    client: TestClient,
    db_session: Session,
):
    unauthenticated = client.get("/api/admin/codex/skills/stats")
    assert unauthenticated.status_code in (400, 401, 403)

    _, _, headers = _create_admin_user(db_session, suffix="skills")
    with patch(
        "backend.routers.skills.skills_context_service.stats",
        AsyncMock(return_value={"totalSkills": 1692, "indexedCount": 1692, "status": "available"}),
    ):
        response = client.get("/api/admin/codex/skills/stats", headers=headers)

    assert response.status_code == 200
    assert response.json()["indexedCount"] == 1692


def test_get_codex_threads(client: TestClient, db_session: Session):
    """GET /api/admin/codex/threads returns 200 OK with thread list."""
    _, _, headers = _create_admin_user(db_session, suffix="threads")

    res = client.get("/api/admin/codex/threads", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_get_codex_health_unauthenticated(client: TestClient):
    """Mounted diagnostic health is not exposed without platform-owner auth."""
    res = client.get("/api/admin/codex/health")
    assert res.status_code in (400, 401, 403)


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
    assert res_unauth.status_code in (400, 401, 403)

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

    # 3. The same ticket is atomically consumed and cannot be replayed.
    replay = client.get(
        f"/api/admin/codex/events/stream?project_id=default&thread_id=th_stream_test&sse_ticket={ticket}&max_events=1"
    )
    assert replay.status_code == 401

    # 4. Stream without authentication is rejected
    unauth_stream = client.get("/api/admin/codex/events/stream")
    assert unauth_stream.status_code == 401


@pytest.mark.parametrize(
    "credential",
    [
        {"headers": {"Authorization": "Bearer local_secret"}},
        {"headers": {"X-Token": "local_secret"}},
        {"params": {"token": "local_secret"}},
    ],
)
def test_mounted_codex_rejects_default_control_secret(
    client: TestClient,
    credential: dict,
):
    """The repository default standalone secret has no mounted authority."""
    response = client.post(
        "/api/admin/codex/events/ticket",
        json={"project_id": "default", "thread_id": "default-secret"},
        **credential,
    )
    assert response.status_code == 401


def test_mounted_event_stream_rejects_bearer_and_query_tokens(
    client: TestClient,
    db_session: Session,
):
    """Only a one-use ticket can open the mounted Control Centre stream."""
    tenant, _, headers = _create_admin_user(db_session, suffix="stream-no-bearer")
    token = headers["X-Token"]

    header_response = client.get(
        "/api/admin/codex/events/stream?project_id=default&thread_id=no-bearer",
        headers={"X-Tenant": tenant.subdomain, "X-Token": token},
    )
    query_response = client.get(
        f"/api/admin/codex/events/stream?project_id=default&thread_id=no-query&token={token}"
    )

    assert header_response.status_code == 401
    assert query_response.status_code == 401


def test_codex_event_ticket_accepts_tenant_scoped_local_auth_bypass(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """The mounted event ticket route shares the native local admin boundary."""
    from app.core.config import settings as app_settings

    tenant, _, _ = _create_admin_user(db_session, suffix="local-bypass-events")
    monkeypatch.setattr(app_settings, "LOCAL_AUTH_BYPASS", True)

    response = client.post(
        "/api/admin/codex/events/ticket",
        json={"project_id": "default", "thread_id": "th_local_bypass"},
        headers={
            "X-Tenant": tenant.subdomain,
            "X-Token": "local-development-bypass",
        },
    )

    assert response.status_code == 200
    assert response.json()["ticket"]


def test_codex_event_ticket_rejects_local_auth_bypass_when_disabled(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    """The development credential remains invalid when its explicit gate is off."""
    from app.core.config import settings as app_settings

    tenant, _, _ = _create_admin_user(db_session, suffix="disabled-local-bypass-events")
    monkeypatch.setattr(app_settings, "LOCAL_AUTH_BYPASS", False)

    response = client.post(
        "/api/admin/codex/events/ticket",
        json={"project_id": "default", "thread_id": "th_disabled_local_bypass"},
        headers={
            "X-Tenant": tenant.subdomain,
            "X-Token": "local-development-bypass",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_codex_local_auth_bypass_is_rejected_outside_native_app(
    monkeypatch: pytest.MonkeyPatch,
):
    """The standalone control-centre cannot inherit the native bypass."""
    from starlette.requests import Request

    from app.core.config import settings as app_settings
    from backend.middleware.auth import _verify_local_development_bypass

    monkeypatch.setattr(app_settings, "LOCAL_AUTH_BYPASS", True)
    standalone_app = FastAPI()
    request = Request(
        {
            "type": "http",
            "app": standalone_app,
            "method": "POST",
            "path": "/codex/events/ticket",
            "headers": [],
            "query_string": b"",
            "server": ("127.0.0.1", 4500),
            "client": ("127.0.0.1", 50000),
            "scheme": "http",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await _verify_local_development_bypass(request, "local-development-bypass")

    assert exc_info.value.status_code == 401


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


