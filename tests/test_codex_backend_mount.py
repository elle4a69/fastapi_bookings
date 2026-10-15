"""Tests for Codex Control Centre backend routers mounted directly into FastAPI Bookings."""

import pytest
from pathlib import Path
import uuid
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture(scope="module", autouse=True)
def _migrate_isolated_codex_database():
    """Assert root conftest migrated the isolated CCC database before import."""
    from backend.database import engine as codex_engine

    with codex_engine.connect() as connection:
        revisions = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
    assert revisions == [("004",)]
    yield
    import gc

    codex_engine.dispose()
    gc.collect()


def _create_admin_user(
    db_session: Session,
    suffix: str = "mount",
    *,
    role: str = "owner",
    is_platform_owner: bool = True,
    is_active: bool = True,
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
        is_active=is_active,
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


def test_supervisor_v2_auth_errors_are_safe_and_precede_ccc_access(
    client: TestClient,
    db_session: Session,
):
    operations = [
        ("get", "/api/admin/codex/v2/bootstrap"),
        ("get", "/api/admin/codex/v2/operations/readiness"),
        ("get", "/api/admin/codex/v2/operations/cutover-mode"),
        ("get", "/api/admin/codex/v2/projects"),
        ("post", "/api/admin/codex/v2/projects/not-valid/claim"),
    ]
    for method, path in operations:
        unauthenticated = client.request(method, path, content=b"not-json")
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["error"]["code"] == "authentication_required"
        assert unauthenticated.headers["cache-control"] == "no-store"
        assert unauthenticated.headers["x-request-id"].startswith("req_")
        assert unauthenticated.headers["x-request-id"] == unauthenticated.json()["meta"]["request_id"]

    _, _, ordinary_headers = _create_admin_user(
        db_session,
        suffix="v2-ordinary-owner",
        role="owner",
        is_platform_owner=False,
    )
    for method, path in operations:
        forbidden = client.request(method, path, headers=ordinary_headers, content=b"not-json")
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "forbidden"

    _, _, inactive_headers = _create_admin_user(
        db_session,
        suffix="v2-inactive-platform-owner",
        role="owner",
        is_platform_owner=True,
        is_active=False,
    )
    for method, path in operations:
        inactive = client.request(method, path, headers=inactive_headers, content=b"not-json")
        assert inactive.status_code == 403
        assert inactive.json()["error"]["code"] == "forbidden"


def test_supervisor_v2_claim_and_exact_replay_are_mounted_end_to_end(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from backend.config import settings as codex_settings
    from backend.database import SessionLocal as CodexSessionLocal
    from backend.models.codex import Project

    repository = tmp_path / "configured-repository"
    repository.mkdir()
    public_id = "prj_abcdef1234567890"
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_id", public_id)
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_root", str(repository))
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_name", "FastAPI Bookings")
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_default_branch", "develop")

    _, _, headers = _create_admin_user(db_session, suffix="v2-claim")
    bootstrap = client.get("/api/admin/codex/v2/bootstrap", headers=headers)
    assert bootstrap.status_code == 200
    assert bootstrap.json()["data"]["project_resolution"]["state"] == "claim_required"
    assert bootstrap.json()["data"]["capabilities"]["can_claim_project"] is True
    assert str(repository) not in bootstrap.text

    idempotency_key = str(uuid.uuid4())
    claim_headers = {
        **headers,
        "Idempotency-Key": idempotency_key,
        "If-Match": '"project-0"',
    }
    body = {
        "action": "claim_project",
        "registry_version": "0.1",
        "expected_version": 0,
        "confirmation": True,
    }
    first = client.post(
        f"/api/admin/codex/v2/projects/{public_id}/claim",
        headers=claim_headers,
        json=body,
    )
    assert first.status_code == 200
    assert first.headers["etag"] == '"project-1"'
    assert first.headers["x-request-id"] == first.json()["meta"]["request_id"]
    assert str(repository) not in first.text

    replay = client.post(
        f"/api/admin/codex/v2/projects/{public_id}/claim",
        headers=claim_headers,
        json=body,
    )
    assert replay.status_code == first.status_code
    assert replay.content == first.content
    assert replay.headers["idempotency-replayed"] == "true"
    assert replay.headers["x-request-id"] == first.headers["x-request-id"]

    with CodexSessionLocal() as codex_db:
        internal_id = codex_db.query(Project.id).filter(Project.public_id == public_id).scalar()
    guarded = client.post(
        "/api/admin/codex/projects",
        headers=headers,
        json={
            "id": internal_id,
            "name": "Attempted v1 mutation",
            "repo_path": str(repository),
            "default_branch": "other",
        },
    )
    assert guarded.status_code == 409
    assert guarded.json()["error"]["code"] == "supervisor_owned"


def test_supervisor_v2_malformed_project_id_is_rejected_before_reservation(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from backend.config import settings as codex_settings
    from backend.database import SessionLocal as CodexSessionLocal
    from backend.models.codex import IdempotencyRecord

    repository = tmp_path / "malformed-id-repository"
    repository.mkdir()
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_id", "prj_1234567890abcdef")
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_root", str(repository))
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_name", "FastAPI Bookings")
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_default_branch", "develop")
    _, _, headers = _create_admin_user(db_session, suffix="v2-malformed-id")
    with CodexSessionLocal() as codex_db:
        before = codex_db.query(IdempotencyRecord).count()
    response = client.post(
        "/api/admin/codex/v2/projects/not-valid/claim",
        headers={
            **headers,
            "Idempotency-Key": str(uuid.uuid4()),
            "If-Match": '"project-0"',
        },
        json={
            "action": "claim_project",
            "registry_version": "0.1",
            "expected_version": 0,
            "confirmation": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert "etag" not in response.headers
    assert "idempotency-replayed" not in response.headers
    with CodexSessionLocal() as codex_db:
        assert codex_db.query(IdempotencyRecord).count() == before


def test_supervisor_v2_cross_scope_exact_root_is_hidden_and_claim_returns_404(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from datetime import datetime, timezone
    from backend.config import settings as codex_settings
    from backend.database import SessionLocal as CodexSessionLocal
    from backend.models.codex import Project
    from backend.services.legacy_adoption_service import (
        load_configured_project,
        root_identity_for_path,
    )

    repository = tmp_path / "hidden-root-repository"
    repository.mkdir()
    public_id = "prj_9999999999999999"
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_id", public_id)
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_root", str(repository))
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_project_name", "FastAPI Bookings")
    monkeypatch.setattr(codex_settings, "codex_supervisor_configured_default_branch", "develop")
    configured = load_configured_project().project
    assert configured is not None
    hidden_id = f"hidden_{uuid.uuid4().hex}"
    unrelated_root = tmp_path / "hidden-unrelated-root"
    unrelated_root.mkdir()
    unrelated_identity = root_identity_for_path(unrelated_root)
    assert unrelated_identity is not None
    try:
        _, _, headers = _create_admin_user(db_session, suffix="v2-hidden-root")
        baseline_bootstrap = client.get(
            "/api/admin/codex/v2/bootstrap", headers=headers
        )
        baseline_projects = client.get("/api/admin/codex/v2/projects", headers=headers)
        assert baseline_bootstrap.status_code == 200
        assert baseline_projects.status_code == 200

        unrelated = [
            {
                "id": f"hidden-volume-api-{index:05d}",
                "name": f"Hidden API {index}",
                "repo_path": str(unrelated_root),
                "root_identity_digest": unrelated_identity[1],
                "default_branch": "develop",
                "public_id": f"prj_{index:016x}",
                "tenant_id": 1_000_000 + index,
                "owner_user_id": 2_000_000 + index,
                "scope_state": "claimed",
                "control_plane": "legacy",
                "configured_fingerprint": f"{index:064x}",
                "claimed_at": datetime.now(timezone.utc),
                "version": 1,
            }
            for index in range(10_001)
        ]
        conflict = {
            "id": hidden_id,
            "name": "Hidden Other Scope",
            "repo_path": configured.canonical_root,
            "root_identity_digest": configured.root_identity_digest,
            "default_branch": "other",
            "public_id": "prj_8888888888888888",
            "tenant_id": 987654,
            "owner_user_id": 987654,
            "scope_state": "claimed",
            "control_plane": "legacy",
            "configured_fingerprint": "d" * 64,
            "claimed_at": datetime.now(timezone.utc),
            "version": 1,
        }
        with CodexSessionLocal() as codex_db:
            codex_db.execute(Project.__table__.insert(), [*unrelated, conflict])
            codex_db.commit()

        bootstrap = client.get("/api/admin/codex/v2/bootstrap", headers=headers)
        assert bootstrap.status_code == 200
        assert bootstrap.json()["data"] == baseline_bootstrap.json()["data"]
        assert bootstrap.headers["etag"] == baseline_bootstrap.headers["etag"]
        assert bootstrap.json()["data"]["project_resolution"] == {
            "state": "claim_required",
            "reason_codes": [],
        }
        assert bootstrap.json()["data"]["capabilities"]["can_claim_project"] is True
        public_project = bootstrap.json()["data"]["project"]
        assert public_project["project_id"] == public_id
        assert public_project["state"] == "claim_required"
        assert public_project["version"] == 0
        assert public_project["claim_action"]["action"] == "claim_project"
        projects = client.get("/api/admin/codex/v2/projects", headers=headers)
        assert projects.status_code == 200
        assert projects.json()["data"] == baseline_projects.json()["data"]
        assert projects.headers["etag"] == baseline_projects.headers["etag"]
        assert projects.json()["data"]["projects"] == [public_project]

        claim_headers = {
            **headers,
            "Idempotency-Key": str(uuid.uuid4()),
            "If-Match": '"project-0"',
        }
        body = {
            "action": "claim_project",
            "registry_version": "0.1",
            "expected_version": 0,
            "confirmation": True,
        }
        denied = client.post(
            f"/api/admin/codex/v2/projects/{public_id}/claim",
            headers=claim_headers,
            json=body,
        )
        assert denied.status_code == 404
        assert denied.json()["error"]["code"] == "resource_not_found"
        replay = client.post(
            f"/api/admin/codex/v2/projects/{public_id}/claim",
            headers=claim_headers,
            json=body,
        )
        assert replay.status_code == 404
        assert replay.content == denied.content
        assert replay.headers["idempotency-replayed"] == "true"
    finally:
        with CodexSessionLocal() as codex_db:
            codex_db.query(Project).filter(Project.id == hidden_id).delete()
            codex_db.query(Project).filter(
                Project.id.like("hidden-volume-api-%")
            ).delete(synchronize_session=False)
            codex_db.commit()


def _configure_and_claim_planning_project(client, db_session, tmp_path, monkeypatch):
    from backend.config import settings as cfg
    repository = tmp_path / "planning-repository"
    repository.mkdir()
    project_id = "prj_" + uuid.uuid4().hex[:16]
    monkeypatch.setattr(cfg, "codex_supervisor_configured_project_id", project_id)
    monkeypatch.setattr(cfg, "codex_supervisor_configured_project_root", str(repository))
    monkeypatch.setattr(cfg, "codex_supervisor_configured_project_name", "Planning test")
    monkeypatch.setattr(cfg, "codex_supervisor_configured_default_branch", "main")
    _, _, headers = _create_admin_user(db_session, suffix="planning-" + uuid.uuid4().hex[:8])
    claimed = client.post(
        f"/api/admin/codex/v2/projects/{project_id}/claim",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4()), "If-Match": '"project-0"'},
        json={"action": "claim_project", "registry_version": "0.2", "expected_version": 0, "confirmation": True},
    )
    assert claimed.status_code == 200, claimed.text
    return project_id, headers


def _planning_post(client, path, headers, action, parent_etag, **payload):
    return client.post(
        path,
        headers={**headers, "Idempotency-Key": str(uuid.uuid4()), "If-Match": parent_etag},
        json={"action": action, "registry_version": "0.2", "confirmation": True, **payload},
    )


def test_supervisor_v2_planning_ledger_persists_full_inert_workflow(client, db_session, tmp_path, monkeypatch):
    project_id, headers = _configure_and_claim_planning_project(client, db_session, tmp_path, monkeypatch)
    stale = _planning_post(client, f"/api/admin/codex/v2/projects/{project_id}/missions", headers, "create_mission", '"project-0"', title="Plan", summary="Structural summary")
    assert stale.status_code == 412
    mission_response = _planning_post(client, f"/api/admin/codex/v2/projects/{project_id}/missions", headers, "create_mission", '"project-1"', title="Plan", summary="Structural summary")
    assert mission_response.status_code == 200, mission_response.text
    assert mission_response.headers["cache-control"] == "no-store"
    assert mission_response.headers["etag"].startswith('"mission-v1-')
    mission = mission_response.json()["data"]["mission"]
    work_response = _planning_post(client, f"/api/admin/codex/v2/missions/{mission['id']}/work-packages", headers, "create_work_package", '"mission-1"', title="Backend foundation", scope="Durable planning API")
    assert work_response.status_code == 200, work_response.text
    work = work_response.json()["data"]["work_package"]
    brief_response = _planning_post(client, f"/api/admin/codex/v2/work-packages/{work['id']}/briefs", headers, "create_brief", '"work_package-1"', content="Implement bounded planning interfaces", future_execution_authorization_requirement="not_required_once_requested")
    assert brief_response.status_code == 200, brief_response.text
    brief = brief_response.json()["data"]["brief"]
    assert brief["future_execution_authorization_requirement"] == "not_required_once_requested"
    assert "run" not in brief_response.text.lower()
    approved = _planning_post(client, f"/api/admin/codex/v2/briefs/{brief['id']}/approve", headers, "approve_brief", '"brief-1"')
    assert approved.status_code == 200, approved.text
    checkpoint = _planning_post(client, f"/api/admin/codex/v2/missions/{mission['id']}/context-checkpoints", headers, "record_context_checkpoint", '"mission-1"', summary="Current scope", decisions="Planning only", constraints="No execution", open_questions="None")
    assert checkpoint.status_code == 200, checkpoint.text
    scope = _planning_post(client, f"/api/admin/codex/v2/work-packages/{work['id']}/audit-scope", headers, "define_audit_scope", '"work_package-2"', criteria="API isolation", exclusions="No production actions")
    assert scope.status_code == 200, scope.text
    assert client.get(f"/api/admin/codex/v2/missions/{mission['id']}", headers=headers).json()["data"]["mission"]["id"] == mission["id"]
    assert len(client.get(f"/api/admin/codex/v2/missions/{mission['id']}/context-checkpoints", headers=headers).json()["data"]["context_checkpoints"]) == 1
    assert client.get(f"/api/admin/codex/v2/work-packages/{work['id']}/audit-scope", headers=headers).json()["data"]["audit_scope"]["id"].startswith("asc_")

    # The mounted workflow must leave behind a ledger that cannot be altered
    # by a direct SQL caller.  This proves the migration triggers, rather than
    # only route-level checks, protect the durable planning context.
    from backend.database import engine as codex_engine

    with pytest.raises(IntegrityError, match="planning_append_only"):
        with codex_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM planning_missions WHERE id=:id"), {"id": mission["id"]}
            )
    with pytest.raises(IntegrityError, match="planning_work_package_immutable"):
        with codex_engine.begin() as connection:
            connection.execute(
                text("UPDATE planning_work_packages SET created_at=CURRENT_TIMESTAMP WHERE id=:id"),
                {"id": work["id"]},
            )
    with pytest.raises(IntegrityError, match="planning_brief_immutable"):
        with codex_engine.begin() as connection:
            connection.execute(
                text("UPDATE planning_briefs SET created_at=CURRENT_TIMESTAMP WHERE id=:id"),
                {"id": brief["id"]},
            )
    with codex_engine.connect() as connection:
        internal_project_id = connection.execute(
            text("SELECT id FROM projects WHERE public_id=:id"), {"id": project_id}
        ).scalar_one()
    with pytest.raises(IntegrityError, match="planning_parent_scope"):
        with codex_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO planning_missions "
                    "(id,project_id,tenant_id,owner_user_id,title,summary,state,version,created_at) "
                    "VALUES (:id,:project_id,:tenant_id,:owner_user_id,'Forged','Forged','draft',1,CURRENT_TIMESTAMP)"
                ),
                {
                    "id": "mis_" + uuid.uuid4().hex,
                    "project_id": internal_project_id,
                    "tenant_id": 999999,
                    "owner_user_id": 999999,
                },
            )


def test_planning_approved_brief_revision_supersedes_and_replays(client, db_session, tmp_path, monkeypatch):
    project_id, headers = _configure_and_claim_planning_project(client, db_session, tmp_path, monkeypatch)
    mission = _planning_post(client, f"/api/admin/codex/v2/projects/{project_id}/missions", headers, "create_mission", '"project-1"', title="Planning", summary="Durable planning scope").json()["data"]["mission"]
    work = _planning_post(client, f"/api/admin/codex/v2/missions/{mission['id']}/work-packages", headers, "create_work_package", '"mission-1"', title="Foundation", scope="Planning persistence").json()["data"]["work_package"]
    first = _planning_post(client, f"/api/admin/codex/v2/work-packages/{work['id']}/briefs", headers, "create_brief", '"work_package-1"', content="Define safe planning records").json()["data"]["brief"]
    _planning_post(client, f"/api/admin/codex/v2/briefs/{first['id']}/approve", headers, "approve_brief", '"brief-1"')
    second = _planning_post(client, f"/api/admin/codex/v2/work-packages/{work['id']}/briefs", headers, "create_brief", '"work_package-2"', content="Refine safe planning records").json()["data"]["brief"]
    ready = client.get(f"/api/admin/codex/v2/work-packages/{work['id']}", headers=headers)
    assert ready.json()["data"]["work_package"]["state"] == "brief_ready"
    key = str(uuid.uuid4())
    request_headers = {**headers, "Idempotency-Key": key, "If-Match": '"brief-1"'}
    body = {"action":"approve_brief", "registry_version":"0.2", "confirmation":True}
    approved = client.post(f"/api/admin/codex/v2/briefs/{second['id']}/approve", headers=request_headers, json=body)
    replay = client.post(f"/api/admin/codex/v2/briefs/{second['id']}/approve", headers=request_headers, json=body)
    assert approved.status_code == replay.status_code == 200
    assert replay.content == approved.content and replay.headers["idempotency-replayed"] == "true"
    assert client.get(f"/api/admin/codex/v2/briefs/{first['id']}", headers=headers).json()["data"]["brief"]["state"] == "superseded"
    assert client.get(f"/api/admin/codex/v2/work-packages/{work['id']}", headers=headers).json()["data"]["work_package"]["state"] == "brief_approved"
    stale_key = str(uuid.uuid4())
    stale_headers = {**headers, "Idempotency-Key": stale_key, "If-Match": '"brief-1"'}
    stale = client.post(f"/api/admin/codex/v2/briefs/{second['id']}/approve", headers=stale_headers, json=body)
    stale_replay = client.post(f"/api/admin/codex/v2/briefs/{second['id']}/approve", headers=stale_headers, json=body)
    assert stale.status_code == stale_replay.status_code == 412
    assert stale_replay.content == stale.content
    assert stale_replay.headers["idempotency-replayed"] == "true"
    from backend.database import engine as codex_engine
    with codex_engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM supervisor_events WHERE action_code='approve_brief'")).scalar_one() == 2
        assert connection.execute(text("SELECT status FROM idempotency_records WHERE action_code='approve_brief' AND idempotency_key=:key"), {"key": stale_key}).scalar_one() == "failed"


def test_supervisor_v2_planning_idempotency_cross_scope_and_openapi(client, db_session, tmp_path, monkeypatch):
    project_id, headers = _configure_and_claim_planning_project(client, db_session, tmp_path, monkeypatch)
    key = str(uuid.uuid4())
    request_headers = {**headers, "Idempotency-Key": key, "If-Match": '"project-1"'}
    body = {"action": "create_mission", "registry_version": "0.2", "confirmation": True, "title": "Repeatable", "summary": "One durable mission"}
    first = client.post(f"/api/admin/codex/v2/projects/{project_id}/missions", headers=request_headers, json=body)
    replay = client.post(f"/api/admin/codex/v2/projects/{project_id}/missions", headers=request_headers, json=body)
    assert first.status_code == replay.status_code == 200
    assert first.content == replay.content and replay.headers["idempotency-replayed"] == "true"
    changed = client.post(f"/api/admin/codex/v2/projects/{project_id}/missions", headers=request_headers, json={**body, "summary": "Different"})
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "idempotency_conflict"
    assert len(client.get(f"/api/admin/codex/v2/projects/{project_id}/missions", headers=headers).json()["data"]["missions"]) == 1
    _, _, other_headers = _create_admin_user(db_session, suffix="planning-other-" + uuid.uuid4().hex[:8])
    mission_id = first.json()["data"]["mission"]["id"]
    hidden = client.get(f"/api/admin/codex/v2/missions/{mission_id}", headers=other_headers)
    assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "resource_not_found"
    unauthenticated = client.post(f"/api/admin/codex/v2/projects/{project_id}/missions", content=b"not-json")
    assert unauthenticated.status_code == 401
    _, _, ordinary = _create_admin_user(db_session, suffix="planning-no-platform-" + uuid.uuid4().hex[:8], is_platform_owner=False)
    assert client.get(f"/api/admin/codex/v2/projects/{project_id}/missions", headers=ordinary).status_code == 403
    operation = client.get("/openapi.json").json()["paths"]["/api/admin/codex/v2/projects/{project_id}/missions"]["post"]
    assert operation["x-action-code"] == "create_mission"
    assert operation["x-action-registry-version"] == "0.2"


def test_planning_deterministic_failure_is_terminal_and_atomic(client, db_session, tmp_path, monkeypatch):
    """A deterministic event-write failure must not strand a planning side effect."""
    from backend.middleware.v2_errors import SupervisorHTTPError
    from backend.models.codex import IdempotencyRecord, PlanningMission, SupervisorEvent
    from backend import database as codex_database
    from backend.routers import v2_supervisor

    project_id, headers = _configure_and_claim_planning_project(
        client, db_session, tmp_path, monkeypatch
    )
    key = str(uuid.uuid4())
    request_headers = {
        **headers,
        "Idempotency-Key": key,
        "If-Match": '"project-1"',
    }
    body = {
        "action": "create_mission",
        "registry_version": "0.2",
        "confirmation": True,
        "title": "Atomic failure",
        "summary": "No partial planning ledger write",
    }

    def fail_event(*_args, **_kwargs):
        raise SupervisorHTTPError(409, "revision_conflict")

    monkeypatch.setattr(v2_supervisor, "append_planning_event", fail_event)
    first = client.post(
        f"/api/admin/codex/v2/projects/{project_id}/missions",
        headers=request_headers,
        json=body,
    )
    assert first.status_code == 409
    assert first.json()["error"]["code"] == "revision_conflict"
    replay = client.post(
        f"/api/admin/codex/v2/projects/{project_id}/missions",
        headers=request_headers,
        json=body,
    )
    assert replay.status_code == 409
    assert replay.content == first.content
    assert replay.headers["idempotency-replayed"] == "true"
    with codex_database.engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM planning_missions m "
                "JOIN projects p ON p.id=m.project_id WHERE p.public_id=:project_id"
            ),
            {"project_id": project_id},
        ).scalar_one() == 0
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM supervisor_events "
                "WHERE action_code='create_mission' AND project_public_id=:project_id"
            ),
            {"project_id": project_id},
        ).scalar_one() == 0
        status = connection.execute(
            text(
                "SELECT status FROM idempotency_records "
                "WHERE action_code='create_mission' AND idempotency_key=:key"
            ),
            {"key": key},
        ).scalar_one()
    assert status == "failed"


