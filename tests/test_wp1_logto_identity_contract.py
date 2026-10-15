"""Comprehensive contract tests for WP1: Logto Foundation.

Validates:
1. RS256 signature validation and organization claim extraction.
2. User authenticating through Logto accesses only linked internal tenants.
3. User with organization token cannot access unlinked or foreign tenants (403 Forbidden).
4. Revoked / deactivated user membership blocks API access immediately (401/403).
5. Uninvited external logins are rejected with 403 Forbidden (preventing auto-provisioning).
6. Tenant invitation redemption and external identity linking (POST /api/identity/exchange).
7. GET /api/identity/me returns correct identity mapping and organization memberships.
8. GET /api/identity/organizations lists only accessible tenant organizations.
9. Outbox tenant provisioning and organization linking are retry-safe and idempotent.
10. Privacy and security: No raw tokens or secrets leak into exception messages or logs.
"""

from datetime import datetime, timezone, timedelta
import json
import uuid
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt

from app.core.security import create_access_token, get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.models.invitation import TenantInvitation
from app.models.external_identity import (
    ExternalIdentityLink,
    ExternalOrganizationLink,
    IdentityOutboxEvent,
)
from app.services.identity import (
    logto_validator,
    LogtoValidationError,
    identity_service,
    IdentityProvisioningError,
    LogtoClient,
)
from app.api.deps import get_current_user, get_current_platform_owner


# ---------------------------------------------------------------------------
# Test RSA Key Infrastructure (In-Memory, strictly no outbound network)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate in-memory RSA keypair for cryptographic token testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv_pem, pub_pem


@pytest.fixture(autouse=True)
def setup_logto_test_keys(rsa_keypair):
    """Register the RSA public key before tests and clean up afterward."""
    _, pub_pem = rsa_keypair
    logto_validator.clear_test_keys()
    logto_validator.register_test_key("test-key-1", pub_pem)
    yield
    logto_validator.clear_test_keys()


def _make_logto_token(
    priv_pem: str,
    sub: str,
    org_id: str | None = None,
    email: str | None = None,
    kid: str = "test-key-1",
    expires_in_seconds: int = 3600,
    issuer: str | None = None,
    aud: str | None = None,
) -> str:
    """Helper to mint a signed RS256 token matching Logto structure."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    if org_id:
        payload["org_id"] = org_id
        payload["urn:logto:organization:id"] = org_id
    if email:
        payload["email"] = email
    if issuer:
        payload["iss"] = issuer
    if aud:
        payload["aud"] = aud

    headers = {"kid": kid, "alg": "RS256"}
    return jwt.encode(payload, priv_pem, algorithm="RS256", headers=headers)


# ---------------------------------------------------------------------------
# Test Helpers: Tenant and User Seeding
# ---------------------------------------------------------------------------

def _seed_tenant(db_session: Session, slug: str) -> Tenant:
    tenant = Tenant(
        name=f"Clinic {slug.upper()}",
        subdomain=f"clinic-{slug.lower()}",
        subscription_tier="starter",
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_user(db_session: Session, tenant_id: int, login: str, role: str = "owner") -> User:
    user = User(
        tenant_id=tenant_id,
        login=login,
        email=f"{login}@example.com",
        password_hash=get_password_hash("Password123!"),
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# 1. Cryptographic Signature Validation & Claim Extraction
# ---------------------------------------------------------------------------

def test_signature_validation_and_claims_extraction(rsa_keypair):
    """Validates RS256 signature, expiry, and claim normalization."""
    priv_pem, _ = rsa_keypair
    token = _make_logto_token(
        priv_pem,
        sub="logto_sub_999",
        org_id="org_alpha_123",
        email="doctor@alpha.test",
    )

    claims = logto_validator.validate_token(token, verify_aud=False)
    assert claims["sub"] == "logto_sub_999"
    assert claims["normalized_org_id"] == "org_alpha_123"
    assert claims["email"] == "doctor@alpha.test"


def test_expired_token_rejected(rsa_keypair):
    """Expired Logto tokens must be rejected with TOKEN_EXPIRED."""
    priv_pem, _ = rsa_keypair
    expired_token = _make_logto_token(
        priv_pem,
        sub="logto_sub_expired",
        expires_in_seconds=-60,
    )

    with pytest.raises(LogtoValidationError) as exc:
        logto_validator.validate_token(expired_token, verify_aud=False)
    assert exc.value.code == "TOKEN_EXPIRED"


def test_tampered_token_signature_rejected(rsa_keypair):
    """Tokens signed with unknown key or tampered bytes must fail signature check."""
    # Generate another rogue private key
    rogue_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue_pem = rogue_priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")

    rogue_token = _make_logto_token(rogue_pem, sub="rogue_user", kid="test-key-1")
    with pytest.raises(LogtoValidationError) as exc:
        logto_validator.validate_token(rogue_token, verify_aud=False)
    assert exc.value.code == "INVALID_SIGNATURE"


# ---------------------------------------------------------------------------
# 2. Multi-Tenant Access & Boundary Enforcement via Logto Tokens
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logto_user_accesses_linked_tenant(client: TestClient, db_session: Session, rsa_keypair):
    """User authenticating with Logto token accesses their linked internal tenant."""
    priv_pem, _ = rsa_keypair
    tenant = _seed_tenant(db_session, "linked1")
    user = _seed_user(db_session, tenant.id, "linked_doc1")

    # Link identity
    identity_service.link_identity(db_session, "logto", "sub_doc1", user.id)
    # Link organization
    identity_service.link_organization(db_session, "logto", "org_doc1", tenant.id)

    token = _make_logto_token(priv_pem, sub="sub_doc1", org_id="org_doc1")

    # Access tenant-scoped dependency get_current_user
    resolved_user = await get_current_user(
        authorization=f"Bearer {token}",
        tenant=tenant,
        db=db_session,
    )
    assert resolved_user.id == user.id
    assert resolved_user.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_logto_user_cannot_switch_to_unlinked_tenant(db_session: Session, rsa_keypair):
    """User presenting token for org A cannot access tenant B (403 Forbidden)."""
    priv_pem, _ = rsa_keypair
    tenant_a = _seed_tenant(db_session, "tenant-a")
    tenant_b = _seed_tenant(db_session, "tenant-b")
    user_a = _seed_user(db_session, tenant_a.id, "usera")

    identity_service.link_identity(db_session, "logto", "sub_usera", user_a.id)
    identity_service.link_organization(db_session, "logto", "org_a", tenant_a.id)
    identity_service.link_organization(db_session, "logto", "org_b", tenant_b.id)

    # Token points to org_a
    token_org_a = _make_logto_token(priv_pem, sub="sub_usera", org_id="org_a")

    # Trying to access tenant_b with token for org_a -> 403 Forbidden
    with pytest.raises(Exception) as exc_info:
        await get_current_user(
            authorization=f"Bearer {token_org_a}",
            tenant=tenant_b,
            db=db_session,
        )
    assert exc_info.value.status_code == 403
    assert "match active tenant" in exc_info.value.detail or "User not found in this tenant" in exc_info.value.detail


@pytest.mark.asyncio
async def test_revoked_or_deactivated_membership_blocks_immediately(db_session: Session, rsa_keypair):
    """Deactivating a user record immediately causes 401 Unauthorized upon next request."""
    priv_pem, _ = rsa_keypair
    tenant = _seed_tenant(db_session, "deact")
    user = _seed_user(db_session, tenant.id, "deact_user")
    identity_service.link_identity(db_session, "logto", "sub_deact", user.id)

    token = _make_logto_token(priv_pem, sub="sub_deact")

    # Deactivate user
    user.is_active = False
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        await get_current_user(
            authorization=f"Bearer {token}",
            tenant=tenant,
            db=db_session,
        )
    assert exc_info.value.status_code == 401
    assert "deactivated" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# 3. Invitation Acceptance & Token Exchange Flow
# ---------------------------------------------------------------------------

def test_token_exchange_with_valid_invitation(client: TestClient, db_session: Session, rsa_keypair):
    """POST /api/identity/exchange redeems an invitation and links the Logto subject."""
    priv_pem, _ = rsa_keypair
    tenant = _seed_tenant(db_session, "invitee")

    # Create invitation
    invitation = TenantInvitation(
        tenant_id=tenant.id,
        email="new_owner@clinic.test",
        role="owner",
        token="inv_secret_token_12345",
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(invitation)
    db_session.commit()

    logto_token = _make_logto_token(
        priv_pem,
        sub="logto_sub_newbie",
        email="new_owner@clinic.test",
    )

    resp = client.post(
        "/api/identity/exchange",
        json={
            "token": logto_token,
            "invitation_token": "inv_secret_token_12345",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["external_subject_id"] == "logto_sub_newbie"
    assert data["tenant_id"] == tenant.id
    assert "access_token" in data

    # Verify invitation state updated
    db_session.refresh(invitation)
    assert invitation.status == "accepted"
    assert invitation.accepted_at is not None

    # Verify link exists in DB
    link = db_session.query(ExternalIdentityLink).filter_by(external_subject_id="logto_sub_newbie").first()
    assert link is not None
    assert link.user_id == data["user_id"]


def test_uninvited_external_login_rejected_with_403(client: TestClient, db_session: Session, rsa_keypair):
    """Uninvited external logins without existing link are rejected (no auto-provisioning)."""
    priv_pem, _ = rsa_keypair
    token = _make_logto_token(priv_pem, sub="uninvited_stranger_123")

    resp = client.post("/api/identity/exchange", json={"token": token})
    assert resp.status_code == 403
    assert "invitation" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Identity Me & Organization Directory Endpoints
# ---------------------------------------------------------------------------

def test_identity_me_and_organizations_endpoints(client: TestClient, db_session: Session, rsa_keypair):
    """GET /api/identity/me and GET /api/identity/organizations return memberships."""
    priv_pem, _ = rsa_keypair
    tenant = _seed_tenant(db_session, "medirun")
    user = _seed_user(db_session, tenant.id, "medirun_owner")

    identity_service.link_identity(db_session, "logto", "sub_medirun", user.id)
    identity_service.link_organization(db_session, "logto", "org_medirun_external", tenant.id)

    token = _make_logto_token(priv_pem, sub="sub_medirun")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. /api/identity/me
    resp_me = client.get("/api/identity/me", headers=headers)
    assert resp_me.status_code == 200, resp_me.text
    me_data = resp_me.json()
    assert me_data["user_id"] == user.id
    assert me_data["external_subject_id"] == "sub_medirun"
    assert me_data["provider"] == "logto"
    assert len(me_data["organizations"]) == 1
    assert me_data["organizations"][0]["tenant_id"] == tenant.id
    assert me_data["organizations"][0]["external_organization_id"] == "org_medirun_external"

    # 2. /api/identity/organizations
    resp_orgs = client.get("/api/identity/organizations", headers=headers)
    assert resp_orgs.status_code == 200, resp_orgs.text
    orgs_data = resp_orgs.json()
    assert orgs_data["ok"] is True
    assert len(orgs_data["data"]) == 1
    assert orgs_data["data"][0]["tenant_subdomain"] == tenant.subdomain


# ---------------------------------------------------------------------------
# 5. Outbox Organization Provisioning & Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_organization_provisioning_idempotency(db_session: Session):
    """Enqueueing tenant provisioning and processing outbox is safe and idempotent."""
    tenant = _seed_tenant(db_session, "outbox-test")

    # 1. Enqueue provisioning
    ev1 = identity_service.enqueue_organization_provisioning(db_session, tenant)
    assert ev1.status == "PENDING"

    # 2. Enqueue again -> must return existing event without duplicate key error
    ev2 = identity_service.enqueue_organization_provisioning(db_session, tenant)
    assert ev1.id == ev2.id

    # 3. Process outbox with mock client
    class FakeLogtoClient:
        async def get_or_create_organization(self, name: str, description: str | None = None):
            return {"id": "fake_logto_org_999", "name": name}

    processed = await identity_service.process_identity_outbox(
        db_session, client=FakeLogtoClient()
    )
    assert processed >= 1

    db_session.refresh(ev1)
    assert ev1.status == "SUCCEEDED"
    assert ev1.processed_at is not None

    # Verify organization link was established
    org_link = (
        db_session.query(ExternalOrganizationLink)
        .filter_by(tenant_id=tenant.id)
        .first()
    )
    assert org_link is not None
    assert org_link.external_organization_id == "fake_logto_org_999"


# ---------------------------------------------------------------------------
# 6. Privacy & Security: No Secret/Token Values in Logs or Error Messages
# ---------------------------------------------------------------------------

def test_privacy_and_token_redaction_in_errors(rsa_keypair):
    """Assert that invalid token strings are NEVER reflected into error details."""
    secret_canary = "SUPER_SECRET_BEARER_CANARY_VALUE_12345"
    with pytest.raises(LogtoValidationError) as exc:
        logto_validator.validate_token(secret_canary, verify_aud=False)

    error_msg = str(exc.value)
    # The canary string must NOT appear in the exception message
    assert secret_canary not in error_msg
    assert exc.value.code in ("MALFORMED_HEADER", "UNSUPPORTED_ALGORITHM")
