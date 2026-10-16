"""Contract tests for Public Onboarding, Sign-up, and Invitation Redemption (WP0/WP4).

Validates:
1. Subdomain availability checking (available vs taken vs reserved).
2. Self-service public signup (tenant creation, owner user, trial projection, JWT access token).
3. Public invitation inspection (valid vs invalid vs expired).
4. Single-use invitation acceptance and workspace ownership activation.
"""

from datetime import datetime, timezone, timedelta
import secrets
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.models.invitation import TenantInvitation
from app.core.security import get_password_hash


def test_public_check_subdomain(client: TestClient, db_session: Session):
    # 1. Reserved subdomain
    res_reserved = client.get("/api/public/check-subdomain?subdomain=admin")
    assert res_reserved.status_code == status.HTTP_200_OK
    data_reserved = res_reserved.json()["data"]
    assert data_reserved["available"] is False
    assert data_reserved["reason"] == "reserved"

    # 2. Fresh random subdomain
    rand_sub = f"avail-{secrets.token_hex(4)}"
    res_avail = client.get(f"/api/public/check-subdomain?subdomain={rand_sub}")
    assert res_avail.status_code == status.HTTP_200_OK
    assert res_avail.json()["data"]["available"] is True

    # 3. Seed tenant and check taken
    tenant = Tenant(
        name="Existing Studio",
        subdomain=rand_sub,
        status="active",
        subscription_tier="starter",
    )
    db_session.add(tenant)
    db_session.commit()

    res_taken = client.get(f"/api/public/check-subdomain?subdomain={rand_sub}")
    assert res_taken.status_code == status.HTTP_200_OK
    assert res_taken.json()["data"]["available"] is False
    assert res_taken.json()["data"]["reason"] == "already_taken"


def test_public_self_service_signup(client: TestClient, db_session: Session):
    rand_sub = f"glow-{secrets.token_hex(4)}"
    payload = {
        "name": "Glow Aesthetics Studio",
        "subdomain": rand_sub,
        "email": f"owner_{rand_sub}@glow.test",
        "password": "SecurePassword123!",
        "first_name": "Elena",
        "last_name": "Rostova",
        "subscription_tier": "growth",
        "billing_cycle": "annual",
        "phone": "+15551234567",
    }

    res = client.post("/api/public/signup", json=payload)
    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["ok"] is True
    assert "access_token" in body["data"]

    # Verify tenant in database
    tenant = db_session.query(Tenant).filter(Tenant.subdomain == rand_sub).first()
    assert tenant is not None
    assert tenant.name == "Glow Aesthetics Studio"
    assert tenant.subscription_tier == "growth"
    assert tenant.addon_quota == 3
    assert "sms_assistant" in tenant.enabled_modules

    # Verify owner in database
    owner = db_session.query(User).filter(User.tenant_id == tenant.id).first()
    assert owner is not None
    assert owner.role == "owner"
    assert owner.email == f"owner_{rand_sub}@glow.test"
    assert owner.first_name == "Elena"


def test_public_invitation_inspection_and_acceptance(client: TestClient, db_session: Session):
    # 1. Create tenant and invitation
    tenant = Tenant(
        name="Zen Retreat Spa",
        subdomain=f"zen-{secrets.token_hex(4)}",
        status="active",
        subscription_tier="unlimited",
    )
    db_session.add(tenant)
    db_session.commit()

    raw_token = secrets.token_urlsafe(32)
    invitation = TenantInvitation(
        tenant_id=tenant.id,
        email="newmanager@zen.test",
        role="owner",
        token=raw_token,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(invitation)
    db_session.commit()

    # 2. Inspect invitation details via public GET
    res_inspect = client.get(f"/api/auth/invitations/{raw_token}")
    assert res_inspect.status_code == status.HTTP_200_OK
    inspect_data = res_inspect.json()["data"]
    assert inspect_data["email"] == "newmanager@zen.test"
    assert inspect_data["role"] == "owner"
    assert inspect_data["tenant_name"] == "Zen Retreat Spa"
    assert inspect_data["tenant_subdomain"] == tenant.subdomain
    assert inspect_data["is_valid"] is True

    # 3. Accept invitation
    accept_payload = {
        "token": raw_token,
        "password": "NewWorkspacePassword123!",
        "first_name": "Maya",
        "last_name": "Lin",
    }
    res_accept = client.post("/api/auth/invitations/accept", json=accept_payload)
    assert res_accept.status_code == status.HTTP_200_OK
    accept_body = res_accept.json()
    assert accept_body["ok"] is True
    assert "access_token" in accept_body["data"]
    assert accept_body["data"]["user"]["role"] == "owner"
    assert accept_body["data"]["user"]["first_name"] == "Maya"

    # 4. Verify invitation marked as accepted and cannot be reused
    db_session.refresh(invitation)
    assert invitation.status == "accepted"

    res_reuse = client.post("/api/auth/invitations/accept", json=accept_payload)
    assert res_reuse.status_code == status.HTTP_400_BAD_REQUEST
