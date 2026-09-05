from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import BigInteger, create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - populate SQLAlchemy metadata
import app.schemas.sms_chatwoot as chatwoot_schemas
from app.db.database import Base
from app.models.provider import Provider
from app.models.sms_chatwoot import (
    ChatwootConnection,
    ChatwootWebhookReceipt,
    SmsChatwootBinding,
)
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.tenant import Tenant
from app.schemas.sms_chatwoot import (
    ChatwootConnectionCreate,
    ChatwootConnectionResponse,
    ChatwootConnectionUpdate,
    ChatwootInboxBindingCreate,
    ChatwootInboxBindingResponse,
    ChatwootInboxBindingUpdate,
    ChatwootSigningSecretRotate,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _tenant_provider(session: Session, suffix: str) -> tuple[Tenant, Provider]:
    tenant = Tenant(name=f"Synthetic Tenant {suffix}", subdomain=f"synthetic-{suffix}")
    session.add(tenant)
    session.flush()
    provider = Provider(tenant_id=tenant.id, name=f"Synthetic Provider {suffix}")
    session.add(provider)
    session.flush()
    return tenant, provider


def _connection(session: Session, tenant: Tenant, account_id: int) -> ChatwootConnection:
    connection = ChatwootConnection(
        tenant_id=tenant.id,
        instance_origin=f"https://chatwoot-{account_id}.example.test",
        chatwoot_account_id=account_id,
    )
    session.add(connection)
    session.flush()
    return connection


def _binding(
    session: Session,
    tenant: Tenant,
    provider: Provider,
    connection: ChatwootConnection,
    inbox_id: int,
) -> SmsChatwootBinding:
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        connection_id=connection.id,
        chatwoot_inbox_id=inbox_id,
        channel="web_widget",
        ingress_enabled=False,
        chatwoot_account_id=None,
        chatwoot_base_url=None,
        _chatwoot_api_token=None,
        _webhook_secret=None,
    )
    session.add(binding)
    session.flush()
    return binding


def test_new_metadata_has_scoped_constraints_and_no_sensitive_receipt_columns():
    connection_table = ChatwootConnection.__table__
    binding_table = SmsChatwootBinding.__table__
    conversation_table = SmsConversation.__table__
    message_table = SmsMessage.__table__
    receipt_table = ChatwootWebhookReceipt.__table__

    assert connection_table.c.public_id.type.python_type is UUID
    assert isinstance(connection_table.c.chatwoot_account_id.type, BigInteger)
    assert connection_table.c.enabled.default.arg is False
    assert str(connection_table.c.enabled.server_default.arg) == "false"
    assert binding_table.c.ingress_enabled.default.arg is False
    assert binding_table.c.is_enabled.default.arg is False
    assert str(binding_table.c.is_enabled.server_default.arg) == "false"
    assert str(binding_table.c.ingress_enabled.server_default.arg) == "false"
    assert binding_table.c.chatwoot_account_id.nullable is True
    assert binding_table.c.chatwoot_base_url.nullable is True
    assert binding_table.c.chatwoot_api_token.nullable is True
    assert binding_table.c.webhook_secret.nullable is True
    assert isinstance(binding_table.c.chatwoot_account_id.type, BigInteger)
    assert isinstance(binding_table.c.chatwoot_inbox_id.type, BigInteger)
    assert isinstance(conversation_table.c.chatwoot_conversation_id.type, BigInteger)
    assert isinstance(conversation_table.c.chatwoot_contact_id.type, BigInteger)
    assert isinstance(conversation_table.c.chatwoot_inbox_id.type, BigInteger)
    assert isinstance(message_table.c.chatwoot_message_id.type, BigInteger)

    uniques = {
        constraint.name
        for table in (connection_table, binding_table, conversation_table, message_table, receipt_table)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert {
        "uq_chatwoot_connections_public_id",
        "uq_chatwoot_connections_origin_account",
        "uq_chatwoot_connections_id_tenant",
        "uq_sms_chatwoot_bindings_id_tenant",
        "uq_sms_chatwoot_bindings_connection_inbox",
        "uq_sms_conversations_binding_conversation",
        "uq_sms_conversations_id_chatwoot_binding",
        "uq_sms_messages_binding_chatwoot_message",
        "uq_chatwoot_webhook_receipts_connection_delivery",
    } <= uniques

    receipt_columns = set(receipt_table.c.keys())
    assert not receipt_columns.intersection(
        {
            "raw_payload",
            "payload",
            "body",
            "headers",
            "signature",
            "url",
            "identity",
            "exception",
            "error",
        }
    )


def test_legacy_binding_is_effectively_disabled_without_mutating_legacy_values(db_session):
    tenant, provider = _tenant_provider(db_session, "legacy")
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        chatwoot_account_id=123,
        chatwoot_inbox_id=456,
        chatwoot_base_url="https://legacy.example.test",
        _chatwoot_api_token="legacy-ciphertext",
        _webhook_secret="legacy-secret-ciphertext",
        is_enabled=True,
    )
    db_session.add(binding)
    db_session.commit()
    db_session.refresh(binding)

    assert binding.connection_id is None
    assert binding.ingress_enabled is False
    assert binding.effective_ingress_enabled is False
    assert binding.chatwoot_account_id == 123
    assert binding.chatwoot_inbox_id == 456
    assert binding.chatwoot_base_url == "https://legacy.example.test"
    assert binding._chatwoot_api_token == "legacy-ciphertext"
    assert binding._webhook_secret == "legacy-secret-ciphertext"


def test_connection_defaults_to_disabled_uuid4_and_relative_webhook_path(db_session):
    tenant, _ = _tenant_provider(db_session, "connection")
    connection = _connection(db_session, tenant, 321)
    db_session.commit()

    assert connection.public_id.version == 4
    assert connection.enabled is False
    assert connection.webhook_path == (
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}"
    )
    assert connection.has_signing_secret is False

    response = ChatwootConnectionResponse.model_validate(connection)
    assert response.webhook_path == connection.webhook_path
    assert response.has_signing_secret is False
    assert not {
        "signing_secret",
        "signing_secret_ciphertext",
        "chatwoot_api_token",
    }.intersection(response.model_dump())


def test_effective_ingress_requires_every_safety_gate(db_session):
    tenant, provider = _tenant_provider(db_session, "effective")
    connection = _connection(db_session, tenant, 330)
    binding = _binding(db_session, tenant, provider, connection, 331)
    db_session.commit()

    assert binding.is_enabled is False
    assert binding.effective_ingress_enabled is False

    binding.ingress_enabled = True
    assert binding.effective_ingress_enabled is False
    connection.enabled = True
    assert binding.effective_ingress_enabled is False
    connection._signing_secret_ciphertext = "synthetic-ciphertext"
    assert binding.effective_ingress_enabled is True

    binding.channel = "unknown"
    assert binding.effective_ingress_enabled is False
    binding.channel = "web_widget"
    binding.is_enabled = True
    assert binding.effective_ingress_enabled is False


def test_connection_and_binding_tenant_constraints_are_enforced(db_session):
    tenant_a, provider_a = _tenant_provider(db_session, "tenant-a")
    tenant_b, _provider_b = _tenant_provider(db_session, "tenant-b")
    connection = _connection(db_session, tenant_a, 400)
    db_session.commit()

    cross_tenant = SmsChatwootBinding(
        tenant_id=tenant_b.id,
        provider_id=provider_a.id,
        connection_id=connection.id,
        chatwoot_inbox_id=401,
        channel="web_widget",
        ingress_enabled=False,
    )
    db_session.add(cross_tenant)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    binding = _binding(db_session, tenant_a, provider_a, connection, 401)
    db_session.commit()
    conversation = SmsConversation(
        tenant_id=tenant_b.id,
        provider_id=provider_a.id,
        sms_account_id=None,
        customer_address="synthetic-channel-reference",
        chatwoot_binding_id=binding.id,
        chatwoot_conversation_id=402,
    )
    db_session.add(conversation)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_global_account_and_connection_inbox_uniqueness_are_enforced(db_session):
    tenant_a, provider_a = _tenant_provider(db_session, "unique-a")
    tenant_b, provider_b = _tenant_provider(db_session, "unique-b")
    connection_a = _connection(db_session, tenant_a, 450)
    db_session.commit()

    duplicate_account = ChatwootConnection(
        tenant_id=tenant_b.id,
        instance_origin=connection_a.instance_origin,
        chatwoot_account_id=connection_a.chatwoot_account_id,
    )
    db_session.add(duplicate_account)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    binding_a = _binding(db_session, tenant_a, provider_a, connection_a, 451)
    db_session.commit()
    duplicate_inbox = SmsChatwootBinding(
        tenant_id=tenant_a.id,
        provider_id=provider_a.id,
        connection_id=connection_a.id,
        chatwoot_inbox_id=binding_a.chatwoot_inbox_id,
        channel="web_widget",
        ingress_enabled=False,
    )
    db_session.add(duplicate_inbox)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    connection_b = _connection(db_session, tenant_b, 452)
    _binding(
        db_session,
        tenant_b,
        provider_b,
        connection_b,
        binding_a.chatwoot_inbox_id,
    )
    db_session.commit()


def test_binding_pairing_constraint_separates_legacy_and_connection_rows(db_session):
    tenant, provider = _tenant_provider(db_session, "pairing")
    connection = _connection(db_session, tenant, 470)
    db_session.commit()

    legacy_enabled_for_ingress = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        chatwoot_account_id=470,
        chatwoot_inbox_id=471,
        chatwoot_base_url="https://legacy.example.test",
        _chatwoot_api_token="legacy-ciphertext",
        ingress_enabled=True,
    )
    db_session.add(legacy_enabled_for_ingress)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    connection_with_legacy_credentials = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        connection_id=connection.id,
        chatwoot_account_id=470,
        chatwoot_inbox_id=471,
        chatwoot_base_url="https://legacy.example.test",
        _chatwoot_api_token="legacy-ciphertext",
        channel="web_widget",
        ingress_enabled=False,
    )
    db_session.add(connection_with_legacy_credentials)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_scoped_remote_id_uniqueness_allows_different_scopes(db_session):
    tenant, provider = _tenant_provider(db_session, "scope")
    connection = _connection(db_session, tenant, 500)
    binding_a = _binding(db_session, tenant, provider, connection, 501)
    binding_b = _binding(db_session, tenant, provider, connection, 502)

    conversation_a = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        customer_address="synthetic-a",
        chatwoot_binding_id=binding_a.id,
        chatwoot_conversation_id=503,
    )
    conversation_b = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        customer_address="synthetic-b",
        chatwoot_binding_id=binding_b.id,
        chatwoot_conversation_id=503,
    )
    db_session.add_all([conversation_a, conversation_b])
    db_session.flush()

    common = {
        "tenant_id": tenant.id,
        "provider_id": provider.id,
        "body": "synthetic",
        "direction": "inbound",
        "author_type": "customer",
    }
    message_a = SmsMessage(
        conversation_id=conversation_a.id,
        chatwoot_binding_id=binding_a.id,
        chatwoot_message_id=504,
        **common,
    )
    message_b = SmsMessage(
        conversation_id=conversation_b.id,
        chatwoot_binding_id=binding_b.id,
        chatwoot_message_id=504,
        **common,
    )
    db_session.add_all([message_a, message_b])
    db_session.commit()

    conversation_c = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        customer_address="synthetic-c",
        chatwoot_binding_id=binding_a.id,
        chatwoot_conversation_id=505,
    )
    db_session.add(conversation_c)
    db_session.flush()
    duplicate = SmsMessage(
        conversation_id=conversation_c.id,
        chatwoot_binding_id=binding_a.id,
        chatwoot_message_id=504,
        **common,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_message_binding_must_match_conversation_binding(db_session):
    tenant, provider = _tenant_provider(db_session, "message-binding")
    connection = _connection(db_session, tenant, 520)
    binding_a = _binding(db_session, tenant, provider, connection, 521)
    binding_b = _binding(db_session, tenant, provider, connection, 522)
    conversation = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        customer_address="synthetic-binding-a",
        chatwoot_binding_id=binding_a.id,
        chatwoot_conversation_id=523,
    )
    db_session.add(conversation)
    db_session.flush()
    db_session.add(
        SmsMessage(
            tenant_id=tenant.id,
            provider_id=provider.id,
            conversation_id=conversation.id,
            chatwoot_binding_id=binding_b.id,
            chatwoot_message_id=524,
            body="synthetic",
            direction="inbound",
            author_type="customer",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_receipt_is_scoped_to_connection_and_uses_structural_fields_only(db_session):
    tenant, _ = _tenant_provider(db_session, "receipt")
    connection_a = _connection(db_session, tenant, 600)
    connection_b = _connection(db_session, tenant, 601)
    delivery_id = UUID("12345678-1234-4234-9234-123456789abc")
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            ChatwootWebhookReceipt(
                connection_id=connection_a.id,
                delivery_id=delivery_id,
                event_type="message_created",
                outcome="accepted",
                webhook_timestamp=now,
            ),
            ChatwootWebhookReceipt(
                connection_id=connection_b.id,
                delivery_id=delivery_id,
                event_type="message_created",
                outcome="accepted",
                webhook_timestamp=now,
            ),
        ]
    )
    db_session.commit()

    db_session.add(
        ChatwootWebhookReceipt(
            connection_id=connection_a.id,
            delivery_id=delivery_id,
            event_type="message_created",
            outcome="duplicate",
            webhook_timestamp=now,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_connection_schemas_are_disabled_first_canonical_and_secret_safe():
    create = ChatwootConnectionCreate(
        instance_origin="HTTPS://Chatwoot.Example.Test:443/",
        chatwoot_account_id=700,
    )
    assert create.instance_origin == "https://chatwoot.example.test"
    assert create.enabled is False
    with pytest.raises(ValidationError):
        ChatwootConnectionCreate(
            instance_origin="https://chatwoot.example.test/path?token=forbidden",
            chatwoot_account_id=700,
        )
    with pytest.raises(ValidationError):
        ChatwootConnectionCreate(
            instance_origin="https://chatwoot.example.test",
            chatwoot_account_id=700,
            enabled=True,
        )

    synthetic_secret = "synthetic-signing-secret-value-123456"
    rotation = ChatwootSigningSecretRotate(signing_secret=synthetic_secret)
    assert synthetic_secret not in repr(rotation)
    assert synthetic_secret not in str(rotation.model_dump())
    assert (
        ChatwootSigningSecretRotate.model_json_schema()["properties"][
            "signing_secret"
        ]["writeOnly"]
        is True
    )
    with pytest.raises(ValidationError):
        ChatwootSigningSecretRotate(signing_secret=" " * 32)

    response = ChatwootConnectionResponse(
        id=1,
        public_id=UUID("12345678-1234-4234-9234-123456789abc"),
        tenant_id=2,
        instance_origin="https://chatwoot.example.test",
        chatwoot_account_id=700,
        enabled=False,
        has_signing_secret=True,
        webhook_path="/api/messaging/chatwoot/webhooks/12345678-1234-4234-9234-123456789abc",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    dumped = response.model_dump()
    assert dumped["webhook_path"].startswith("/api/")
    assert all(
        forbidden not in key
        for key in dumped
        for forbidden in ("cipher", "token", "secret")
        if key != "has_signing_secret"
    )


def test_inbox_schemas_keep_identity_immutable_and_web_widget_only():
    create = ChatwootInboxBindingCreate(
        connection_id=1,
        provider_id=2,
        chatwoot_inbox_id=3,
    )
    assert create.channel == "web_widget"
    assert create.ingress_enabled is False
    assert "is_enabled" not in ChatwootInboxBindingCreate.model_fields
    with pytest.raises(ValidationError):
        ChatwootInboxBindingCreate(
            connection_id=1,
            provider_id=2,
            chatwoot_inbox_id=3,
            channel="sms",
        )
    assert set(ChatwootInboxBindingUpdate.model_fields) == {"ingress_enabled"}
    assert {
        "connection_id",
        "provider_id",
        "chatwoot_inbox_id",
        "channel",
    }.isdisjoint(ChatwootConnectionUpdate.model_fields)
    assert set(ChatwootConnectionUpdate.model_fields) == {"enabled"}
    with pytest.raises(ValidationError):
        ChatwootConnectionUpdate(
            enabled=False,
            chatwoot_account_id=999,
        )
    with pytest.raises(ValidationError):
        ChatwootInboxBindingUpdate(
            ingress_enabled=False,
            chatwoot_inbox_id=999,
        )
    assert "webhook_secret" not in ChatwootInboxBindingResponse.model_fields
    assert "chatwoot_api_token" not in ChatwootInboxBindingResponse.model_fields


def test_schema_export_surface_has_no_plaintext_legacy_credentials():
    forbidden_fields = {"chatwoot_api_token", "webhook_secret"}
    assert not {
        "SmsChatwootBindingBase",
        "SmsChatwootBindingCreate",
        "SmsChatwootBindingUpdate",
        "SmsChatwootBindingResponse",
    }.intersection(vars(chatwoot_schemas))

    assert set(chatwoot_schemas.__all__) == {
        "ChatwootConnectionCreate",
        "ChatwootConnectionUpdate",
        "ChatwootSigningSecretRotate",
        "ChatwootConnectionResponse",
        "ChatwootInboxBindingCreate",
        "ChatwootInboxBindingUpdate",
        "ChatwootInboxBindingResponse",
    }
    for schema_name in chatwoot_schemas.__all__:
        schema = getattr(chatwoot_schemas, schema_name)
        assert forbidden_fields.isdisjoint(schema.model_fields)

    signing_secret_field = ChatwootSigningSecretRotate.model_fields[
        "signing_secret"
    ]
    assert signing_secret_field.annotation is SecretStr


def test_schema_tables_exist_in_sqlite_create_all(db_session):
    table_names = set(inspect(db_session.bind).get_table_names())
    assert {"chatwoot_connections", "chatwoot_webhook_receipts"} <= table_names

    receipt_fks = inspect(db_session.bind).get_foreign_keys(
        "chatwoot_webhook_receipts"
    )
    assert receipt_fks[0]["options"]["ondelete"] == "RESTRICT"
    conversation_fks = inspect(db_session.bind).get_foreign_keys("sms_conversations")
    binding_fk = next(
        fk
        for fk in conversation_fks
        if fk["name"] == "fk_sms_conversations_chatwoot_binding_tenant"
    )
    assert binding_fk["constrained_columns"] == ["chatwoot_binding_id", "tenant_id"]
    assert binding_fk["options"]["ondelete"] == "RESTRICT"


def test_message_projection_adds_only_approved_normalized_fields():
    new_fields = {
        "chatwoot_binding_id",
        "chatwoot_message_type",
        "chatwoot_content_type",
        "chatwoot_private",
        "chatwoot_sender_type",
        "chatwoot_sender_reference",
        "chatwoot_attachment_metadata",
    }
    assert new_fields <= set(SmsMessage.__table__.c.keys())
    assert {
        "channel",
        "event_type",
        "delivery_status",
        "correlation_id",
        "source_reference",
    }.isdisjoint(SmsMessage.__table__.c.keys())
