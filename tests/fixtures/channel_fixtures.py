"""Deterministic Test Fixtures for Channel-Neutral Messaging & Compatibility.

Provides reusable synthetic fixtures for omnichannel accounts, conversations,
multi-turn messages with Chatwoot metadata, and legacy SMS compatibility.
"""

from datetime import datetime, timezone
import pytest

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


@pytest.fixture
def channel_test_env(db_session):
    """Base multi-tenant, multi-provider test environment."""
    # Tenant A (Primary test tenant)
    tenant_a = Tenant(name="Omni Tenant A", subdomain="omni-a")
    # Tenant B (Isolation verification tenant)
    tenant_b = Tenant(name="Omni Tenant B", subdomain="omni-b")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    # Admin users
    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin@omni-a.com",
        password_hash="fake_hash_a",
        role="admin",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin@omni-b.com",
        password_hash="fake_hash_b",
        role="admin",
    )
    db_session.add_all([admin_a, admin_b])
    db_session.commit()

    # Providers in Tenant A
    provider_a1 = Provider(tenant_id=tenant_a.id, name="Dr. Alice Smith", active=True)
    provider_a2 = Provider(tenant_id=tenant_a.id, name="Dr. Bob Jones", active=True)
    # Provider in Tenant B
    provider_b1 = Provider(tenant_id=tenant_b.id, name="Dr. Charlie Brown", active=True)
    db_session.add_all([provider_a1, provider_a2, provider_b1])
    db_session.commit()

    # Clients
    client_a = Client(
        tenant_id=tenant_a.id,
        name="Samantha Client",
        phone="+61411222333",
        email="samantha@example.com",
        active=True,
    )
    client_b = Client(
        tenant_id=tenant_b.id,
        name="David TenantB Client",
        phone="+61499888777",
        email="david@example.com",
        active=True,
    )
    db_session.add_all([client_a, client_b])
    db_session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "provider_a1": provider_a1,
        "provider_a2": provider_a2,
        "provider_b1": provider_b1,
        "client_a": client_a,
        "client_b": client_b,
        "headers_a": {
            "X-Tenant": "omni-a",
            "X-Token": create_access_token({"sub": str(admin_a.id)}),
        },
        "headers_b": {
            "X-Tenant": "omni-b",
            "X-Token": create_access_token({"sub": str(admin_b.id)}),
        },
    }


@pytest.fixture
def synthetic_channel_accounts(db_session, channel_test_env):
    """Synthetic ChannelAccounts across multiple channels, scoped vs shared."""
    env = channel_test_env
    t_a = env["tenant_a"]
    t_b = env["tenant_b"]
    p_a1 = env["provider_a1"]
    p_a2 = env["provider_a2"]
    p_b1 = env["provider_b1"]

    # 1. SMS Channel Account (Provider-scoped for Provider A1)
    sms_acc = ChannelAccount(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        channel_type=ChannelType.SMS,
        inbox_name="Provider A1 Dedicated SMS",
        account_identifier="+61400111222",
        chatwoot_inbox_id=101,
        is_active=True,
    )

    # 2. WhatsApp Channel Account (Provider-scoped for Provider A1)
    wa_acc = ChannelAccount(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        channel_type=ChannelType.WHATSAPP,
        inbox_name="Provider A1 WhatsApp Business",
        account_identifier="+61400333444",
        chatwoot_inbox_id=102,
        is_active=True,
    )

    # 3. WebChat Channel Account (Tenant-wide Shared Inbox, provider_id=None)
    webchat_acc = ChannelAccount(
        tenant_id=t_a.id,
        provider_id=None,
        channel_type=ChannelType.WEBCHAT,
        inbox_name="Tenant A Main Website Chat",
        account_identifier="webchat_widget_omni_a",
        chatwoot_inbox_id=103,
        is_active=True,
    )

    # 4. Simulated Test Channel Account (Provider-scoped for Provider A2)
    sim_acc = ChannelAccount(
        tenant_id=t_a.id,
        provider_id=p_a2.id,
        channel_type=ChannelType.SIMULATED,
        inbox_name="Provider A2 Sandbox Simulation",
        account_identifier="sim_test_box_a2",
        chatwoot_inbox_id=None,
        is_active=True,
    )

    # 5. Isolation Account (Tenant B, Provider B1)
    tenant_b_acc = ChannelAccount(
        tenant_id=t_b.id,
        provider_id=p_b1.id,
        channel_type=ChannelType.SMS,
        inbox_name="Tenant B Isolated Inbox",
        account_identifier="+61499999000",
        chatwoot_inbox_id=201,
        is_active=True,
    )

    db_session.add_all([sms_acc, wa_acc, webchat_acc, sim_acc, tenant_b_acc])
    db_session.commit()
    for acc in [sms_acc, wa_acc, webchat_acc, sim_acc, tenant_b_acc]:
        db_session.refresh(acc)

    return {
        "sms_account": sms_acc,
        "whatsapp_account": wa_acc,
        "webchat_shared_account": webchat_acc,
        "simulated_account": sim_acc,
        "tenant_b_account": tenant_b_acc,
    }


@pytest.fixture
def multi_turn_conversation_with_chatwoot(db_session, channel_test_env, synthetic_channel_accounts):
    """Synthetic multi-turn Conversation and Message objects with Chatwoot metadata."""
    env = channel_test_env
    t_a = env["tenant_a"]
    p_a1 = env["provider_a1"]
    wa_acc = synthetic_channel_accounts["whatsapp_account"]

    # Multi-turn conversation with Chatwoot metadata
    conv = Conversation(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        channel_account_id=wa_acc.id,
        external_conversation_id="cw_conv_889900",
        contact_identifier="+61411222333",
        contact_name="Samantha Client",
        status="active",
        metadata_payload={
            "chatwoot_inbox_id": 102,
            "channel_type": "whatsapp",
            "priority": "high",
            "intent": "service_booking",
        },
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    # Turn 1: Client Inbound Inquiry
    msg1 = Message(
        conversation_id=conv.id,
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        direction=MessageDirection.INBOUND,
        source=MessageSource.CLIENT,
        content="Hello, can I book a session for Thursday at 3 PM?",
        external_message_id="cw_msg_001",
        delivery_status=DeliveryStatus.DELIVERED,
        metadata_payload={"chatwoot_msg_type": "incoming"},
    )

    # Turn 2: Assistant Autonomous Response
    msg2 = Message(
        conversation_id=conv.id,
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        direction=MessageDirection.OUTBOUND,
        source=MessageSource.ASSISTANT,
        content="Let me check Dr. Alice Smith's calendar for Thursday 3 PM.",
        external_message_id="cw_msg_002",
        delivery_status=DeliveryStatus.SENT,
        tool_calls=[{"name": "check_availability", "args": {"date": "2026-10-01", "time": "15:00"}}],
        metadata_payload={"model": "gpt-4o", "confidence": 0.98},
    )

    # Turn 3: Human Operator / Chatwoot Intervention
    msg3 = Message(
        conversation_id=conv.id,
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        direction=MessageDirection.OUTBOUND,
        source=MessageSource.CHATWOOT,
        content="Hi Samantha, Alice can see you at 3:15 PM instead if that works?",
        external_message_id="cw_msg_003",
        delivery_status=DeliveryStatus.DELIVERED,
        metadata_payload={"agent_name": "Front Desk Jenny"},
    )

    # Turn 4: Client Confirmation
    msg4 = Message(
        conversation_id=conv.id,
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        direction=MessageDirection.INBOUND,
        source=MessageSource.CLIENT,
        content="Yes, 3:15 PM is perfect. Thank you!",
        external_message_id="cw_msg_004",
        delivery_status=DeliveryStatus.READ,
        metadata_payload={"sentiment": "positive"},
    )

    # Turn 5: Simulated Validation Message
    msg5 = Message(
        conversation_id=conv.id,
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        direction=MessageDirection.OUTBOUND,
        source=MessageSource.SIMULATED,
        content="[TEST-HARNESS] Automated slot reservation simulated successfully.",
        external_message_id=None,
        delivery_status=DeliveryStatus.DELIVERED,
        metadata_payload={"simulated": True},
    )

    db_session.add_all([msg1, msg2, msg3, msg4, msg5])
    db_session.commit()
    for m in [msg1, msg2, msg3, msg4, msg5]:
        db_session.refresh(m)

    return {
        "conversation": conv,
        "messages": [msg1, msg2, msg3, msg4, msg5],
    }


@pytest.fixture
def legacy_sms_compatibility_data(db_session, channel_test_env):
    """Synthetic legacy SmsConversation and SmsMessage records for facade testing."""
    env = channel_test_env
    t_a = env["tenant_a"]
    p_a1 = env["provider_a1"]
    client_a = env["client_a"]

    # Legacy SmsAccount
    legacy_acc = SmsAccount(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        transport_type="simulator",
        display_name="Legacy Provider Line",
        sender_address="+61400555666",
        is_enabled=True,
    )
    db_session.add(legacy_acc)
    db_session.commit()
    db_session.refresh(legacy_acc)

    # Legacy SmsConversation
    legacy_conv = SmsConversation(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        sms_account_id=legacy_acc.id,
        customer_address="+61488777666",
        client_id=client_a.id,
        state="auto-reply",
        source="sms",
        unread_count=1,
        chatwoot_conversation_id=45678,
        chatwoot_inbox_id=88,
        chatwoot_contact_id=1234,
        is_pinned=False,
        is_blocked=False,
        ai_enabled=True,
    )
    db_session.add(legacy_conv)
    db_session.commit()
    db_session.refresh(legacy_conv)

    # Legacy SmsMessage 1 (inbound)
    legacy_msg1 = SmsMessage(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        sms_account_id=legacy_acc.id,
        conversation_id=legacy_conv.id,
        body="Do you offer initial consultations?",
        direction="inbound",
        author_type="customer",
        status="received",
        chatwoot_message_id=90001,
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )

    # Legacy SmsMessage 2 (outbound)
    legacy_msg2 = SmsMessage(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        sms_account_id=legacy_acc.id,
        conversation_id=legacy_conv.id,
        body="Yes we do! Consultations run for 45 minutes.",
        direction="outbound",
        author_type="ai",
        status="sent",
        chatwoot_message_id=90002,
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )

    db_session.add_all([legacy_msg1, legacy_msg2])
    db_session.commit()
    db_session.refresh(legacy_msg1)
    db_session.refresh(legacy_msg2)

    return {
        "legacy_account": legacy_acc,
        "legacy_conversation": legacy_conv,
        "legacy_messages": [legacy_msg1, legacy_msg2],
    }
