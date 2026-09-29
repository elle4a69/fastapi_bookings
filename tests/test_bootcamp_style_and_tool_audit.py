"""Automated tests proving Style Examples Wiring, Tool-Audit Persistence, and Unified Runtime.

Covers:
1. Style examples reach the model prompt payload in both Bootcamp and Simulation.
2. Tool audit records persist in SmsBootcampMessage.meta across Bootcamp turns.
3. Studio /simulate multi-turn tool execution backed by AssistantRuntimeService.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.conversation import ChannelType
from app.models.location import Location
from app.models.message_style_example import MessageStyleExample
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.sms_bootcamp import (
    SmsBootcampConversation,
    SmsBootcampMessage,
    SmsBootcampRun,
    SmsBootcampSettings,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.assistant import (
    AssistantRuntimeService,
    ClientInfo,
    LocationInfo,
    RuntimeContext,
)
from app.services.knowledge.example_service import detect_style_intent, retrieve_style_examples
from app.services.sms.bootcamp import BootcampRunner, DEFAULT_STYLE_PROFILE
from app.services.sms.bootcamp_service import (
    _build_bootcamp_runtime_and_prompt,
    generate_bootcamp_tori_reply,
)


def _auth_headers(tenant: Tenant, admin_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(admin_user.id)})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


@pytest.fixture
def audit_test_env(db_session):
    """Seed test fixtures for style examples and tool audit tests."""
    tenant = Tenant(name="Equinox Wellness", subdomain="equinox")
    db_session.add(tenant)
    db_session.flush()

    admin = User(
        tenant_id=tenant.id,
        login="admin@equinox.com",
        password_hash="hashed_pw",
        role="admin",
    )
    db_session.add(admin)
    db_session.flush()

    provider = Provider(
        tenant_id=tenant.id,
        name="Dr. Taylor Brooks",
        active=True,
        in_call_address="42 Ocean Street, Manly NSW 2095",
    )
    db_session.add(provider)
    db_session.flush()

    location = Location(
        tenant_id=tenant.id,
        name="Manly Beachside Clinic",
        address="42 Ocean Street, Manly NSW 2095",
        timezone="Australia/Sydney",
        active=True,
    )
    db_session.add(location)
    db_session.flush()

    service = Service(
        tenant_id=tenant.id,
        name="Aromatherapy Massage",
        price=160.00,
        duration=60,
        active=True,
    )
    db_session.add(service)
    db_session.flush()

    db_session.add(
        ServiceProvider(
            service_id=service.id,
            provider_id=provider.id,
            tenant_id=tenant.id,
        )
    )

    settings = SmsBootcampSettings(
        tenant_id=tenant.id,
        provider_id=provider.id,
        agent_name="Tori",
        model="gpt-4o-mini",
        active_style_profile=dict(DEFAULT_STYLE_PROFILE),
    )
    db_session.add(settings)
    db_session.commit()

    return {
        "tenant": tenant,
        "admin": admin,
        "provider": provider,
        "location": location,
        "service": service,
        "settings": settings,
    }


# ===========================================================================
# 1. Style Examples Wiring Tests
# ===========================================================================

def test_intent_aware_style_retrieval_respects_scope_precedence(audit_test_env, db_session):
    """Only relevant examples are selected provider -> tenant -> platform."""
    env = audit_test_env
    tenant = env["tenant"]
    provider = env["provider"]
    scopes = [
        (None, None, "platform"),
        (tenant.id, None, "tenant"),
        (tenant.id, provider.id, "provider"),
    ]
    for tenant_id, provider_id, label in scopes:
        db_session.add(MessageStyleExample(
            tenant_id=tenant_id,
            provider_id=provider_id,
            intent="pricing",
            client_message=f"{label}: What does it cost?",
            assistant_reply=f"{label}: I can help with service pricing.",
            category="procedural",
            is_approved=True,
            is_active=True,
            content_hash=f"pricing-{label}",
        ))
    # An irrelevant most-recent example must never displace the pricing set.
    db_session.add(MessageStyleExample(
        tenant_id=tenant.id,
        provider_id=provider.id,
        intent="greeting",
        client_message="irrelevant newest greeting",
        assistant_reply="Hello!",
        category="procedural",
        is_approved=True,
        is_active=True,
        content_hash="greeting-newest",
    ))
    db_session.commit()

    assert detect_style_intent("How much does an appointment cost?") == "pricing"
    examples = retrieve_style_examples(
        db_session,
        tenant_id=tenant.id,
        provider_id=provider.id,
        detected_intent="pricing",
        limit=3,
    )
    assert [example.client_message.split(":", 1)[0] for example in examples] == [
        "provider", "tenant", "platform"
    ]

def test_style_examples_reach_prompt_in_bootcamp_and_runtime(audit_test_env, db_session):
    """Prove that approved MessageStyleExample records reach the model prompt payload.

    Deficiency 1 Resolved: retrieve_style_examples is called by both
    _build_bootcamp_runtime_and_prompt and AssistantRuntimeService.execute_turn.
    """
    env = audit_test_env
    tenant = env["tenant"]
    provider = env["provider"]

    # Seed an approved style example with a unique marker string
    marker_query = "MARKER_QUERY: Are sessions suitable during pregnancy?"
    marker_reply = "MARKER_REPLY: Yes, Dr. Brooks provides specialized prenatal positioning."

    example = MessageStyleExample(
        tenant_id=tenant.id,
        provider_id=provider.id,
        intent="pregnancy_inquiry",
        client_message=marker_query,
        assistant_reply=marker_reply,
        category="clinical_tone",
        is_approved=True,
        is_active=True,
    )
    db_session.add(example)
    db_session.commit()

    # Part A: Test Bootcamp runtime prompt builder
    history = [{"role": "persona", "text": "Are sessions suitable during pregnancy?"}]
    context, assembled, model, agent_name, _, _, _ = _build_bootcamp_runtime_and_prompt(
        history=history,
        style_profile=DEFAULT_STYLE_PROFILE,
        tenant_id=tenant.id,
        provider_id=provider.id,
        db=db_session,
    )

    # Verify style example appears in assembled system prompt (Tier 8)
    assert "tier_8_examples" in assembled.sections
    assert marker_query in assembled.sections["tier_8_examples"]
    assert marker_reply in assembled.sections["tier_8_examples"]
    assert marker_query in assembled.system_prompt
    assert marker_reply in assembled.system_prompt

    # Part B: Test AssistantRuntimeService.execute_turn
    runtime_context = RuntimeContext(
        tenant_id=tenant.id,
        provider_id=provider.id,
        channel_type=ChannelType.SIMULATED.value,
        client=ClientInfo(name="Test Client", phone="+61400000000"),
        location=LocationInfo(id=env["location"].id, name=env["location"].name),
    )

    turn_result = AssistantRuntimeService.execute_turn(
        db=db_session,
        runtime_context=runtime_context,
        user_message="Are sessions suitable during pregnancy?",
        is_simulation=True,
    )

    # Verify style examples are loaded and present in prompt & result metadata
    assert len(turn_result.style_examples_used) >= 1
    found_marker = any(
        ex.get("client_message") == marker_query or marker_query in str(ex)
        for ex in turn_result.style_examples_used
    )
    assert found_marker, "Seeded style example not found in style_examples_used"
    assert marker_query in turn_result.system_prompt
    assert marker_reply in turn_result.system_prompt


# ===========================================================================
# 2. Tool Audit Persistence in Bootcamp Message Meta
# ===========================================================================

def test_bootcamp_persists_tool_audit_in_message_meta(audit_test_env, db_session, monkeypatch):
    """Prove that when Bootcamp generates a Tori reply calling tools, tool audit traces persist in SmsBootcampMessage.meta.

    Deficiency 2 Resolved: BootcampRunner initializes executed_tools_meta, passes it
    through _call_generate_tori, and commits msg.meta containing executed_tools.
    """
    env = audit_test_env
    tenant = env["tenant"]
    provider = env["provider"]

    # 1. Create Bootcamp Run and Conversation
    run = SmsBootcampRun(
        tenant_id=tenant.id,
        provider_id=provider.id,
        status="running",
        selected_personas=["happy-harry"],
        autonomy_level=2,  # Semi-autonomous
        max_turns=3,
        style_profile=DEFAULT_STYLE_PROFILE,
    )
    db_session.add(run)
    db_session.flush()

    conv = SmsBootcampConversation(
        run_id=run.id,
        tenant_id=tenant.id,
        provider_id=provider.id,
        persona_id="happy-harry",
        persona_name="Happy Harry",
        scenario_id="service_inquiry",
        status="running",
        current_turn=0,
    )
    db_session.add(conv)
    db_session.flush()

    # Initial persona message
    persona_msg = SmsBootcampMessage(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="persona",
        text="What is the price of Aromatherapy Massage?",
        meta={"turn": 0, "scenario_id": "service_inquiry"},
    )
    db_session.add(persona_msg)
    db_session.commit()

    # 2. Mock OpenAI multi-turn completion: Turn 1 calls service_lookup, Turn 2 gives final reply
    tool_call_obj = MagicMock()
    tool_call_obj.id = "call_audit_test_1"
    tool_call_obj.type = "function"
    tool_call_obj.function.name = "service_lookup"
    tool_call_obj.function.arguments = json.dumps({"service_id_or_slug": "Aromatherapy"})

    mock_resp_1 = MagicMock()
    mock_resp_1.choices = [MagicMock()]
    mock_resp_1.choices[0].message.content = ""
    mock_resp_1.choices[0].message.tool_calls = [tool_call_obj]

    mock_resp_2 = MagicMock()
    mock_resp_2.choices = [MagicMock()]
    mock_resp_2.choices[0].message.content = (
        "Our Aromatherapy Massage is $160.00 for 60 minutes with Dr. Taylor Brooks."
    )
    mock_resp_2.choices[0].message.tool_calls = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [mock_resp_1, mock_resp_2]

    monkeypatch.setattr("openai.OpenAI", lambda *args, **kwargs: mock_client)
    monkeypatch.setattr("app.services.sms.bootcamp_service._is_openai_available", lambda: True)
    monkeypatch.setattr("app.services.assistant.runtime_service.is_openai_available", lambda: True)

    # 3. Advance turn using BootcampRunner with controlled persona response
    runner = BootcampRunner(
        message_delay_seconds=0,
        generate_persona=lambda *args, **kwargs: "How much is the Aromatherapy session?",
    )
    runner.advance_turn(db=db_session, conv=conv, run=run)

    # 4. Query messages from DB and verify tool audit persistence
    messages = (
        db_session.query(SmsBootcampMessage)
        .filter(
            SmsBootcampMessage.conversation_id == conv.id,
            SmsBootcampMessage.role == "tori",
        )
        .order_by(SmsBootcampMessage.created_at.desc())
        .all()
    )

    assert len(messages) >= 1, "Expected at least one Tori message to be persisted"
    tori_msg = messages[0]

    # Verify SmsBootcampMessage.meta persisted executed_tools
    assert tori_msg.meta is not None, "Message meta is empty"
    assert "executed_tools" in tori_msg.meta, "executed_tools missing from SmsBootcampMessage.meta"
    assert tori_msg.meta.get("tool_count", 0) >= 1

    executed_tools = tori_msg.meta["executed_tools"]
    assert len(executed_tools) == 1
    tool_trace = executed_tools[0]

    assert tool_trace["tool_name"] == "service_lookup"
    assert tool_trace["status"] == "success"
    assert "timestamp" in tool_trace
    # Telemetry must remain structural: raw arguments, prices, service data,
    # addresses, and tool bodies are never stored in conversation metadata.
    assert tool_trace["argument_keys"] == ["service_id_or_slug"]
    assert tool_trace["result_keys"]
    assert not ({"arguments", "result", "result_preview", "output"} & set(tool_trace))


# ===========================================================================
# 3. Studio /simulate Multi-Turn Tool Execution
# ===========================================================================

def test_studio_simulate_multi_turn_tool_execution(audit_test_env, client: TestClient, monkeypatch):
    """Prove that POST /simulate executes multi-turn tool loops via AssistantRuntimeService.

    Deficiency 3 Resolved: Studio /simulate uses AssistantRuntimeService rather than
    divergent keyword pre-triggering.
    """
    env = audit_test_env
    headers = _auth_headers(env["tenant"], env["admin"])

    # 1. Mock OpenAI multi-turn tool execution
    tool_call_obj = MagicMock()
    tool_call_obj.id = "call_sim_test_1"
    tool_call_obj.type = "function"
    tool_call_obj.function.name = "service_lookup"
    tool_call_obj.function.arguments = json.dumps({"service_id_or_slug": "Aromatherapy"})

    mock_resp_1 = MagicMock()
    mock_resp_1.choices = [MagicMock()]
    mock_resp_1.choices[0].message.content = ""
    mock_resp_1.choices[0].message.tool_calls = [tool_call_obj]

    mock_resp_2 = MagicMock()
    mock_resp_2.choices = [MagicMock()]
    mock_resp_2.choices[0].message.content = (
        "Our Aromatherapy Massage is $160.00 for 60 minutes. Would you like to reserve a time?"
    )
    mock_resp_2.choices[0].message.tool_calls = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [mock_resp_1, mock_resp_2]

    monkeypatch.setattr("openai.OpenAI", lambda *args, **kwargs: mock_client)
    monkeypatch.setattr("app.services.assistant.runtime_service.is_openai_available", lambda: True)

    sim_payload = {
        "client_input": "How much does the Aromatherapy session cost?",
        "conversation_history": [],
        "provider_id": env["provider"].id,
    }

    resp = client.post("/api/admin/assistant-studio/simulate", json=sim_payload, headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    # 2. Verify model calls occurred and live tool loop completed
    assert mock_client.chat.completions.create.call_count == 2
    assert "Aromatherapy Massage is $160.00" in data["reply"]

    # 3. Verify executed_tools telemetry returned in response
    assert len(data["executed_tools"]) == 1
    tool_trace = data["executed_tools"][0]
    assert tool_trace["name"] == "service_lookup"
    assert tool_trace["status"] == "success"
    assert tool_trace["argument_keys"] == ["service_id_or_slug"]
    assert tool_trace["server_bound_keys"] == ["tenant_id"]
    assert not ({"arguments", "result", "result_preview", "output"} & set(tool_trace))
