"""Tests for Channel-Neutral Domain Models, Schemas, Services, Facade, and APIs."""

import pytest
from datetime import datetime, timezone
from fastapi import status

from app.core.security import create_access_token
from app.models.client import Client
from app.models.conversation import (
    ChannelAccount,
    ChannelType,
    Conversation,
    DeliveryStatus,
    Message,
    MessageDirection,
    MessageSource,
)
from app.models.provider import Provider
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.channel import ChannelAccountCreate, ChannelAccountOut, ChannelAccountUpdate
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationMetadataContract,
    ConversationOut,
    MessageCreate,
    MessageOut,
)
from app.services.channel.channel_service import ChannelService
from app.services.channel.compatibility_facade import ChannelCompatibilityFacade


@pytest.fixture
def setup_channel_test_data(db_session):
    # 1. Tenant
    tenant = Tenant(name="Omnichannel Salon", subdomain="omni-test")
    db_session.add(tenant)
    db_session.commit()

    # 2. Admin User
    admin = User(tenant_id=tenant.id, login="admin@omni.test", password_hash="hash", role="admin")
    db_session.add(admin)
    db_session.commit()

    # 3. Provider
    provider = Provider(tenant_id=tenant.id, name="Dr. Omnichannel", active=True)
    db_session.add(provider)
    db_session.commit()

    # 4. Client
    client = Client(tenant_id=tenant.id, name="Alice Inbound", phone="+61411222333", active=True)
    db_session.add(client)
    db_session.commit()

    return {
        "tenant": tenant,
        "admin": admin,
        "provider": provider,
        "client": client,
        "headers": {
            "X-Tenant": "omni-test",
            "X-Token": create_access_token({"sub": str(admin.id)}),
        },
    }


def test_channel_enums():
    """Verify enum members and case-insensitive lookup."""
    assert ChannelType("sms") == ChannelType.SMS
    assert ChannelType("SMS") == ChannelType.SMS
    assert ChannelType("whatsapp") == ChannelType.WHATSAPP
    assert ChannelType("INSTAGRAM") == ChannelType.INSTAGRAM

    assert MessageDirection("inbound") == MessageDirection.INBOUND
    assert MessageDirection("OUTBOUND") == MessageDirection.OUTBOUND

    assert MessageSource("client") == MessageSource.CLIENT
    assert MessageSource("OPERATOR") == MessageSource.OPERATOR
    assert MessageSource("CHATWOOT") == MessageSource.CHATWOOT

    assert DeliveryStatus("sent") == DeliveryStatus.SENT
    assert DeliveryStatus("DELIVERED") == DeliveryStatus.DELIVERED


def test_channel_account_encrypted_credentials(db_session, setup_channel_test_data):
    """Verify credential encryption and transparent decryption property."""
    tenant = setup_channel_test_data["tenant"]

    account = ChannelAccount(
        tenant_id=tenant.id,
        channel_type=ChannelType.WHATSAPP,
        inbox_name="WhatsApp Official",
        account_identifier="+61499888777",
        chatwoot_inbox_id=42,
    )
    secret_creds = {"api_key": "wa_live_secret_123", "webhook_secret": "wh_sec_999"}
    account.credentials = secret_creds
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    assert account.id is not None
    # Underlying encrypted_data column must not expose plaintext
    assert "encrypted_data" in account.credentials_encrypted
    assert "wa_live_secret_123" not in str(account.credentials_encrypted)
    # Property getter decrypts correctly
    assert account.credentials == secret_creds


def test_channel_service_account_lifecycle(db_session, setup_channel_test_data):
    """Verify ChannelService CRUD for ChannelAccounts."""
    tenant = setup_channel_test_data["tenant"]
    provider = setup_channel_test_data["provider"]

    create_data = ChannelAccountCreate(
        provider_id=provider.id,
        channel_type=ChannelType.INSTAGRAM,
        inbox_name="IG Main",
        account_identifier="@omni_salon",
        chatwoot_inbox_id=101,
        credentials={"access_token": "token_abc"},
    )
    account = ChannelService.create_channel_account(db_session, tenant_id=tenant.id, data=create_data)
    assert account.id is not None
    assert account.channel_type == ChannelType.INSTAGRAM
    assert account.credentials == {"access_token": "token_abc"}

    fetched = ChannelService.get_channel_account(db_session, account.id, tenant_id=tenant.id)
    assert fetched is not None
    assert fetched.account_identifier == "@omni_salon"

    # Update
    updated = ChannelService.update_channel_account(
        db_session,
        account_id=account.id,
        tenant_id=tenant.id,
        data=ChannelAccountUpdate(inbox_name="IG Official Main"),
    )
    assert updated.inbox_name == "IG Official Main"

    # List
    accounts = ChannelService.list_channel_accounts(
        db_session, tenant_id=tenant.id, channel_type=ChannelType.INSTAGRAM
    )
    assert len(accounts) == 1
    assert accounts[0].id == account.id


def test_channel_service_conversation_and_messages(db_session, setup_channel_test_data):
    """Verify ChannelService creation and retrieval of conversations and messages."""
    tenant = setup_channel_test_data["tenant"]
    provider = setup_channel_test_data["provider"]

    # 1. Create channel account
    acc = ChannelAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        channel_type=ChannelType.SMS,
        inbox_name="Front Desk SMS",
        account_identifier="+61400000000",
    )
    db_session.add(acc)
    db_session.commit()

    # 2. Create conversation
    conv_data = ConversationCreate(
        channel_account_id=acc.id,
        provider_id=provider.id,
        contact_identifier="+61412345678",
        contact_name="Alice Inbound",
        external_conversation_id="cw_conv_777",
        metadata_payload={"custom_tag": "vip"},
    )
    conv = ChannelService.create_conversation(db_session, tenant_id=tenant.id, data=conv_data)
    assert conv.id is not None
    assert conv.status == "active"
    assert conv.channel_type == ChannelType.SMS

    # 3. Add message
    msg_data = MessageCreate(
        content="Welcome to our salon!",
        direction=MessageDirection.OUTBOUND,
        source=MessageSource.OPERATOR,
        delivery_status=DeliveryStatus.SENT,
        external_message_id="ext_msg_888",
        metadata_payload={"source_worker": "test"},
    )
    msg = ChannelService.create_message(
        db_session, tenant_id=tenant.id, conversation_id=conv.id, data=msg_data
    )
    assert msg.id is not None
    assert msg.content == "Welcome to our salon!"

    # 4. Fetch messages
    messages = ChannelService.get_messages(db_session, conversation_id=conv.id, tenant_id=tenant.id)
    assert len(messages) == 1
    assert messages[0].external_message_id == "ext_msg_888"

    # 5. Update delivery status
    updated_msg = ChannelService.update_delivery_status(
        db_session, message_id=msg.id, status=DeliveryStatus.DELIVERED, tenant_id=tenant.id
    )
    assert updated_msg.delivery_status == DeliveryStatus.DELIVERED


def test_metadata_contract():
    """Verify ConversationMetadataContract preserves all integration attributes."""
    contract = ConversationMetadataContract(
        tenant_id=1,
        provider_id=2,
        channel_type=ChannelType.WHATSAPP,
        chatwoot_inbox_id=10,
        external_conversation_id="cw_99",
        external_message_id="wam_123",
        delivery_status=DeliveryStatus.READ,
        source=MessageSource.CLIENT,
        extra={"ip": "127.0.0.1"},
    )
    dumped = contract.model_dump()
    assert dumped["tenant_id"] == 1
    assert dumped["channel_type"] == "whatsapp"
    assert dumped["delivery_status"] == "read"
    assert dumped["source"] == "client"


def test_compatibility_facade_with_legacy_sms(db_session, setup_channel_test_data):
    """Verify ChannelCompatibilityFacade transparently adapts legacy SmsConversation and SmsMessage."""
    tenant = setup_channel_test_data["tenant"]
    provider = setup_channel_test_data["provider"]
    client = setup_channel_test_data["client"]

    # 1. Create legacy SmsAccount
    sms_acc = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Legacy Line",
        sender_address="61411111111",
        is_enabled=True,
    )
    db_session.add(sms_acc)
    db_session.commit()

    # 2. Create legacy SmsConversation
    sms_conv = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=sms_acc.id,
        customer_address=client.phone,
        client_id=client.id,
        state="auto-reply",
        chatwoot_conversation_id=555,
        chatwoot_inbox_id=12,
    )
    db_session.add(sms_conv)
    db_session.commit()

    # 3. Create legacy SmsMessage
    sms_msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=sms_acc.id,
        conversation_id=sms_conv.id,
        body="Legacy SMS message body",
        direction="inbound",
        author_type="customer",
        status="delivered",
        provider_message_id="telnyx_001",
    )
    db_session.add(sms_msg)
    db_session.commit()

    # 4. Read through facade
    adapted_conv = ChannelCompatibilityFacade.get_conversation(
        db_session, conversation_id=sms_conv.id, tenant_id=tenant.id, include_legacy=True
    )
    assert adapted_conv is not None
    assert adapted_conv.id == sms_conv.id
    assert adapted_conv.channel_type == ChannelType.SMS
    assert adapted_conv.contact_identifier == client.phone
    assert adapted_conv.contact_name == client.name
    assert adapted_conv.metadata_payload["is_legacy_sms"] is True

    # 5. Read detail with messages through facade
    detail = ChannelCompatibilityFacade.get_conversation_detail(
        db_session, conversation_id=sms_conv.id, tenant_id=tenant.id, include_legacy=True
    )
    assert detail is not None
    assert len(detail.messages) == 1
    assert detail.messages[0].content == "Legacy SMS message body"
    assert detail.messages[0].direction == MessageDirection.INBOUND
    assert detail.messages[0].source == MessageSource.CLIENT
    assert detail.messages[0].delivery_status == DeliveryStatus.DELIVERED
    assert detail.messages[0].external_message_id == "telnyx_001"

    # 6. Send outbound message on legacy conversation via facade
    out_payload = MessageCreate(
        content="Replying via facade",
        direction=MessageDirection.OUTBOUND,
        source=MessageSource.OPERATOR,
        delivery_status=DeliveryStatus.SENT,
        external_message_id="sim_999",
    )
    recorded_msg = ChannelCompatibilityFacade.record_outbound_message(
        db_session,
        conversation_id=sms_conv.id,
        tenant_id=tenant.id,
        data=out_payload,
        include_legacy=True,
    )
    assert recorded_msg is not None
    assert recorded_msg.content == "Replying via facade"
    assert recorded_msg.direction == MessageDirection.OUTBOUND
    assert recorded_msg.source == MessageSource.OPERATOR

    # Verify message was stored in legacy SmsMessage table
    saved_sms_msg = (
        db_session.query(SmsMessage)
        .filter(SmsMessage.conversation_id == sms_conv.id, SmsMessage.body == "Replying via facade")
        .first()
    )
    assert saved_sms_msg is not None
    assert saved_sms_msg.author_type == "staff"


def test_api_list_and_get_conversations(client, setup_channel_test_data, db_session):
    """Test GET /api/admin/conversations and GET /api/admin/conversations/{id}."""
    headers = setup_channel_test_data["headers"]
    tenant = setup_channel_test_data["tenant"]
    provider = setup_channel_test_data["provider"]

    # 1. Create a neutral ChannelAccount and Conversation
    account = ChannelAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        channel_type=ChannelType.WHATSAPP,
        inbox_name="WhatsApp VIP",
        account_identifier="+61499990000",
    )
    db_session.add(account)
    db_session.commit()

    conv = Conversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        channel_account_id=account.id,
        contact_identifier="+61422334455",
        contact_name="Bob Omnichannel",
        status="active",
        metadata_payload={"channel_type": "whatsapp"},
    )
    db_session.add(conv)
    db_session.commit()

    # 2. List conversations API
    res = client.get("/api/admin/conversations", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    items = res.json()
    assert isinstance(items, list)
    assert any(c["contact_identifier"] == "+61422334455" for c in items)

    # 3. Filter by channel=whatsapp
    res_filtered = client.get("/api/admin/conversations?channel=whatsapp", headers=headers)
    assert res_filtered.status_code == status.HTTP_200_OK
    whatsapp_items = res_filtered.json()
    assert all(c["channel_type"] == "whatsapp" for c in whatsapp_items)

    # 4. Get conversation detail API
    detail_res = client.get(f"/api/admin/conversations/{conv.id}", headers=headers)
    assert detail_res.status_code == status.HTTP_200_OK
    detail_data = detail_res.json()
    assert detail_data["id"] == conv.id
    assert detail_data["contact_identifier"] == "+61422334455"
    assert "messages" in detail_data


def test_api_send_message(client, setup_channel_test_data, db_session):
    """Test POST /api/admin/conversations/{id}/messages."""
    headers = setup_channel_test_data["headers"]
    tenant = setup_channel_test_data["tenant"]

    conv = Conversation(
        tenant_id=tenant.id,
        contact_identifier="+61488889999",
        contact_name="Charlie Test",
        status="active",
    )
    db_session.add(conv)
    db_session.commit()

    payload = {
        "content": "Hello Charlie from the admin API!",
        "direction": "outbound",
        "source": "operator",
        "delivery_status": "sent",
        "metadata_payload": {"ticket_id": "T-100"},
    }
    res = client.post(f"/api/admin/conversations/{conv.id}/messages", headers=headers, json=payload)
    assert res.status_code == status.HTTP_201_CREATED
    msg_data = res.json()
    assert msg_data["content"] == "Hello Charlie from the admin API!"
    assert msg_data["conversation_id"] == conv.id
    assert msg_data["source"] == "operator"

    # Verify message appears in GET /api/admin/conversations/{id}
    detail_res = client.get(f"/api/admin/conversations/{conv.id}", headers=headers)
    assert detail_res.status_code == status.HTTP_200_OK
    messages = detail_res.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello Charlie from the admin API!"


def test_tenant_isolation(client, setup_channel_test_data, db_session):
    """Verify that conversations cannot be accessed across tenant boundaries."""
    headers = setup_channel_test_data["headers"]

    # Create another tenant and conversation
    other_tenant = Tenant(name="Other Tenant", subdomain="other-tenant")
    db_session.add(other_tenant)
    db_session.commit()

    other_conv = Conversation(
        tenant_id=other_tenant.id,
        contact_identifier="+61400112233",
        status="active",
    )
    db_session.add(other_conv)
    db_session.commit()

    # Attempt to retrieve other_tenant's conversation using omni-test tenant headers
    res = client.get(f"/api/admin/conversations/{other_conv.id}", headers=headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND
