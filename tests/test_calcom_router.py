"""Tests for Cal.com integration router."""

from datetime import datetime, timezone
import pytest
from fastapi import status

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture
def calcom_test_env(db_session):
    """Creates a test tenant and admin user with auth headers."""
    tenant = Tenant(
        name="Calcom Testing Studio",
        subdomain="calcom-studio",
        email="info@calcomstudio.com",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        login="calcom_admin",
        password_hash="fake_hash",
        role="admin",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }
    return {
        "tenant": tenant,
        "user": user,
        "headers": headers,
    }


def test_calcom_status_endpoint(client, calcom_test_env):
    """GET /api/admin/integrations/calcom/status should return status info."""
    headers = calcom_test_env["headers"]
    response = client.get("/api/admin/integrations/calcom/status", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["ok"] is True
    assert "configured" in body["data"]
    assert "base_url" in body["data"]


def test_calcom_embed_config_endpoint(client, calcom_test_env):
    """GET /api/admin/integrations/calcom/embed generates embed parameters."""
    headers = calcom_test_env["headers"]
    response = client.get(
        "/api/admin/integrations/calcom/embed?cal_link=jane/consultation&layout=month_view&theme=light",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["cal_link"] == "jane/consultation"
    assert "https://cal.com/jane/consultation?embed=true" in data["iframe_url"]
    assert "Cal(" in data["js_snippet"]


def test_calcom_event_types_endpoint(client, calcom_test_env):
    """GET /api/admin/integrations/calcom/event-types returns list gracefully even with mock/unconfigured key."""
    headers = calcom_test_env["headers"]
    response = client.get("/api/admin/integrations/calcom/event-types", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["ok"] is True
    assert isinstance(body["data"], list)
