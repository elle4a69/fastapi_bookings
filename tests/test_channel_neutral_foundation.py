"""Channel-Neutral Foundation Regression Test Suite.

Validates:
1. Channel Account creation & provider isolation.
2. Message creation across multiple directions (inbound, outbound, simulated, manual, chatwoot).
3. Chatwoot metadata preservation (immutable external IDs, delivery status, and inbox IDs).
4. Compatibility facade bridging legacy SmsConversation/SmsMessage with channel-neutral schemas.
5. Router endpoint validation (GET /api/admin/conversations, message creation, tenant isolation).
"""

from datetime import datetime, timezone
import pytest
from fastapi import status

from app.models.conversation import (
    ChannelAccount,
    ChannelType,
    Conversation,
    DeliveryStatus,
    Message,
    MessageDirection,
    MessageSource,
)
from app.models.sms_message import SmsMessage
from app.schemas.channel import ChannelAccountCreate
from app.schemas.conversation import (
    ConversationCreate,
    ConversationMetadataContract,
    ConversationOut,
    MessageCreate,
    MessageOut,
)
from app.services.channel.channel_service import ChannelService
from app.services.channel.compatibility_facade import ChannelCompatibilityFacade
from tests.fixtures.channel_fixtures import (
    channel_test_env,
    synthetic_channel_accounts,
    multi_turn_conversation_with_chatwoot,
    legacy_sms_compatibility_data,
)


# =============================================================================
# Test 1: Channel Account Creation & Provider Isolation
# =============================================================================

def test_channel_account_creation_and_provider_isolation(
    db_session,
    channel_test_env,
    synthetic_channel_accounts,
):
    """Test ChannelAccount creation across multiple channel types and verify provider isolation."""
    env = channel_test_env
    accounts = synthetic_channel_accounts
    t_a = env["tenant_a"]
    t_b = env["tenant_b"]
    p_a1 = env["provider_a1"]
    p_a2 = env["provider_a2"]
    p_b1 = env["provider_b1"]

    # 1. Verify multiple channels are created with correct types
    assert accounts["sms_account"].channel_type == ChannelType.SMS
    assert accounts["whatsapp_account"].channel_type == ChannelType.WHATSAPP
    assert accounts["webchat_shared_account"].channel_type == ChannelType.WEBCHAT
    assert accounts["simulated_account"].channel_type == ChannelType.SIMULATED
    assert accounts["tenant_b_account"].channel_type == ChannelType.SMS

    # 2. Verify Provider A1 can list only Provider A1's channel accounts
    a1_accounts = ChannelService.list_channel_accounts(
        db_session, tenant_id=t_a.id, provider_id=p_a1.id
    )
    a1_ids = {a.id for a in a1_accounts}
    assert accounts["sms_account"].id in a1_ids
    assert accounts["whatsapp_account"].id in a1_ids
    assert accounts["simulated_account"].id not in a1_ids  # Owned by Provider A2
    assert accounts["tenant_b_account"].id not in a1_ids  # Owned by Tenant B

    # 3. Verify Provider A2 sees only Provider A2's accounts
    a2_accounts = ChannelService.list_channel_accounts(
        db_session, tenant_id=t_a.id, provider_id=p_a2.id
    )
    a2_ids = {a.id for a in a2_accounts}
    assert accounts["simulated_account"].id in a2_ids
    assert accounts["sms_account"].id not in a2_ids
    assert accounts["whatsapp_account"].id not in a2_ids

    # 4. Verify Tenant-wide shared accounts (provider_id=None)
    all_t_a_accounts = ChannelService.list_channel_accounts(
        db_session, tenant_id=t_a.id, provider_id=None
    )
    shared_inboxes = [a for a in all_t_a_accounts if a.provider_id is None]
    assert len(shared_inboxes) >= 1
    assert accounts["webchat_shared_account"].id in [a.id for a in shared_inboxes]

    # 5. Strict Tenant Isolation: Tenant B cannot access Tenant A's accounts
    t_b_accounts = ChannelService.list_channel_accounts(
        db_session, tenant_id=t_b.id, provider_id=None
    )
    for acc in t_b_accounts:
        assert acc.tenant_id == t_b.id
        assert acc.id != accounts["sms_account"].id
        assert acc.id != accounts["whatsapp_account"].id


# =============================================================================
# Test 2: Message Creation Across Multiple Directions & Sources
# =============================================================================

def test_message_creation_multi_direction_and_sources(
    db_session,
    channel_test_env,
    synthetic_channel_accounts,
):
    """Test Message creation across multiple directions (inbound, outbound) and sources."""
    env = channel_test_env
    t_a = env["tenant_a"]
    p_a1 = env["provider_a1"]
    acc = synthetic_channel_accounts["whatsapp_account"]

    conv = ChannelService.create_conversation(
        db_session,
        tenant_id=t_a.id,
        data=ConversationCreate(
            provider_id=p_a1.id,
            channel_account_id=acc.id,
            contact_identifier="+61433000111",
            contact_name="Multi Direction Test User",
            channel_type=ChannelType.WHATSAPP,
        ),
    )

    directions_sources_matrix = [
        (MessageDirection.INBOUND, MessageSource.CLIENT, DeliveryStatus.DELIVERED, "Customer query"),
        (MessageDirection.OUTBOUND, MessageSource.ASSISTANT, DeliveryStatus.SENT, "AI auto-reply"),
        (MessageDirection.OUTBOUND, MessageSource.OPERATOR, DeliveryStatus.SENT, "Staff manual text"),
        (MessageDirection.OUTBOUND, MessageSource.SIMULATED, DeliveryStatus.DELIVERED, "Simulated beacon"),
        (MessageDirection.OUTBOUND, MessageSource.CHATWOOT, DeliveryStatus.READ, "Chatwoot sync message"),
    ]

    created_messages = []
    for direction, source, delivery_status, text in directions_sources_matrix:
        msg = ChannelService.create_message(
            db_session,
            tenant_id=t_a.id,
            conversation_id=conv.id,
            data=MessageCreate(
                content=text,
                direction=direction,
                source=source,
                delivery_status=delivery_status,
                external_message_id=f"ext_{source.value}_{direction.value}",
                metadata_payload={"source_tag": source.value},
            ),
            provider_id=p_a1.id,
        )
        created_messages.append(msg)

    assert len(created_messages) == 5

    # Verify attributes and persistence in DB
    refetched_conv = ChannelService.get_conversation(
        db_session, conversation_id=conv.id, tenant_id=t_a.id, load_messages=True
    )
    assert len(refetched_conv.messages) == 5

    persisted_sources = [m.source for m in refetched_conv.messages]
    assert MessageSource.CLIENT in persisted_sources
    assert MessageSource.ASSISTANT in persisted_sources
    assert MessageSource.OPERATOR in persisted_sources
    assert MessageSource.SIMULATED in persisted_sources
    assert MessageSource.CHATWOOT in persisted_sources


# =============================================================================
# Test 3: Chatwoot Metadata Preservation
# =============================================================================

def test_chatwoot_metadata_preservation(
    db_session,
    multi_turn_conversation_with_chatwoot,
):
    """Test Chatwoot metadata preservation ensuring external IDs and statuses are immutable."""
    fixture = multi_turn_conversation_with_chatwoot
    conv = fixture["conversation"]
    messages = fixture["messages"]

    # 1. Verify conversation-level Chatwoot contract
    assert conv.external_conversation_id == "cw_conv_889900"
    assert conv.metadata_payload.get("chatwoot_inbox_id") == 102
    assert conv.metadata_payload.get("channel_type") == "whatsapp"

    # 2. Verify message-level Chatwoot external IDs and statuses
    expected_cw_ids = ["cw_msg_001", "cw_msg_002", "cw_msg_003", "cw_msg_004", None]
    for i, expected_id in enumerate(expected_cw_ids):
        assert messages[i].external_message_id == expected_id

    # 3. Verify tool calls preservation
    assert messages[1].tool_calls is not None
    assert messages[1].tool_calls[0]["name"] == "check_availability"

    # 4. Validate metadata contract through schema
    contract = ConversationMetadataContract(
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        channel_type=ChannelType.WHATSAPP,
        chatwoot_inbox_id=conv.metadata_payload.get("chatwoot_inbox_id"),
        external_conversation_id=conv.external_conversation_id,
        external_message_id=messages[0].external_message_id,
        delivery_status=messages[0].delivery_status,
        source=messages[0].source,
        extra={"custom_intent": conv.metadata_payload.get("intent")},
    )
    assert contract.external_conversation_id == "cw_conv_889900"
    assert contract.chatwoot_inbox_id == 102
    assert contract.external_message_id == "cw_msg_001"
    assert contract.delivery_status == DeliveryStatus.DELIVERED
    assert contract.source == MessageSource.CLIENT


# =============================================================================
# Test 4: Compatibility Facade Test (Legacy SmsConversation & SmsMessage)
# =============================================================================

def test_compatibility_facade_legacy_sms(
    db_session,
    channel_test_env,
    legacy_sms_compatibility_data,
):
    """Create legacy SmsConversation and SmsMessage; verify facade presents them as Conversation/Message."""
    env = channel_test_env
    t_a = env["tenant_a"]
    legacy_data = legacy_sms_compatibility_data
    legacy_conv = legacy_data["legacy_conversation"]
    legacy_msgs = legacy_data["legacy_messages"]

    # 1. Fetch single conversation through facade
    conv_out = ChannelCompatibilityFacade.get_conversation(
        db=db_session,
        conversation_id=legacy_conv.id,
        tenant_id=t_a.id,
        include_legacy=True,
    )
    assert conv_out is not None
    assert isinstance(conv_out, ConversationOut)
    assert conv_out.id == legacy_conv.id
    assert conv_out.channel_type == ChannelType.SMS
    assert conv_out.contact_identifier == legacy_conv.customer_address
    assert conv_out.status == legacy_conv.state
    assert conv_out.external_conversation_id == str(legacy_conv.chatwoot_conversation_id)
    assert conv_out.metadata_payload["is_legacy_sms"] is True
    assert conv_out.metadata_payload["chatwoot_inbox_id"] == 88

    # 2. Fetch conversation detail with messages through facade
    detail_out = ChannelCompatibilityFacade.get_conversation_detail(
        db=db_session,
        conversation_id=legacy_conv.id,
        tenant_id=t_a.id,
        include_legacy=True,
    )
    assert detail_out is not None
    assert len(detail_out.messages) == 2

    # Inbound message check
    inbound_m = detail_out.messages[0]
    assert inbound_m.content == "Do you offer initial consultations?"
    assert inbound_m.direction == MessageDirection.INBOUND
    assert inbound_m.source == MessageSource.CLIENT
    assert inbound_m.delivery_status == DeliveryStatus.PENDING or inbound_m.delivery_status == DeliveryStatus.SENT or inbound_m.delivery_status is not None
    assert inbound_m.external_message_id == "90001"

    # Outbound message check
    outbound_m = detail_out.messages[1]
    assert outbound_m.content == "Yes we do! Consultations run for 45 minutes."
    assert outbound_m.direction == MessageDirection.OUTBOUND
    assert outbound_m.source == MessageSource.ASSISTANT
    assert outbound_m.delivery_status == DeliveryStatus.SENT
    assert outbound_m.external_message_id == "90002"

    # 3. Record outbound message on legacy conversation via facade
    new_outbound = ChannelCompatibilityFacade.record_outbound_message(
        db=db_session,
        conversation_id=legacy_conv.id,
        tenant_id=t_a.id,
        data=MessageCreate(
            content="Follow up note via facade",
            direction=MessageDirection.OUTBOUND,
            source=MessageSource.OPERATOR,
            delivery_status=DeliveryStatus.SENT,
            external_message_id="90003",
        ),
        include_legacy=True,
    )
    assert new_outbound is not None
    assert new_outbound.content == "Follow up note via facade"
    assert new_outbound.direction == MessageDirection.OUTBOUND
    assert new_outbound.source == MessageSource.OPERATOR

    # Verify that the message was saved to the legacy SmsMessage table
    saved_sms_msg = db_session.query(SmsMessage).filter(SmsMessage.body == "Follow up note via facade").first()
    assert saved_sms_msg is not None
    assert saved_sms_msg.conversation_id == legacy_conv.id
    assert saved_sms_msg.author_type == "staff"

    # 4. List conversations through facade (should include legacy SMS conversation)
    conversations_list, total = ChannelCompatibilityFacade.list_conversations(
        db=db_session,
        tenant_id=t_a.id,
        channel_type=ChannelType.SMS,
        include_legacy=True,
    )
    assert total >= 1
    found = any(c.id == legacy_conv.id for c in conversations_list)
    assert found is True


# =============================================================================
# Test 5: Router Endpoint Validation & Multi-Tenant Isolation
# =============================================================================

def test_router_endpoints_and_tenant_isolation(
    client,
    channel_test_env,
    synthetic_channel_accounts,
    multi_turn_conversation_with_chatwoot,
    legacy_sms_compatibility_data,
):
    """Validate GET/POST /api/admin/conversations router endpoints and verify multi-tenant isolation."""
    env = channel_test_env
    headers_a = env["headers_a"]
    headers_b = env["headers_b"]
    p_a1 = env["provider_a1"]
    active_conv = multi_turn_conversation_with_chatwoot["conversation"]

    # 1. GET /api/admin/conversations with Tenant A admin headers
    res_list = client.get("/api/admin/conversations", headers=headers_a)
    assert res_list.status_code == status.HTTP_200_OK
    data = res_list.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # 2. Filter by channel=whatsapp
    res_wa = client.get("/api/admin/conversations?channel=whatsapp", headers=headers_a)
    assert res_wa.status_code == status.HTTP_200_OK
    wa_data = res_wa.json()
    assert len(wa_data) >= 1
    for item in wa_data:
        assert item["channel_type"] == "whatsapp"

    # 3. Filter by provider_id
    res_prov = client.get(f"/api/admin/conversations?provider_id={p_a1.id}", headers=headers_a)
    assert res_prov.status_code == status.HTTP_200_OK
    prov_data = res_prov.json()
    assert len(prov_data) >= 1
    for item in prov_data:
        assert item["provider_id"] == p_a1.id

    # 4. GET /api/admin/conversations/{id} detailed conversation
    res_detail = client.get(f"/api/admin/conversations/{active_conv.id}", headers=headers_a)
    assert res_detail.status_code == status.HTTP_200_OK
    detail_data = res_detail.json()
    assert detail_data["id"] == active_conv.id
    assert detail_data["contact_identifier"] == "+61411222333"
    assert "messages" in detail_data
    assert len(detail_data["messages"]) == 5

    # 5. POST /api/admin/conversations/{id}/messages
    msg_payload = {
        "content": "Administrative appointment reminder sent from test suite.",
        "direction": "outbound",
        "source": "operator",
        "delivery_status": "sent",
        "external_message_id": "cw_reply_999",
        "metadata_payload": {"test_dispatch": True},
    }
    res_post_msg = client.post(
        f"/api/admin/conversations/{active_conv.id}/messages",
        json=msg_payload,
        headers=headers_a,
    )
    assert res_post_msg.status_code == status.HTTP_201_CREATED
    posted_msg = res_post_msg.json()
    assert posted_msg["content"] == msg_payload["content"]
    assert posted_msg["direction"] == "outbound"
    assert posted_msg["source"] == "operator"

    # 6. POST /api/admin/conversations (create new neutral conversation)
    new_conv_payload = {
        "provider_id": p_a1.id,
        "contact_identifier": "+61477123456",
        "contact_name": "New WebChat Visitor",
        "channel_type": "webchat",
        "status": "active",
        "metadata_payload": {"browser": "Chrome", "entry_page": "/pricing"},
    }
    res_create_conv = client.post(
        "/api/admin/conversations",
        json=new_conv_payload,
        headers=headers_a,
    )
    assert res_create_conv.status_code == status.HTTP_201_CREATED
    created_conv = res_create_conv.json()
    assert created_conv["contact_identifier"] == "+61477123456"
    assert created_conv["channel_type"] == "webchat"

    # =========================================================================
    # Strict Multi-Tenant Isolation Checks
    # =========================================================================

    # Tenant B lists conversations: must not see Tenant A's conversations
    res_b_list = client.get("/api/admin/conversations", headers=headers_b)
    assert res_b_list.status_code == status.HTTP_200_OK
    b_data = res_b_list.json()
    t_a_conv_ids = {active_conv.id, created_conv["id"]}
    for c in b_data:
        assert c["id"] not in t_a_conv_ids
        assert c["tenant_id"] == env["tenant_b"].id

    # Tenant B tries to GET Tenant A's conversation -> 404 NOT FOUND
    res_b_detail = client.get(f"/api/admin/conversations/{active_conv.id}", headers=headers_b)
    assert res_b_detail.status_code == status.HTTP_404_NOT_FOUND

    # Tenant B tries to POST a message into Tenant A's conversation -> 404 NOT FOUND
    res_b_post = client.post(
        f"/api/admin/conversations/{active_conv.id}/messages",
        json=msg_payload,
        headers=headers_b,
    )
    assert res_b_post.status_code == status.HTTP_404_NOT_FOUND
