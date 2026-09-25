"""Tests for scripts.sync_mock_to_chatwoot synchronization utility."""

import pytest
from unittest.mock import patch, MagicMock
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.client import Client
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_chatwoot import SmsChatwootBinding
from scripts.sync_mock_to_chatwoot import format_e164, ChatwootClient, sync_scenarios_to_chatwoot


def test_format_e164():
    assert format_e164("0411000001") == "+61411000001"
    assert format_e164("+61411000001") == "+61411000001"
    assert format_e164("61411000001") == "+61411000001"
    assert format_e164("0411 000 002") == "+61411000002"


@patch("urllib.request.urlopen")
def test_sync_scenarios_to_chatwoot_flow(mock_urlopen, db_session):
    """Test full sync_scenarios_to_chatwoot workflow with mocked HTTP responses."""
    # 1. Setup DB state
    tenant = Tenant(name="Sync Test Tenant", subdomain="sync-test")
    db_session.add(tenant)
    db_session.commit()

    prov = Provider(tenant_id=tenant.id, name="Provider 1 - Dr. Sarah Bennett", phone="0400000001", active=True)
    db_session.add(prov)
    db_session.commit()

    client1 = Client(tenant_id=tenant.id, name="Client 1 - Alice Walker", phone="0411000001", email="client1@example.com", active=True)
    db_session.add(client1)
    db_session.commit()

    conv1 = SmsConversation(
        tenant_id=tenant.id,
        provider_id=prov.id,
        customer_address="0411000001",
        client_id=client1.id,
        state="auto-reply",
        unread_count=0
    )
    db_session.add(conv1)
    db_session.commit()

    msg1 = SmsMessage(
        tenant_id=tenant.id,
        provider_id=prov.id,
        conversation_id=conv1.id,
        body="Hello Provider 1, booking request.",
        direction="inbound",
        author_type="customer",
        status="received"
    )
    msg2 = SmsMessage(
        tenant_id=tenant.id,
        provider_id=prov.id,
        conversation_id=conv1.id,
        body="Hi Alice, booking confirmed.",
        direction="outbound",
        author_type="ai",
        status="draft"
    )
    db_session.add_all([msg1, msg2])
    db_session.commit()

    # 2. Mock urllib.request responses
    import json

    def fake_response(status=200, data=None):
        resp = MagicMock()
        resp.status = status
        resp.read.return_value = json.dumps(data or {}).encode("utf-8")
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    def urlopen_router(req, timeout=15):
        url = req.full_url
        method = req.get_method()

        if "/api/v1/profile" in url:
            return fake_response(200, {
                "id": 2,
                "name": "Frank",
                "email": "lucisano.frank@gmail.com",
                "accounts": [{"id": 2, "name": "Company Name"}]
            })
        elif "/inboxes" in url and method == "GET":
            return fake_response(200, {
                "payload": [{"id": 2, "name": "SMS Line - Provider 1", "channel_type": "Channel::Api"}]
            })
        elif "/inbox_members" in url:
            return fake_response(200, {"payload": [{"id": 2}]})
        elif "/contacts/search" in url:
            return fake_response(200, {"payload": []})
        elif "/contacts" in url and method == "POST":
            return fake_response(200, {
                "payload": {
                    "contact": {
                        "id": 7,
                        "name": "Client 1 - Alice Walker",
                        "phone_number": "+61411000001",
                        "contact_inboxes": [{"inbox": {"id": 2}, "source_id": "src-123"}]
                    }
                }
            })
        elif "/conversations" in url and method == "GET" and "/contacts/" in url:
            return fake_response(200, {"payload": []})
        elif "/conversations" in url and method == "POST":
            return fake_response(200, {"id": 8, "uuid": "uuid-8"})
        elif "/messages" in url and method == "GET":
            return fake_response(200, {"payload": []})
        elif "/messages" in url and method == "POST":
            return fake_response(200, {"id": 1001, "status": "sent"})
        return fake_response(200, {})

    mock_urlopen.side_effect = urlopen_router

    # 3. Execute sync
    result = sync_scenarios_to_chatwoot(
        chatwoot_base_url="http://127.0.0.1:3000",
        chatwoot_api_token="test-token",
        chatwoot_account_id=2,
        tenant_subdomain="sync-test",
        inbox_name="SMS Line - Provider 1",
        db=db_session
    )

    assert result["success"] is True
    assert result["chatwoot_account_id"] == 2
    assert result["chatwoot_inbox_id"] == 2

    # Check that SmsChatwootBinding was created
    binding = db_session.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.tenant_id == tenant.id,
        SmsChatwootBinding.provider_id == prov.id
    ).first()
    assert binding is not None
    assert binding.chatwoot_account_id == 2
    assert binding.chatwoot_inbox_id == 2
    assert binding.is_enabled is True
