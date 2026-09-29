"""Automated Test Suite for Assistant Studio Policy Persistence, Scoping Lockdown & Importer Dry-Run Safety.

Enforces:
1. Real database persistence of Tenant.assistant_policy via GET & PUT /api/admin/assistant-studio/policy.
2. Uniform provider scoping enforcement: cross-tenant provider IDs are rejected with 404 across all endpoints.
3. Platform seed lockdown: examples with tenant_id IS NULL are read-only and reject PUT/DELETE with 403 Forbidden.
4. Importer dry-run safety: dry_run=True validates the asset and reports counts but commits 0 rows to DB.
"""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.curated_memory import CuratedMemory
from app.models.location import Location
from app.models.message_style_example import MessageStyleExample
from app.models.provider import Provider
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.user import User
from app.services.knowledge.asset_importer import (
    DEFAULT_APPROVED_EXAMPLES_PATH,
    import_approved_style_examples,
)


def _auth_headers(tenant: Tenant, admin_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(admin_user.id)})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


def _error_message(resp) -> str:
    body = resp.json()
    if isinstance(body, dict):
        if "error" in body and isinstance(body["error"], dict):
            return body["error"].get("message", "")
        return body.get("detail", "")
    return str(body)


@pytest.fixture
def policy_scoping_env(db_session: Session):
    """Seed multi-tenant fixture with two isolated tenants, providers, and examples."""
    # Ensure tables
    CuratedMemory.__table__.create(bind=db_session.bind, checkfirst=True)
    MessageStyleExample.__table__.create(bind=db_session.bind, checkfirst=True)

    tenant_a = Tenant(name="Tenant Alpha Health", subdomain="tenant-alpha")
    tenant_b = Tenant(name="Tenant Beta Wellness", subdomain="tenant-beta")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin@tenant-alpha.test",
        password_hash="hashed_pw_a",
        role="admin",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin@tenant-beta.test",
        password_hash="hashed_pw_b",
        role="admin",
    )
    db_session.add_all([admin_a, admin_b])
    db_session.flush()

    prov_a = Provider(
        tenant_id=tenant_a.id,
        name="Dr. Alpha Specialist",
        active=True,
    )
    prov_b = Provider(
        tenant_id=tenant_b.id,
        name="Dr. Beta Practitioner",
        active=True,
    )
    db_session.add_all([prov_a, prov_b])
    db_session.flush()

    loc_a = Location(
        tenant_id=tenant_a.id,
        name="Alpha Clinic Sydney",
        address="100 George St, Sydney NSW 2000",
        timezone="Australia/Sydney",
        active=True,
    )
    db_session.add(loc_a)

    srv_a = Service(
        tenant_id=tenant_a.id,
        name="Alpha Health Assessment",
        price=120.00,
        duration=45,
        active=True,
    )
    db_session.add(srv_a)

    # Platform seed example (tenant_id IS NULL)
    seed_example = MessageStyleExample(
        tenant_id=None,
        provider_id=None,
        intent="general_greeting",
        client_message="Hello, are you there?",
        assistant_reply="Hello! How may I assist you with your booking today?",
        category="procedural",
        tags=["greeting"],
        is_approved=True,
        is_active=True,
        source="platform_seed",
        content_hash="seed_hash_001",
    )
    # Tenant-specific example for Tenant A
    tenant_a_example = MessageStyleExample(
        tenant_id=tenant_a.id,
        provider_id=prov_a.id,
        intent="booking_inquiry",
        client_message="Do you have open consultations?",
        assistant_reply="Yes, we offer health assessments Monday to Friday.",
        category="procedural",
        tags=["inquiry"],
        is_approved=True,
        is_active=True,
        source="assistant_studio",
        content_hash="tenant_a_hash_001",
    )
    # Tenant-specific example for Tenant B
    tenant_b_example = MessageStyleExample(
        tenant_id=tenant_b.id,
        provider_id=prov_b.id,
        intent="hours_inquiry",
        client_message="What are your hours?",
        assistant_reply="Our Melbourne clinic is open 9am-5pm.",
        category="procedural",
        tags=["hours"],
        is_approved=True,
        is_active=True,
        source="assistant_studio",
        content_hash="tenant_b_hash_001",
    )
    db_session.add_all([seed_example, tenant_a_example, tenant_b_example])
    db_session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "prov_a": prov_a,
        "prov_b": prov_b,
        "seed_example": seed_example,
        "tenant_a_example": tenant_a_example,
        "tenant_b_example": tenant_b_example,
    }


# =========================================================================
# 1. Tenant Policy Persistence Tests
# =========================================================================

def test_tenant_policy_persistence_via_api_and_db(policy_scoping_env, db_session: Session, client: TestClient):
    """PUT /policy saves tenant_policy into Tenant.assistant_policy, and GET /policy returns it."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])

    custom_policy_text = (
        "Strict 48-hour cancellation policy applies to all Alpha Health bookings. "
        "Clients must arrive 10 minutes prior to scheduled session."
    )

    # 1. Update policy via PUT /api/admin/assistant-studio/policy
    put_resp = client.put(
        "/api/admin/assistant-studio/policy",
        headers=headers_a,
        json={"tenant_policy": custom_policy_text},
    )
    assert put_resp.status_code == status.HTTP_200_OK
    put_data = put_resp.json()
    assert put_data["tenant_policy"] == custom_policy_text

    # Verify Tier 3 in response matches
    tier_3 = next(t for t in put_data["tiers"] if t["tier"] == 3)
    assert tier_3["content"] == custom_policy_text

    # 2. Query GET /api/admin/assistant-studio/policy
    get_resp = client.get("/api/admin/assistant-studio/policy", headers=headers_a)
    assert get_resp.status_code == status.HTTP_200_OK
    get_data = get_resp.json()
    assert get_data["tenant_policy"] == custom_policy_text

    # 3. Verify directly on the database row
    tenant_row = db_session.query(Tenant).filter(Tenant.id == env["tenant_a"].id).first()
    assert tenant_row is not None
    assert tenant_row.assistant_policy == custom_policy_text


# =========================================================================
# 2. Uniform Provider Scoping Enforcement Tests
# =========================================================================

def test_provider_scoping_rejected_on_policy_endpoints(policy_scoping_env, client: TestClient):
    """GET and PUT /policy reject cross-tenant provider_id with 404."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])
    cross_provider_id = env["prov_b"].id

    # GET /policy with Tenant B provider_id
    resp_get = client.get(
        f"/api/admin/assistant-studio/policy?provider_id={cross_provider_id}",
        headers=headers_a,
    )
    assert resp_get.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found in current tenant" in _error_message(resp_get)

    # PUT /policy with Tenant B provider_id
    resp_put = client.put(
        "/api/admin/assistant-studio/policy",
        headers=headers_a,
        json={"provider_id": cross_provider_id, "agent_name": "Injected"},
    )
    assert resp_put.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found in current tenant" in _error_message(resp_put)


def test_provider_scoping_rejected_on_simulate_endpoint(policy_scoping_env, client: TestClient):
    """POST /simulate rejects cross-tenant provider_id with 404."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])
    cross_provider_id = env["prov_b"].id

    resp = client.post(
        "/api/admin/assistant-studio/simulate",
        headers=headers_a,
        json={
            "client_input": "Do you have any openings tomorrow?",
            "provider_id": cross_provider_id,
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found in current tenant" in _error_message(resp)


def test_provider_scoping_rejected_on_examples_endpoints(policy_scoping_env, client: TestClient):
    """GET and POST /examples reject cross-tenant provider_id with 404."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])
    cross_provider_id = env["prov_b"].id

    # GET /examples with cross-tenant provider_id
    resp_get = client.get(
        f"/api/admin/assistant-studio/examples?provider_id={cross_provider_id}",
        headers=headers_a,
    )
    assert resp_get.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found in current tenant" in _error_message(resp_get)

    # POST /examples with cross-tenant provider_id
    resp_post = client.post(
        "/api/admin/assistant-studio/examples",
        headers=headers_a,
        json={
            "intent": "cross_tenant_test",
            "client_message": "Test inquiry message",
            "assistant_reply": "Test reply message",
            "provider_id": cross_provider_id,
        },
    )
    assert resp_post.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found in current tenant" in _error_message(resp_post)


def test_provider_scoping_rejected_on_variables_and_curator(policy_scoping_env, client: TestClient):
    """GET /variables and GET /curator/proposals reject cross-tenant provider_id with 404."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])
    cross_provider_id = env["prov_b"].id

    # GET /variables
    resp_var = client.get(
        f"/api/admin/assistant-studio/variables?provider_id={cross_provider_id}",
        headers=headers_a,
    )
    assert resp_var.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found in current tenant" in _error_message(resp_var)

    # GET /curator/proposals
    resp_cur = client.get(
        f"/api/admin/assistant-studio/curator/proposals?provider_id={cross_provider_id}",
        headers=headers_a,
    )
    assert resp_cur.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found in current tenant" in _error_message(resp_cur)


def test_provider_scoping_rejected_on_import(policy_scoping_env, client: TestClient):
    """POST /import rejects cross-tenant provider_id with 404."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])
    cross_provider_id = env["prov_b"].id

    resp = client.post(
        "/api/admin/assistant-studio/import",
        headers=headers_a,
        json={
            "provider_id": cross_provider_id,
            "scope": "provider_override",
            "dry_run": True,
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "Provider not found in current tenant" in _error_message(resp)


# =========================================================================
# 3. Platform Seed Examples Read-Only Lockdown Tests
# =========================================================================

def test_platform_seed_examples_are_read_only(policy_scoping_env, db_session: Session, client: TestClient):
    """PUT and DELETE on an example where tenant_id IS NULL returns 403 Forbidden."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])
    seed_id = env["seed_example"].id

    # 1. Attempt to update platform seed example
    put_resp = client.put(
        f"/api/admin/assistant-studio/examples/{seed_id}",
        headers=headers_a,
        json={"assistant_reply": "Maliciously modified seed reply."},
    )
    assert put_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "Platform seed examples are read-only" in _error_message(put_resp)

    # 2. Attempt to delete platform seed example
    del_resp = client.delete(
        f"/api/admin/assistant-studio/examples/{seed_id}",
        headers=headers_a,
    )
    assert del_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "Platform seed examples are read-only" in _error_message(del_resp)

    # 3. Verify record was NOT mutated or deleted in DB
    seed_record = db_session.query(MessageStyleExample).filter(MessageStyleExample.id == seed_id).first()
    assert seed_record is not None
    assert seed_record.assistant_reply == "Hello! How may I assist you with your booking today?"


def test_cross_tenant_example_modification_rejected(policy_scoping_env, client: TestClient):
    """Admin A cannot modify or delete Tenant B's style example."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])
    tenant_b_example_id = env["tenant_b_example"].id

    # Attempt to update Tenant B's example as Tenant A
    put_resp = client.put(
        f"/api/admin/assistant-studio/examples/{tenant_b_example_id}",
        headers=headers_a,
        json={"assistant_reply": "Hijacked reply."},
    )
    assert put_resp.status_code == status.HTTP_404_NOT_FOUND

    # Attempt to delete Tenant B's example as Tenant A
    del_resp = client.delete(
        f"/api/admin/assistant-studio/examples/{tenant_b_example_id}",
        headers=headers_a,
    )
    assert del_resp.status_code == status.HTTP_404_NOT_FOUND


def test_style_example_write_rejects_dynamic_operational_content(policy_scoping_env, client: TestClient):
    """Studio CRUD cannot turn a literal future slot into reusable prompting."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])
    response = client.post(
        "/api/admin/assistant-studio/examples",
        headers=headers_a,
        json={
            "intent": "availability",
            "client_message": "Can I come tomorrow?",
            "assistant_reply": "Yes, I have a 2:30 pm slot tomorrow.",
            "provider_id": env["prov_a"].id,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "safety classifier" in _error_message(response)


# =========================================================================
# 4. Importer Dry-Run Safe Rollback Tests
# =========================================================================

def test_importer_dry_run_persists_zero_rows_direct_service(policy_scoping_env, db_session: Session):
    """Calling import_approved_style_examples with dry_run=True commits 0 rows to DB."""
    initial_count = db_session.query(MessageStyleExample).count()

    report = import_approved_style_examples(
        db=db_session,
        file_path=DEFAULT_APPROVED_EXAMPLES_PATH,
        tenant_id=policy_scoping_env["tenant_a"].id,
        enforce_sha=True,
        dry_run=True,
    )

    assert report.sha256_verified is True
    assert report.total_scanned == 180
    assert report.imported_count == 157
    assert report.rejected_count == 23

    # Verify that database row count did not change!
    final_count = db_session.query(MessageStyleExample).count()
    assert final_count == initial_count


def test_importer_dry_run_via_api_persists_zero_rows(policy_scoping_env, db_session: Session, client: TestClient):
    """POST /import with dry_run=True validates the asset but leaves DB count unchanged."""
    env = policy_scoping_env
    headers_a = _auth_headers(env["tenant_a"], env["admin_a"])

    initial_tenant_a_count = (
        db_session.query(MessageStyleExample)
        .filter(MessageStyleExample.tenant_id == env["tenant_a"].id)
        .count()
    )

    resp = client.post(
        "/api/admin/assistant-studio/import",
        headers=headers_a,
        json={
            "scope": "tenant_override",
            "dry_run": True,
        },
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "success"
    assert data["dryRunUsed"] is True
    assert data["sha256_verified"] is True
    assert data["imported"] == 157

    # Ensure exactly 0 rows were added for Tenant A in DB
    final_tenant_a_count = (
        db_session.query(MessageStyleExample)
        .filter(MessageStyleExample.tenant_id == env["tenant_a"].id)
        .count()
    )
    assert final_tenant_a_count == initial_tenant_a_count
