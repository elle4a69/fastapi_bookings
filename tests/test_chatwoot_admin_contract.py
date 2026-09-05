"""Tenant-admin contract tests for Chatwoot connection and inbox setup."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.security import create_access_token
from app.models.provider import Provider
from app.models.sms_chatwoot import ChatwootConnection, SmsChatwootBinding
from app.models.tenant import Tenant
from app.models.user import User


def _admin_context(db_session, suffix: str):
    tenant = Tenant(
        name=f"Synthetic Chatwoot {suffix}", subdomain=f"chatwoot-{suffix}"
    )
    db_session.add(tenant)
    db_session.flush()
    admin = User(
        tenant_id=tenant.id,
        login=f"admin-{suffix}",
        password_hash="synthetic",
        role="admin",
        created_at=datetime.now(timezone.utc),
    )
    provider = Provider(
        tenant_id=tenant.id, name=f"Synthetic Provider {suffix}", active=True
    )
    db_session.add_all([admin, provider])
    db_session.commit()
    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(admin.id)}),
    }
    return tenant, provider, headers


def _create_connection(client, headers, account_id=101):
    return client.post(
        "/api/admin/messaging/chatwoot/connections",
        headers=headers,
        json={
            "instance_origin": "HTTPS://Chatwoot.Example.Test:443/",
            "chatwoot_account_id": account_id,
        },
    )


def test_admin_connection_is_disabled_first_tenant_scoped_and_secret_safe(
    client, db_session
):
    tenant_a, _, headers_a = _admin_context(db_session, "admin-a")
    _, _, headers_b = _admin_context(db_session, "admin-b")
    unauthenticated = client.get("/api/admin/messaging/chatwoot/connections")
    assert unauthenticated.status_code in {400, 401}

    rejected = client.post(
        "/api/admin/messaging/chatwoot/connections",
        headers=headers_a,
        json={
            "instance_origin": "https://chatwoot.example.test",
            "chatwoot_account_id": 101,
            "enabled": True,
        },
    )
    assert rejected.status_code == 422

    created = _create_connection(client, headers_a)
    assert created.status_code == 201
    body = created.json()
    assert body["tenant_id"] == tenant_a.id
    assert body["instance_origin"] == "https://chatwoot.example.test"
    assert body["enabled"] is False
    assert body["has_signing_secret"] is False
    assert body["webhook_path"].startswith(
        "/api/messaging/chatwoot/webhooks/"
    )
    serialized = created.text.lower()
    assert "ciphertext" not in serialized
    assert "signing_secret" not in body
    assert "token" not in serialized
    assert "http://testserver" not in serialized

    assert (
        client.get(
            f"/api/admin/messaging/chatwoot/connections/{body['id']}",
            headers=headers_b,
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/admin/messaging/chatwoot/connections/{body['id']}",
            headers=headers_a,
            json={"enabled": True},
        ).status_code
        == 409
    )

    secret = "synthetic-chatwoot-signing-secret-000001"
    rotated = client.put(
        f"/api/admin/messaging/chatwoot/connections/{body['id']}/signing-secret",
        headers=headers_a,
        json={"signing_secret": secret},
    )
    assert rotated.status_code == 200
    assert rotated.json()["has_signing_secret"] is True
    assert secret not in rotated.text
    stored = db_session.get(ChatwootConnection, body["id"])
    assert stored._signing_secret_ciphertext != secret
    assert secret not in stored._signing_secret_ciphertext

    enabled = client.patch(
        f"/api/admin/messaging/chatwoot/connections/{body['id']}",
        headers=headers_a,
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert (
        client.put(
            f"/api/admin/messaging/chatwoot/connections/{body['id']}/signing-secret",
            headers=headers_a,
            json={"signing_secret": secret + "-rotated"},
        ).status_code
        == 409
    )


def test_inbox_binding_validates_provider_and_effective_connection(
    client, db_session
):
    _, provider_a, headers_a = _admin_context(db_session, "binding-a")
    _, provider_b, _ = _admin_context(db_session, "binding-b")
    connection = _create_connection(client, headers_a, account_id=201).json()

    wrong_provider = client.post(
        "/api/admin/messaging/chatwoot/inbox-bindings",
        headers=headers_a,
        json={
            "connection_id": connection["id"],
            "provider_id": provider_b.id,
            "chatwoot_inbox_id": 202,
        },
    )
    assert wrong_provider.status_code == 404

    created = client.post(
        "/api/admin/messaging/chatwoot/inbox-bindings",
        headers=headers_a,
        json={
            "connection_id": connection["id"],
            "provider_id": provider_a.id,
            "chatwoot_inbox_id": 202,
        },
    )
    assert created.status_code == 201
    binding = created.json()
    assert binding["ingress_enabled"] is False
    assert binding["effective_ingress_enabled"] is False
    assert (
        client.patch(
            f"/api/admin/messaging/chatwoot/inbox-bindings/{binding['id']}",
            headers=headers_a,
            json={"ingress_enabled": True},
        ).status_code
        == 409
    )

    secret = "synthetic-chatwoot-signing-secret-000002"
    client.put(
        f"/api/admin/messaging/chatwoot/connections/{connection['id']}/signing-secret",
        headers=headers_a,
        json={"signing_secret": secret},
    )
    client.patch(
        f"/api/admin/messaging/chatwoot/connections/{connection['id']}",
        headers=headers_a,
        json={"enabled": True},
    )
    enabled = client.patch(
        f"/api/admin/messaging/chatwoot/inbox-bindings/{binding['id']}",
        headers=headers_a,
        json={"ingress_enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["effective_ingress_enabled"] is True

    immutable = client.patch(
        f"/api/admin/messaging/chatwoot/inbox-bindings/{binding['id']}",
        headers=headers_a,
        json={"chatwoot_inbox_id": 999},
    )
    assert immutable.status_code == 422
    assert (
        client.delete(
            f"/api/admin/messaging/chatwoot/inbox-bindings/{binding['id']}",
            headers=headers_a,
        ).status_code
        == 405
    )


def test_duplicate_identity_conflicts_and_legacy_routes_are_removed(
    client, db_session, caplog
):
    _, provider, headers = _admin_context(db_session, "duplicates")
    connection = _create_connection(client, headers, account_id=301)
    assert connection.status_code == 201
    assert _create_connection(client, headers, account_id=301).status_code == 409

    connection_id = connection.json()["id"]
    payload = {
        "connection_id": connection_id,
        "provider_id": provider.id,
        "chatwoot_inbox_id": 302,
    }
    assert (
        client.post(
            "/api/admin/messaging/chatwoot/inbox-bindings",
            headers=headers,
            json=payload,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/admin/messaging/chatwoot/inbox-bindings",
            headers=headers,
            json=payload,
        ).status_code
        == 409
    )

    legacy = client.post(
        "/api/sms/chatwoot/webhook?token=synthetic-query-secret",
        content=b"not-json-and-must-not-be-read",
    )
    assert legacy.status_code == 410
    assert "synthetic-query-secret" not in legacy.text
    assert "synthetic-query-secret" not in caplog.text
    assert client.get("/api/sms/chatwoot/bindings", headers=headers).status_code == 404
    assert (
        client.get("/api/admin/sms/chatwoot/bindings", headers=headers).status_code
        == 404
    )
    assert db_session.query(SmsChatwootBinding).count() == 1


@pytest.mark.parametrize(
    "secret",
    [
        "SENTINEL-too-short",
        "SENTINEL-" + "x" * 600,
        " SENTINEL-whitespace-secret-value-000001 ",
    ],
)
def test_validation_errors_never_reflect_rejected_signing_secrets(
    client, db_session, caplog, secret
):
    _, _, headers = _admin_context(db_session, f"validation-{uuid4().hex[:8]}")
    connection = _create_connection(client, headers, account_id=401).json()
    response = client.put(
        f"/api/admin/messaging/chatwoot/connections/{connection['id']}/signing-secret",
        headers=headers,
        json={"signing_secret": secret},
    )
    assert response.status_code == 422
    assert "SENTINEL" not in response.text
    assert "SENTINEL" not in caplog.text
    details = response.json()["error"]["details"]
    assert details
    assert set(details[0]) == {"loc", "type", "msg"}


def test_validation_error_never_reflects_credential_bearing_origin(
    client, db_session, caplog
):
    _, _, headers = _admin_context(db_session, "origin-validation")
    sentinel = "SENTINEL-CREDENTIAL"
    response = client.post(
        "/api/admin/messaging/chatwoot/connections",
        headers=headers,
        json={
            "instance_origin": (
                f"https://user:{sentinel}@chatwoot.example.test/?token={sentinel}"
            ),
            "chatwoot_account_id": 402,
        },
    )
    assert response.status_code == 422
    assert sentinel not in response.text
    assert sentinel not in caplog.text
