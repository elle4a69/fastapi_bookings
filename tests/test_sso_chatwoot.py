"""Tests for Google OIDC SSO and Chatwoot Platform API integration."""
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import create_access_token, decode_access_token


def test_admin_login_embeds_tenant_id_in_jwt(client: TestClient, db_session: Session):
    """Verify that minted JWT access tokens contain tenant_id claim."""
    tenant = Tenant(name="SSO Tenant Alpha", subdomain="sso-alpha")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        login="admin_alpha",
        password_hash="$2b$12$e80yqXyE1y4G5U.eA9lFDuC92mJv88k8y.fU6m5B58eH9lFDuC92m",  # fake hash
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    # Use real verify_password mock or plaintext password hash
    from app.core.security import get_password_hash
    user.password_hash = get_password_hash("SecretPassword123!")
    db_session.add(user)
    db_session.commit()

    resp = client.post(
        "/api/admin/auth",
        json={"company": "sso-alpha", "login": "admin_alpha", "password": "SecretPassword123!"},
        headers={"X-Tenant": "sso-alpha"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    payload = decode_access_token(token)
    assert payload is not None
    assert payload.get("tenant_id") == tenant.id
    assert payload.get("sub") == str(user.id)


def test_cross_tenant_token_rejected_by_deps(client: TestClient, db_session: Session):
    """Verify that a token minted for Tenant 1 cannot authenticate against Tenant 2."""
    t1 = Tenant(name="Tenant 1", subdomain="t1-sec")
    t2 = Tenant(name="Tenant 2", subdomain="t2-sec")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    u1 = User(
        tenant_id=t1.id,
        login="admin1",
        password_hash="fake",
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    u2 = User(
        tenant_id=t2.id,
        login="admin2",
        password_hash="fake",
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([u1, u2])
    db_session.commit()

    # Mint token with tenant_id = t1.id
    token_t1 = create_access_token({
        "sub": str(u2.id),  # even if user ID exists
        "role": "owner",
        "tenant_id": t1.id,
    })

    # Request t2 using t1 token
    resp = client.get("/api/admin/system/diagnostics", headers={"X-Tenant": "t2-sec", "X-Token": token_t1})
    assert resp.status_code == 401
    assert "Token not valid for active tenant" in resp.text


def test_google_login_invalid_token_returns_401(client: TestClient, db_session: Session):
    """Verify that invalid Google tokens are rejected with 401 Unauthorized."""
    t = Tenant(name="Google Tenant", subdomain="google-t")
    db_session.add(t)
    db_session.commit()

    resp = client.post(
        "/api/admin/auth/google",
        json={"id_token": "invalid.mock.token"},
        headers={"X-Tenant": "google-t"},
    )
    assert resp.status_code == 401
    assert "Invalid Google ID token" in resp.text


def test_google_login_provisions_user_and_session(client: TestClient, db_session: Session):
    """Verify Google OIDC login creates user and returns valid token with tenant_id."""
    t = Tenant(name="Google Provision Tenant", subdomain="google-prov")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    mock_claims = {
        "sub": "google-oauth2|987654321",
        "email": "dr.smith@example.com",
        "name": "Dr. Sarah Smith",
        "given_name": "Sarah",
        "family_name": "Smith",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
        "iss": "https://accounts.google.com",
    }

    with patch("app.services.auth.google_oidc.id_token.verify_oauth2_token", return_value=mock_claims):
        resp = client.post(
            "/api/admin/auth/google",
            json={"id_token": "valid.mock.token"},
            headers={"X-Tenant": "google-prov"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "access_token" in data
        assert data["user"]["email"] == "dr.smith@example.com"
        assert data["user"]["role"] == "owner"

        # Verify DB object
        user = db_session.query(User).filter(User.tenant_id == t.id, User.email == "dr.smith@example.com").first()
        assert user is not None
        assert user.google_sub == "google-oauth2|987654321"
        assert user.first_name == "Sarah"
        assert user.last_name == "Smith"


def test_google_login_with_chatwoot_sso_link(client: TestClient, db_session: Session):
    """Verify that when tenant has chatwoot_account_id, chatwoot_sso_url is returned."""
    t = Tenant(name="Chatwoot SSO Tenant", subdomain="cw-sso", chatwoot_account_id=99)
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    mock_claims = {
        "sub": "google-oauth2|123456789",
        "email": "agent@example.com",
        "name": "Agent Cooper",
        "iss": "https://accounts.google.com",
    }

    sso_link = "https://chatwoot.example.com/app/login?email=agent%40example.com&sso_auth_token=abcdef123456"

    with patch("app.services.auth.google_oidc.id_token.verify_oauth2_token", return_value=mock_claims), \
         patch("app.services.auth.chatwoot_sso.sync_user_to_chatwoot_platform", new_callable=AsyncMock, return_value=42), \
         patch("app.services.auth.chatwoot_sso.generate_chatwoot_sso_url", new_callable=AsyncMock, return_value=sso_link):

        resp = client.post(
            "/api/admin/auth/google",
            json={"id_token": "valid.mock.token"},
            headers={"X-Tenant": "cw-sso"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["chatwoot_sso_url"] == sso_link
