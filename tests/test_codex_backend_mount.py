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

