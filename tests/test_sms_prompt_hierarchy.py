import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile
from app.models.user import User

from app.services.sms.ai_orchestrator import run_ai_orchestration
from app.core.security import create_access_token

@pytest.fixture
def setup_hierarchy_test_data(db_session):
    # 1. Tenant
    tenant = Tenant(name="Hierarchy Test Tenant", subdomain="hierarchy-test")
    db_session.add(tenant)
    db_session.commit()

    # 2. Admin User
    admin = User(tenant_id=tenant.id, login="admin@hierarchytest.com", password_hash="hash", role="admin")
    db_session.add(admin)
    db_session.commit()

    # 3. Two Providers
    prov_a = Provider(tenant_id=tenant.id, name="Dr. Alice", active=True)
    prov_b = Provider(tenant_id=tenant.id, name="Dr. Bob", active=True)
    db_session.add_all([prov_a, prov_b])
    db_session.commit()

    # 4. Two SMS Accounts
    acc_a = SmsAccount(
        tenant_id=tenant.id,
        provider_id=prov_a.id,
        transport_type="simulator",
        display_name="Line Alice",
        sender_address="61400000001",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="autopilot"
    )
    acc_b = SmsAccount(
        tenant_id=tenant.id,
        provider_id=prov_b.id,
        transport_type="simulator",
        display_name="Line Bob",
        sender_address="61400000002",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="autopilot"
    )
    db_session.add_all([acc_a, acc_b])
    db_session.commit()

    # 5. Two Conversations
    conv_a = SmsConversation(
        tenant_id=tenant.id,
        provider_id=prov_a.id,
        sms_account_id=acc_a.id,
        customer_address="61411111111",
        state="auto-reply",
        unread_count=0
    )
    conv_b = SmsConversation(
        tenant_id=tenant.id,
        provider_id=prov_b.id,
        sms_account_id=acc_b.id,
        customer_address="61422222222",
        state="auto-reply",
        unread_count=0
    )
    db_session.add_all([conv_a, conv_b])
    db_session.commit()

    # 6. Global Prompt Profile (Active)
    gp_1 = SmsPromptProfile(
        tenant_id=tenant.id,
        provider_id=None,
        name="Global Safety Rules",
        system_prompt="Global prompt: Be polite and secure.",
        is_active=True
    )
    # 7. Provider A Prompt Profile (Active)
    pp_a = SmsPromptProfile(
        tenant_id=tenant.id,
        provider_id=prov_a.id,
        name="Alice Prompt Instructions",
        system_prompt="Provider Instructions A: You are Dr. Alice.",
        is_active=True
    )
    # 8. Provider B Prompt Profile (Active)
    pp_b = SmsPromptProfile(
        tenant_id=tenant.id,
        provider_id=prov_b.id,
        name="Bob Prompt Instructions",
        system_prompt="Provider Instructions B: You are Dr. Bob.",
        is_active=True
    )
    db_session.add_all([gp_1, pp_a, pp_b])
    db_session.commit()

    # 9. Knowledge Entries
    # Shared approved
    sk_1 = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=None,
        category="policy",
        text="Shared approved: No refund policy.",
        status="approved"
    )
    # Shared proposed (should be excluded)
    sk_proposed = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=None,
        category="faq",
        text="Shared proposed fact.",
        status="proposed"
    )
    # Scoped approved Provider A
    pk_a = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=prov_a.id,
        category="location",
        text="Provider A approved: Alice Room 1.",
        status="approved"
    )
    # Scoped proposed Provider A (should be excluded)
    pk_a_proposed = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=prov_a.id,
        category="faq",
        text="Provider A proposed fact.",
        status="proposed"
    )
    # Scoped approved Provider B
    pk_b = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=prov_b.id,
        category="location",
        text="Provider B approved: Bob Room 2.",
        status="approved"
    )
    db_session.add_all([sk_1, sk_proposed, pk_a, pk_a_proposed, pk_b])
    db_session.commit()

    # 10. Messages history
    msg_prior_a = SmsMessage(
        tenant_id=tenant.id,
        provider_id=prov_a.id,
        sms_account_id=acc_a.id,
        conversation_id=conv_a.id,
        body="Prior message A",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-prior",
        occurred_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        received_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    db_session.add(msg_prior_a)
    db_session.commit()

    return {
        "tenant": tenant,
        "admin": admin,
        "prov_a": prov_a,
        "prov_b": prov_b,
        "acc_a": acc_a,
        "acc_b": acc_b,
        "conv_a": conv_a,
        "conv_b": conv_b,
        "gp_1": gp_1,
        "pp_a": pp_a,
        "pp_b": pp_b,
        "sk_1": sk_1,
        "pk_a": pk_a,
        "pk_b": pk_b,
        "msg_prior_a": msg_prior_a,
        "headers": {
            "X-Tenant": "hierarchy-test",
            "X-Token": create_access_token({"sub": str(admin.id)}),
        }
    }

def test_exact_7_layer_ordering_and_isolation(db_session, setup_hierarchy_test_data):
    data = setup_hierarchy_test_data
    acc_a = data["acc_a"]
    conv_a = data["conv_a"]
    acc_a.credentials = {"api_key": "sk-test-mock-key"}
    
    # Add a distinct current turn message
    msg_current_a = SmsMessage(
        tenant_id=data["tenant"].id,
        provider_id=data["prov_a"].id,
        sms_account_id=acc_a.id,
        conversation_id=conv_a.id,
        body="Current message A",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-current",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db_session.add(msg_current_a)
    db_session.commit()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Mocked AI reply"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        mock_client.post.return_value = mock_resp

        # Call the orchestrator
        import asyncio
        asyncio.run(run_ai_orchestration(db_session, acc_a, conv_a, "turn-current"))

        mock_client.post.assert_called_once()
        payload = mock_client.post.call_args[1]["json"]
        messages = payload["messages"]

        # Exact 7 layers check
        assert len(messages) == 7

        # Layer 1: Immutable Safety Rules
        assert "Immutable Platform Safety Rules" in messages[0]["content"]

        # Layer 2: Exactly one active tenant-wide Global System Prompt
        assert messages[1]["content"] == "Global prompt: Be polite and secure."

        # Layer 3: Provider A prompt / Provider Instructions
        assert messages[2]["content"] == "Provider Instructions A: You are Dr. Alice."

        # Layer 4: Approved Shared Knowledge entries
        assert any("Shared approved: No refund policy." in m["content"] for m in messages[3:5])

        # Layer 5: Approved Knowledge entries scoped to the active provider
        assert any("Provider A approved: Alice Room 1." in m["content"] for m in messages[3:5])

        # Layer 6: Chronological conversation history
        assert messages[5]["role"] == "user"
        assert messages[5]["content"] == "Prior message A"

        # Layer 7: The current inbound customer message
        assert messages[6]["role"] == "user"
        assert messages[6]["content"] == "Current message A"

        # Assert that current turn does not duplicate history
        assert messages[5]["content"] != messages[6]["content"]

        # Verify no provider cross-talk / leakage:
        all_contents = [m["content"] for m in messages]
        assert "Provider Instructions B: You are Dr. Bob." not in all_contents
        assert "Provider B approved: Bob Room 2." not in all_contents

        # Verify proposed knowledge entries are excluded
        assert "Shared proposed fact." not in all_contents
        assert "Provider A proposed fact." not in all_contents

def test_global_prompt_shared_across_providers(db_session, setup_hierarchy_test_data):
    data = setup_hierarchy_test_data
    acc_b = data["acc_b"]
    conv_b = data["conv_b"]
    acc_b.credentials = {"api_key": "sk-test-mock-key"}
    
    # Add a history message for B to ensure the turn works
    msg_prior_b = SmsMessage(
        tenant_id=data["tenant"].id,
        provider_id=data["prov_b"].id,
        sms_account_id=acc_b.id,
        conversation_id=conv_b.id,
        body="Prior message B",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-prior-b",
        occurred_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        received_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    # Add a distinct current turn message for B
    msg_current_b = SmsMessage(
        tenant_id=data["tenant"].id,
        provider_id=data["prov_b"].id,
        sms_account_id=acc_b.id,
        conversation_id=conv_b.id,
        body="Current message B",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-current-b",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db_session.add_all([msg_prior_b, msg_current_b])
    db_session.commit()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Mocked AI reply B"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        mock_client.post.return_value = mock_resp

        import asyncio
        asyncio.run(run_ai_orchestration(db_session, acc_b, conv_b, "turn-current-b"))

        mock_client.post.assert_called_once()
        payload = mock_client.post.call_args[1]["json"]
        messages = payload["messages"]

        # Exact 7 layers check
        assert len(messages) == 7

        # Layer 2: Global prompt is shared!
        assert messages[1]["content"] == "Global prompt: Be polite and secure."

        # Layer 3: Provider B prompt instructions used instead of A
        assert messages[2]["content"] == "Provider Instructions B: You are Dr. Bob."

        # Layer 5: Provider B knowledge used instead of A
        assert any("Provider B approved: Bob Room 2." in m["content"] for m in messages[3:5])

        # Layer 6: Prior messages
        assert messages[5]["role"] == "user"
        assert messages[5]["content"] == "Prior message B"

        # Layer 7: Current message
        assert messages[6]["role"] == "user"
        assert messages[6]["content"] == "Current message B"

        # Assert that current turn does not duplicate history
        assert messages[5]["content"] != messages[6]["content"]

        # No A leakage
        all_contents = [m["content"] for m in messages]
        assert "Provider Instructions A: You are Dr. Alice." not in all_contents
        assert "Provider A approved: Alice Room 1." not in all_contents

def test_activating_global_prompt_deactivates_previous(client, setup_hierarchy_test_data, db_session):
    headers = setup_hierarchy_test_data["headers"]
    gp_1 = setup_hierarchy_test_data["gp_1"]

    # Verify initial state: gp_1 is active
    assert gp_1.is_active is True

    # 1. Test POST /api/admin/sms/settings/prompts (creating a new global prompt)
    new_global_payload = {
        "name": "New Global Rules",
        "system_prompt": "New Global prompt: Strict security.",
        "provider_id": None,
        "sms_account_id": None
    }
    resp = client.post("/api/admin/sms/settings/prompts", json=new_global_payload, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    new_gp_id = resp.json()["id"]

    # Refresh gp_1 and verify it is deactivated
    db_session.refresh(gp_1)
    assert gp_1.is_active is False

    # Verify new prompt is active
    new_gp = db_session.query(SmsPromptProfile).filter(SmsPromptProfile.id == new_gp_id).first()
    assert new_gp.is_active is True

    # 2. Test PUT /api/admin/sms/settings/prompts/{id} (activating gp_1 again)
    resp_put = client.put(
        f"/api/admin/sms/settings/prompts/{gp_1.id}",
        json={"is_active": True},
        headers=headers
    )
    assert resp_put.status_code == status.HTTP_200_OK

    db_session.refresh(gp_1)
    db_session.refresh(new_gp)
    assert gp_1.is_active is True
    assert new_gp.is_active is False

def test_activating_provider_prompt_deactivates_previous(client, setup_hierarchy_test_data, db_session):
    headers = setup_hierarchy_test_data["headers"]
    prov_a = setup_hierarchy_test_data["prov_a"]
    pp_a = setup_hierarchy_test_data["pp_a"]
    pp_b = setup_hierarchy_test_data["pp_b"]

    # Verify initial states
    assert pp_a.is_active is True
    assert pp_b.is_active is True

    # 1. Create a new provider prompt for Provider A
    new_pp_payload = {
        "name": "New Alice Instructions",
        "system_prompt": "New Provider instructions A",
        "provider_id": prov_a.id,
        "sms_account_id": None
    }
    resp = client.post("/api/admin/sms/settings/prompts", json=new_pp_payload, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    new_pp_a_id = resp.json()["id"]

    # Refresh pp_a and verify it is deactivated
    db_session.refresh(pp_a)
    assert pp_a.is_active is False

    # Provider B's prompt MUST NOT be deactivated
    db_session.refresh(pp_b)
    assert pp_b.is_active is True

    # Verify new prompt is active
    new_pp_a = db_session.query(SmsPromptProfile).filter(SmsPromptProfile.id == new_pp_a_id).first()
    assert new_pp_a.is_active is True

    # 2. Test PUT /api/admin/sms/settings/prompts/{id} (activating pp_a again)
    resp_put = client.put(
        f"/api/admin/sms/settings/prompts/{pp_a.id}",
        json={"is_active": True},
        headers=headers
    )
    assert resp_put.status_code == status.HTTP_200_OK

    db_session.refresh(pp_a)
    db_session.refresh(new_pp_a)
    db_session.refresh(pp_b)
    assert pp_a.is_active is True
    assert new_pp_a.is_active is False
    assert pp_b.is_active is True
