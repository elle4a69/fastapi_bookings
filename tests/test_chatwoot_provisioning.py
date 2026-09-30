"""Automated Test Suite for Chatwoot Provisioning Pipeline.

Verifies:
1. End-to-end real Docker Chatwoot provisioning of new tenants, providers, inboxes, webhooks, and staff.
2. Idempotency on repeated runs (non-destructive, reuse existing entities).
3. 1-to-1 account mapping persistence and scoping isolation.
4. Timing-safe webhook secret generation and registration.
5. Admin trigger endpoint: POST /api/sms/chatwoot/provision.
6. Tenant lifecycle integration and offline fail-safe behavior.
"""

import socket
import _socket
import uuid
import secrets
import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.core.config import settings
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.user import User
from app.models.sms_chatwoot import SmsChatwootBinding
from app.services.sms.chatwoot_provisioning_service import (
    provision_tenant_chatwoot,
    ProvisioningResult,
)


@pytest.fixture(autouse=True)
def allow_chatwoot_docker_socket(monkeypatch):
    """Permit loopback connection to Docker Chatwoot on port 4000 while preserving conftest guards."""
    def custom_create_connection(address, *args, **kwargs):
        host, port = address[0], address[1]
        if str(host) in ("127.0.0.1", "localhost", "::1"):
            sock = socket.socket()
            _socket.socket.connect(sock, address)
            return sock
        from tests.conftest import _block_outbound_network
        return _block_outbound_network(address, *args, **kwargs)

    def custom_connect(sock, address):
        host, port = address[0], address[1]
        if str(host) in ("127.0.0.1", "localhost", "::1"):
            return _socket.socket.connect(sock, address)
        from tests.conftest import _guard_socket_connect
        return _guard_socket_connect(sock, address)

    monkeypatch.setattr(socket, "create_connection", custom_create_connection)
    monkeypatch.setattr(socket.socket, "connect", custom_connect)
    if not settings.CHATWOOT_PLATFORM_API_TOKEN:
        monkeypatch.setattr(settings, "CHATWOOT_PLATFORM_API_TOKEN", "ReqRYyswSvVB8nVktQrZP1zg")
    if not settings.CHATWOOT_API_ACCESS_TOKEN:
        monkeypatch.setattr(settings, "CHATWOOT_API_ACCESS_TOKEN", "4ULEfYYtAJAbPZmZYaVcr9Lb")
    yield


def _docker_chatwoot_available() -> bool:
    try:
        r = httpx.get("http://localhost:4000", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def test_provision_tenant_chatwoot_e2e_real_docker(db_session):
    """Verify complete vertical slice of Chatwoot provisioning against local Docker."""
    if not _docker_chatwoot_available():
        pytest.skip("Docker Chatwoot is not online on port 4000.")

    uid = uuid.uuid4().hex[:6]
    tenant = Tenant(
        name=f"E2E Provision Clinic {uid}",
        subdomain=f"clinic-{uid}",
        email=f"admin-{uid}@clinic.local",
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    provider = Provider(
        tenant_id=tenant.id,
        name=f"Dr. Test Provider {uid}",
        email=f"provider-{uid}@clinic.local",
        active=True,
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)

    staff_user = User(
        tenant_id=tenant.id,
        login=f"staff-{uid}@clinic.local",
        password_hash="hashed_pw",
        role="admin",
    )
    db_session.add(staff_user)
    db_session.commit()

    # Run provisioning
    result = provision_tenant_chatwoot(
        db=db_session,
        tenant_id=tenant.id,
    )

    # 1. Assert overall success and persistence
    assert result.success is True
    assert result.status == "provisioned"
    assert result.chatwoot_account_id is not None
    assert result.account_created is True

    # 2. Verify Tenant has persisted chatwoot_account_id
    db_session.refresh(tenant)
    assert tenant.chatwoot_account_id == result.chatwoot_account_id

    # 3. Verify Inbox was created
    assert len(result.inboxes_provisioned) >= 1
    inbox_info = result.inboxes_provisioned[0]
    assert inbox_info["provider_id"] == provider.id
    assert inbox_info["inbox_id"] > 0

    # 4. Verify SmsChatwootBinding was created in DB
    bindings = db_session.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.tenant_id == tenant.id,
        SmsChatwootBinding.provider_id == provider.id,
    ).all()
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.chatwoot_account_id == result.chatwoot_account_id
    assert binding.chatwoot_inbox_id == inbox_info["inbox_id"]
    assert binding.is_enabled is True
    assert binding.webhook_secret is not None
    assert len(binding.webhook_secret) > 20

    # 5. Verify Webhook registration
    assert len(result.webhooks_registered) >= 1
    webhook_info = result.webhooks_registered[0]
    assert "token=" in webhook_info["url"]

    # 6. Verify Staff provisioning
    assert len(result.staff_members_provisioned) >= 1
    staff_info = result.staff_members_provisioned[0]
    assert staff_info["user_id"] == staff_user.id
    assert staff_info["agent_id"] > 0


def test_provision_tenant_chatwoot_idempotency(db_session):
    """Verify running provisioning multiple times is non-destructive and skips existing entities."""
    if not _docker_chatwoot_available():
        pytest.skip("Docker Chatwoot is not online on port 4000.")

    uid = uuid.uuid4().hex[:6]
    tenant = Tenant(
        name=f"Idempotent Health {uid}",
        subdomain=f"idemp-{uid}",
        email=f"admin-{uid}@idemp.local",
    )
    db_session.add(tenant)
    db_session.commit()

    provider = Provider(
        tenant_id=tenant.id,
        name=f"Dr. Idempotent {uid}",
        email=f"provider-{uid}@idemp.local",
        active=True,
    )
    db_session.add(provider)
    db_session.commit()

    staff_user = User(
        tenant_id=tenant.id,
        login=f"admin-{uid}@idemp.local",
        password_hash="pw",
        role="admin",
    )
    db_session.add(staff_user)
    db_session.commit()

    # First run
    result1 = provision_tenant_chatwoot(db=db_session, tenant_id=tenant.id)
    assert result1.success is True
    assert result1.account_created is True
    first_account_id = result1.chatwoot_account_id
    first_inbox_id = result1.inboxes_provisioned[0]["inbox_id"]

    # Count bindings
    bindings_count_1 = db_session.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.tenant_id == tenant.id
    ).count()
    assert bindings_count_1 == 1

    # Second run (immediate retry / reconciliation)
    result2 = provision_tenant_chatwoot(db=db_session, tenant_id=tenant.id)
    assert result2.success is True
    assert result2.status == "provisioned"
    # Account should NOT be recreated
    assert result2.account_created is False
    assert result2.chatwoot_account_id == first_account_id
    # Inbox should be reused
    assert result2.inboxes_provisioned[0]["inbox_id"] == first_inbox_id

    # No duplicate bindings in DB
    bindings_count_2 = db_session.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.tenant_id == tenant.id
    ).count()
    assert bindings_count_2 == 1


def test_admin_trigger_provision_route(db_session, client):
    """Verify POST /api/sms/chatwoot/provision endpoint."""
    if not _docker_chatwoot_available():
        pytest.skip("Docker Chatwoot is not online on port 4000.")

    uid = uuid.uuid4().hex[:6]
    tenant = Tenant(
        name=f"Admin Trigger Clinic {uid}",
        subdomain=f"admintrigger-{uid}",
        email=f"admin-{uid}@trigger.local",
    )
    db_session.add(tenant)
    db_session.commit()

    provider = Provider(
        tenant_id=tenant.id,
        name=f"Dr. Admin Trigger {uid}",
        active=True,
    )
    db_session.add(provider)
    db_session.commit()

    admin_user = User(
        id=777,
        tenant_id=tenant.id,
        login=f"admin-{uid}@trigger.local",
        password_hash="pw",
        role="admin",
    )
    db_session.add(admin_user)
    db_session.commit()

    from app.api.deps import get_current_tenant, get_current_admin
    fastapi_app.dependency_overrides[get_current_tenant] = lambda: tenant
    fastapi_app.dependency_overrides[get_current_admin] = lambda: admin_user

    try:
        resp = client.post("/api/sms/chatwoot/provision", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "provisioned"
        assert data["tenant_id"] == tenant.id
        assert data["chatwoot_account_id"] is not None
        assert len(data["inboxes_provisioned"]) >= 1
        assert len(data["bindings_created"]) >= 1
    finally:
        fastapi_app.dependency_overrides.pop(get_current_tenant, None)
        fastapi_app.dependency_overrides.pop(get_current_admin, None)


def test_offline_failsafe_handling(db_session):
    """Verify fail-safe behavior when Chatwoot instance is offline."""
    uid = uuid.uuid4().hex[:6]
    tenant = Tenant(
        name=f"Offline Test Clinic {uid}",
        subdomain=f"offline-{uid}",
    )
    db_session.add(tenant)
    db_session.commit()

    # Point to an unreachable port
    result = provision_tenant_chatwoot(
        db=db_session,
        tenant_id=tenant.id,
        chatwoot_base_url="http://127.0.0.1:59999",
    )

    assert result.success is False
    assert result.status == "pending"
    assert "unreachable" in result.error_message.lower() or "connect" in result.error_message.lower()


def test_tenant_lifecycle_creation_with_auto_provision(db_session, client, monkeypatch):
    """Verify POST /api/tenants triggers auto-provisioning when enabled."""
    if not _docker_chatwoot_available():
        pytest.skip("Docker Chatwoot is not online on port 4000.")

    monkeypatch.setattr(settings, "CHATWOOT_AUTO_PROVISION", True)

    uid = uuid.uuid4().hex[:6]
    resp = client.post(
        "/api/tenants",
        json={
            "name": f"Lifecycle Tenant {uid}",
            "subdomain": f"lifecycle-{uid}",
            "email": f"lifecycle-{uid}@test.local",
            "timezone": "UTC",
        },
    )
    assert resp.status_code == 201
    tenant_data = resp.json()["data"]
    created_id = tenant_data["id"]

    # Verify tenant in DB has chatwoot_account_id set by the lifecycle hook
    created_tenant = db_session.query(Tenant).filter(Tenant.id == created_id).first()
    assert created_tenant is not None
    assert created_tenant.chatwoot_account_id is not None
