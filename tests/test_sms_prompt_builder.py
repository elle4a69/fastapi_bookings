"""Comprehensive test suite for Unified Layered Prompt Builder and Runtime Convergence.

Tests Master Spec requirements (Specs 2-12, 44-46, 48-49):
- Test 1: Layer order precedence (Safety > Tenant policy > Provider style > Knowledge > State > Modulation > Tools).
- Test 2: Style Lab trait incorporation (verifying traits like Sarcasm, Warmth, Wit are rendered as behavioral priors).
- Test 3: Situational modulation (frustrated customer reduces sarcasm and increases patience).
- Test 4: Earned stylistic escalation (formal/new customer receives polite/neutral tone).
- Test 5: Operational data separation (services, pricing, and notice formatted outside prose prompts).
- Test 6: Multi-tenant and provider scoping on knowledge and profiles.
- Test 7: Integration with ai_orchestrator and bootcamp_service.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile
from app.models.curated_memory import CuratedMemory
from app.models.sms_bootcamp import SmsBootcampSettings
from app.services.sms.prompt_builder import (
    UnifiedPromptBuilder,
    build_system_prompt,
    build_messages_payload,
    detect_situational_modulation,
    detect_earned_escalation,
    format_structured_operational_data,
    format_style_profile,
    DEFAULT_CORE_SAFETY_RULES,
)
from app.services.sms.bootcamp import DEFAULT_STYLE_PROFILE
from app.services.sms.bootcamp_service import (
    build_bootcamp_instructions,
    generate_bootcamp_tori_reply,
)
from app.services.sms.ai_orchestrator import call_openai_chat_completions


# ---------------------------------------------------------------------------
# Test 1: Layer order precedence
# ---------------------------------------------------------------------------
def test_layer_order_precedence():
    """Verify strict hierarchical order of the layered prompt components."""
    core_safety = "Core Safety Rules: Verification required, no guessing."
    tenant_policy = "Tenant Policy: Cancellation requires 24h notice. Deposit is 20%."
    provider_instructions = "Provider Style: Professional aesthetician instructions."
    style_profile = {"sarcasm": 1, "warmth": 5, "wit": 3, "directness": 4}
    structured_config = "Operational Config: Service A $100, Service B $200."
    shared_knowledge = [{"text": "Shared Clinic Address: 100 Main St."}]
    provider_knowledge = [{"text": "Provider Room: Suite 4B."}]
    curated_memories = [
        CuratedMemory(
            tenant_id=1,
            category="aftercare",
            user_query="How to care for skin?",
            ideal_response="Apply sunscreen daily.",
            status="active",
            conflict_state="clear",
        )
    ]
    conversation_state = {"intent": "booking", "selected_service": "Facial"}
    modulation_instructions = "Modulation: Extra patience active."
    tool_instructions = "Available Tools: check_availability, book_appointment."

    # 1. Test build_system_prompt string assembly
    system_prompt = build_system_prompt(
        core_safety=core_safety,
        tenant_policy=tenant_policy,
        provider_instructions=provider_instructions,
        style_profile=style_profile,
        structured_config=structured_config,
        shared_knowledge=shared_knowledge,
        provider_knowledge=provider_knowledge,
        curated_memories=curated_memories,
        conversation_state=conversation_state,
        modulation_instructions=modulation_instructions,
        tool_instructions=tool_instructions,
    )

    core_idx = system_prompt.index("--- CORE SYSTEM BEHAVIOUR ---")
    tenant_idx = system_prompt.index("--- TENANT / BUSINESS POLICY ---")
    provider_idx = system_prompt.index("--- PROVIDER BEHAVIOUR PROFILE & STYLE LAB ---")
    config_idx = system_prompt.index("--- STRUCTURED PROVIDER CONFIGURATION ---")
    knowledge_idx = system_prompt.index("--- RELEVANT CURATED KNOWLEDGE ---")
    state_idx = system_prompt.index("--- CURRENT CUSTOMER + CONVERSATION STATE ---")
    modulation_idx = system_prompt.index("--- CUSTOMER TONE ADAPTATION & SITUATIONAL MODULATION ---")
    tool_idx = system_prompt.index("--- CURRENT TOOL / APPLICATION STATE ---")

    assert core_idx < tenant_idx < provider_idx < config_idx < knowledge_idx < state_idx < modulation_idx < tool_idx

    # 2. Test build_messages_payload with discrete messages
    messages = build_messages_payload(
        core_safety=core_safety,
        tenant_policy=tenant_policy,
        provider_instructions=provider_instructions,
        style_profile=style_profile,
        structured_config=structured_config,
        shared_knowledge=shared_knowledge,
        provider_knowledge=provider_knowledge,
        curated_memories=curated_memories,
        conversation_state=conversation_state,
        modulation_instructions=modulation_instructions,
        tool_instructions=tool_instructions,
        history_messages=[{"role": "user", "content": "Prior message"}],
        current_message="Current inbound question",
        discrete_system_messages=True,
        separate_operational_message=True,
    )

    roles = [m["role"] for m in messages]
    assert roles[0] == "system"
    assert "Core Safety Rules" in messages[0]["content"]

    assert messages[1]["role"] == "system"
    assert "Tenant Policy" in messages[1]["content"]

    assert messages[2]["role"] == "system"
    assert "Provider Style" in messages[2]["content"]
    assert "Warmth 5/5" in messages[2]["content"]

    assert messages[3]["role"] == "system"
    assert "Operational Config" in messages[3]["content"]

    assert messages[4]["role"] == "system"
    assert "Context Knowledge: Shared Clinic Address" in messages[4]["content"]

    assert messages[5]["role"] == "system"
    assert "Context Knowledge: Provider Room" in messages[5]["content"]

    assert messages[6]["role"] == "system"
    assert "Context Knowledge: [aftercare] How to care for skin?: Apply sunscreen daily." in messages[6]["content"]

    assert messages[7]["role"] == "system"
    assert "Customer Conversation State:" in messages[7]["content"]

    assert messages[8]["role"] == "system"
    assert "Modulation: Extra patience" in messages[8]["content"]

    assert messages[9]["role"] == "system"
    assert "Available Tools:" in messages[9]["content"]

    assert messages[10]["role"] == "user"
    assert messages[10]["content"] == "Prior message"

    assert messages[11]["role"] == "user"
    assert messages[11]["content"] == "Current inbound question"


# ---------------------------------------------------------------------------
# Test 2: Style Lab trait incorporation
# ---------------------------------------------------------------------------
def test_style_lab_trait_incorporation():
    """Verify that all 8 Style Lab traits are rendered as behavioral priors on a 0-5 scale."""
    custom_profile = {
        "flirtiness": 0,
        "cheerfulness": 5,
        "wit": 4,
        "sarcasm": 2,
        "warmth": 4,
        "directness": 5,
        "chattiness": 1,
        "patience": 5,
    }

    rendered = format_style_profile(custom_profile)

    assert "Provider Behaviour Profile & Style Lab:" in rendered
    assert "Flirtiness 0/5: Keep the tone entirely non-flirtatious." in rendered
    assert "Cheerfulness 5/5: Be highly cheerful without sounding artificial." in rendered
    assert "Wit 4/5: Be playfully witty without distracting from the answer." in rendered
    assert "Sarcasm 2/5: Use rare, gentle sarcasm only when clearly safe." in rendered
    assert "Warmth 4/5: Be notably warm and reassuring." in rendered
    assert "Directness 5/5: Be exceptionally blunt and concise without rudeness." in rendered
    assert "Chattiness 1/5: Usually use one short sentence." in rendered
    assert "Patience 5/5: Be exceptionally patient without rewarding pressure or manipulation." in rendered

    # Verify clamping behavior for out-of-range inputs
    clamped = format_style_profile({"sarcasm": 10, "warmth": -3})
    assert "Sarcasm 5/5" in clamped
    assert "Warmth 0/5" in clamped


# ---------------------------------------------------------------------------
# Test 3: Situational modulation
# ---------------------------------------------------------------------------
def test_situational_modulation():
    """Verify that frustrated or complaining customer messages trigger trait modulation."""
    base_profile = {
        "sarcasm": 4,
        "wit": 3,
        "warmth": 2,
        "directness": 3,
        "patience": 2,
        "flirtiness": 2,
        "cheerfulness": 3,
        "chattiness": 2,
    }

    # 1. Frustrated customer message
    frustrated_msg = "I am extremely furious and frustrated!! You double charged my card and I want an immediate refund!"
    result = detect_situational_modulation(frustrated_msg, base_profile=base_profile)

    assert result["is_modulated"] is True
    mod_traits = result["modulated_profile"]

    # Sarcasm suppressed to 0
    assert mod_traits["sarcasm"] == 0
    # Wit suppressed/capped to 1
    assert mod_traits["wit"] <= 1
    # Flirtiness suppressed to 0
    assert mod_traits["flirtiness"] == 0
    # Patience boosted to maximum 5
    assert mod_traits["patience"] == 5
    # Warmth and directness boosted
    assert mod_traits["warmth"] >= 4
    assert mod_traits["directness"] >= 4

    assert "Situational Modulation Active" in result["instructions"]
    assert "Suppress all sarcasm" in result["instructions"]

    # 2. Shouting message
    shouting_msg = "WHY HAS NOBODY REPLIED TO ME THIS IS RIDICULOUS"
    result_shout = detect_situational_modulation(shouting_msg, base_profile=base_profile)
    assert result_shout["is_modulated"] is True
    assert result_shout["modulated_profile"]["sarcasm"] == 0

    # 3. Escalation request
    manager_msg = "I need to speak to a real person or manager right now."
    result_mgr = detect_situational_modulation(manager_msg, base_profile=base_profile)
    assert result_mgr["is_modulated"] is True
    assert result_mgr["modulated_profile"]["sarcasm"] == 0

    # 4. Calm customer inquiry (no modulation)
    calm_msg = "Hi there, do you have any appointments available on Friday?"
    result_calm = detect_situational_modulation(calm_msg, base_profile=base_profile)
    assert result_calm["is_modulated"] is False
    assert result_calm["modulated_profile"] == base_profile
    assert result_calm["instructions"] == ""


# ---------------------------------------------------------------------------
# Test 4: Earned stylistic escalation
# ---------------------------------------------------------------------------
def test_earned_stylistic_escalation():
    """Verify that unfamiliar or formal customers have sassy/cheeky banter suppressed."""
    base_profile = {
        "sarcasm": 3,
        "wit": 4,
        "flirtiness": 3,
        "warmth": 4,
        "directness": 3,
        "patience": 3,
        "cheerfulness": 3,
        "chattiness": 2,
    }

    # 1. New customer without prior rapport
    new_res = detect_earned_escalation("Hey, what are your hours?", is_new_customer=True, base_profile=base_profile)
    assert new_res["rapport_earned"] is False
    assert new_res["modulated_profile"]["sarcasm"] == 0
    assert new_res["modulated_profile"]["flirtiness"] == 0
    assert new_res["modulated_profile"]["wit"] <= 1
    assert "Earned Escalation Guard Active" in new_res["instructions"]

    # 2. Established customer using formal language
    formal_res = detect_earned_escalation(
        "Good morning. I am writing to inquire regarding available consultation slots. Respectfully, Arthur.",
        is_new_customer=False,
        base_profile=base_profile,
    )
    assert formal_res["rapport_earned"] is False
    assert formal_res["modulated_profile"]["sarcasm"] == 0

    # 3. Established customer using casual banter (rapport earned!)
    casual_res = detect_earned_escalation(
        "Hey Tori! Haha you're hilarious, are you free this Friday?",
        is_new_customer=False,
        base_profile=base_profile,
    )
    assert casual_res["rapport_earned"] is True
    assert casual_res["modulated_profile"]["sarcasm"] == base_profile["sarcasm"]
    assert casual_res["modulated_profile"]["flirtiness"] == base_profile["flirtiness"]
    assert casual_res["instructions"] == ""


# ---------------------------------------------------------------------------
# Test 5: Operational data separation
# ---------------------------------------------------------------------------
def test_operational_data_separation():
    """Verify that operational services, pricing, buffer, and hours are cleanly formatted."""
    provider_data = {
        "name": "Dr. Sarah",
        "turnaround_buffer_mins": 20,
        "weekly_schedule": {"monday": "9am-5pm", "tuesday": "9am-5pm"},
        "in_call_address": "456 Wellness Way, Suite 2",
        "out_call_radius_km": 30.0,
        "base_outcall_surcharge": 25.0,
    }
    services_data = [
        {
            "name": "Deep Tissue Massage",
            "duration": 60,
            "price": 140.0,
            "deposit_amount": 30.0,
            "description": "Full body relaxation",
        },
        {
            "name": "Express Facial",
            "duration": 30,
            "price": 75.0,
            "deposit_amount": 0.0,
            "description": "Quick hydration treatment",
        },
    ]
    locations_data = [
        {"name": "Downtown Clinic", "address": "123 Central Ave"},
        "Northside Annex",
    ]

    formatted = format_structured_operational_data(
        provider=provider_data,
        services=services_data,
        locations=locations_data,
    )

    assert "Structured Provider Configuration & Operational Menu:" in formatted
    assert "Provider: Dr. Sarah" in formatted
    assert "Notice & Turnaround Buffer: 20 mins" in formatted
    assert "Working Schedule: {'monday': '9am-5pm', 'tuesday': '9am-5pm'}" in formatted
    assert "In-call Address: 456 Wellness Way, Suite 2" in formatted
    assert "Out-call Coverage Radius: 30.0 km (Base Surcharge: $25.0)" in formatted
    assert "- Deep Tissue Massage | Duration: 60 mins | Price: $140.0 | Deposit: $30.0 (Full body relaxation)" in formatted
    assert "- Express Facial | Duration: 30 mins | Price: $75.0 (Quick hydration treatment)" in formatted
    assert "- Downtown Clinic: 123 Central Ave" in formatted
    assert "- Northside Annex" in formatted

    # Empty inputs return empty string
    assert format_structured_operational_data(provider=None, services=None, locations=None) == ""


# ---------------------------------------------------------------------------
# Test 6: Multi-tenant and provider scoping on knowledge and profiles
# ---------------------------------------------------------------------------
def test_multi_tenant_and_provider_scoping(db_session):
    """Verify that prompt builder queries strictly isolate across tenant and provider boundaries."""
    # 1. Create Tenant A and Tenant B
    tenant_a = Tenant(name="Tenant A - Medical", subdomain="tenant-a-builder")
    tenant_b = Tenant(name="Tenant B - Dental", subdomain="tenant-b-builder")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    # 2. Providers
    prov_a1 = Provider(tenant_id=tenant_a.id, name="Dr. A1", active=True)
    prov_a2 = Provider(tenant_id=tenant_a.id, name="Dr. A2", active=True)
    prov_b1 = Provider(tenant_id=tenant_b.id, name="Dr. B1", active=True)
    db_session.add_all([prov_a1, prov_a2, prov_b1])
    db_session.flush()

    # 3. Prompt Profiles
    pp_global_a = SmsPromptProfile(
        tenant_id=tenant_a.id,
        provider_id=None,
        name="Global A",
        system_prompt="Tenant A Global Policy: Safe and HIPAA compliant.",
        is_active=True,
    )
    pp_prov_a1 = SmsPromptProfile(
        tenant_id=tenant_a.id,
        provider_id=prov_a1.id,
        name="Profile A1",
        system_prompt="Dr. A1 is a specialist dermatologist.",
        is_active=True,
    )
    pp_prov_a2 = SmsPromptProfile(
        tenant_id=tenant_a.id,
        provider_id=prov_a2.id,
        name="Profile A2",
        system_prompt="Dr. A2 is a plastic surgeon.",
        is_active=True,
    )
    pp_global_b = SmsPromptProfile(
        tenant_id=tenant_b.id,
        provider_id=None,
        name="Global B",
        system_prompt="Tenant B Secret Rules.",
        is_active=True,
    )
    db_session.add_all([pp_global_a, pp_prov_a1, pp_prov_a2, pp_global_b])

    # 4. Knowledge Entries
    sk_a = SmsKnowledgeEntry(
        tenant_id=tenant_a.id,
        provider_id=None,
        category="general",
        text="Tenant A shared parking: Basement level 2.",
        status="approved",
    )
    pk_a1 = SmsKnowledgeEntry(
        tenant_id=tenant_a.id,
        provider_id=prov_a1.id,
        category="bio",
        text="Dr. A1 room is 201.",
        status="approved",
    )
    pk_a2 = SmsKnowledgeEntry(
        tenant_id=tenant_a.id,
        provider_id=prov_a2.id,
        category="bio",
        text="Dr. A2 room is 305.",
        status="approved",
    )
    sk_b = SmsKnowledgeEntry(
        tenant_id=tenant_b.id,
        provider_id=None,
        category="secret",
        text="Tenant B confidential pricing info.",
        status="approved",
    )
    db_session.add_all([sk_a, pk_a1, pk_a2, sk_b])

    # 5. Curated Memories
    cm_a = CuratedMemory(
        tenant_id=tenant_a.id,
        provider_id=prov_a1.id,
        category="procedure",
        user_query="How long is recovery?",
        ideal_response="Standard recovery is 3-5 days.",
        status="active",
        conflict_state="clear",
    )
    cm_b = CuratedMemory(
        tenant_id=tenant_b.id,
        provider_id=prov_b1.id,
        category="procedure",
        user_query="Root canal info?",
        ideal_response="Root canal takes 90 minutes.",
        status="active",
        conflict_state="clear",
    )
    db_session.add_all([cm_a, cm_b])
    db_session.commit()

    # Query for Tenant A, Provider A1
    queried_shared_k = db_session.query(SmsKnowledgeEntry).filter(
        SmsKnowledgeEntry.tenant_id == tenant_a.id,
        SmsKnowledgeEntry.provider_id.is_(None),
        SmsKnowledgeEntry.status == "approved",
    ).all()

    queried_prov_k = db_session.query(SmsKnowledgeEntry).filter(
        SmsKnowledgeEntry.tenant_id == tenant_a.id,
        SmsKnowledgeEntry.provider_id == prov_a1.id,
        SmsKnowledgeEntry.status == "approved",
    ).all()

    queried_curated = db_session.query(CuratedMemory).filter(
        CuratedMemory.tenant_id == tenant_a.id,
        CuratedMemory.provider_id == prov_a1.id,
        CuratedMemory.status == "active",
        CuratedMemory.conflict_state == "clear",
    ).all()

    builder = (
        UnifiedPromptBuilder(tenant_id=tenant_a.id, provider_id=prov_a1.id)
        .with_core_safety()
        .with_tenant_policy(pp_global_a.system_prompt)
        .with_provider_profile(text=pp_prov_a1.system_prompt)
        .with_knowledge(
            shared_entries=queried_shared_k,
            provider_entries=queried_prov_k,
            curated_memories=queried_curated,
        )
    )

    sys_prompt = builder.build_system_prompt()

    # Verify inclusion of Tenant A and Provider A1 facts
    assert "Tenant A Global Policy: Safe and HIPAA compliant." in sys_prompt
    assert "Dr. A1 is a specialist dermatologist." in sys_prompt
    assert "Tenant A shared parking: Basement level 2." in sys_prompt
    assert "Dr. A1 room is 201." in sys_prompt
    assert "Standard recovery is 3-5 days." in sys_prompt

    # Verify EXCLUSION of Provider A2 and Tenant B data
    assert "Dr. A2 is a plastic surgeon." not in sys_prompt
    assert "Dr. A2 room is 305." not in sys_prompt
    assert "Tenant B Secret Rules." not in sys_prompt
    assert "Tenant B confidential pricing info." not in sys_prompt
    assert "Root canal takes 90 minutes." not in sys_prompt


# ---------------------------------------------------------------------------
# Test 7: Integration with ai_orchestrator and bootcamp_service
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_integration_with_ai_orchestrator_and_bootcamp_service(db_session):
    """Verify runtime convergence of ai_orchestrator and bootcamp_service via UnifiedPromptBuilder."""
    # 1. Setup tenant & provider
    tenant = Tenant(name="Integration Tenant", subdomain="integ-builder")
    db_session.add(tenant)
    db_session.flush()

    provider = Provider(tenant_id=tenant.id, name="Dr. Convergence", active=True)
    db_session.add(provider)
    db_session.flush()

    service = Service(tenant_id=tenant.id, name="Acupuncture", duration=45, price=95.0)
    db_session.add(service)
    db_session.flush()

    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Line Convergence",
        sender_address="61412340001",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="autopilot",
        line_prompt="Fallback line prompt.",
    )
    db_session.add(account)
    db_session.flush()

    conv = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        customer_address="61488880001",
        state="auto-reply",
        unread_count=0,
    )
    db_session.add(conv)
    db_session.flush()

    # Active Provider Prompt Profile
    pp = SmsPromptProfile(
        tenant_id=tenant.id,
        provider_id=provider.id,
        name="Convergence Provider Profile",
        system_prompt="Convergence instructions for Dr. Convergence.",
        is_active=True,
    )
    db_session.add(pp)

    # Bootcamp Settings with custom style profile & training notes
    bootcamp_settings = SmsBootcampSettings(
        tenant_id=tenant.id,
        active_style_profile={"sarcasm": 0, "warmth": 5, "patience": 5, "directness": 4},
        custom_training_notes="Never book after 7 PM without explicit consent.",
        agent_name="Tori-Integ",
    )
    db_session.add(bootcamp_settings)

    # Curated Memory
    curated = CuratedMemory(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="policies",
        user_query="Do you accept cash?",
        ideal_response="Cash and credit cards are both accepted at checkout.",
        status="active",
        conflict_state="clear",
    )
    db_session.add(curated)
    db_session.commit()

    # Inbound current message
    msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        conversation_id=conv.id,
        body="Do you accept cash payments?",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-integ-1",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(msg)
    db_session.commit()

    # Mock OpenAI client
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Yes, cash and card are accepted!"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class, patch(
        "app.core.config.settings.OPENAI_API_KEY", "sk-test-integ-key"
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        mock_client.post.return_value = mock_resp

        reply = await call_openai_chat_completions(
            db=db_session,
            account=account,
            conversation=conv,
            message_body="Do you accept cash payments?",
            turn_ref="turn-integ-1",
        )

        assert reply == "Yes, cash and card are accepted!"
        mock_client.post.assert_called_once()
        payload = mock_client.post.call_args[1]["json"]
        sent_messages = payload["messages"]

        all_contents = [m["content"] for m in sent_messages]

        # Verify Layered convergence elements:
        assert any("Immutable Platform Safety Rules" in c for c in all_contents)
        assert any("Convergence instructions for Dr. Convergence." in c for c in all_contents)
        assert any("Warmth 5/5" in c for c in all_contents)
        assert any("Acupuncture | Duration: 45 mins | Price: $95.00" in c for c in all_contents)
        assert any("Cash and credit cards are both accepted" in c for c in all_contents)
        assert any("Do you accept cash payments?" in c for c in all_contents)

    # 2. Test Bootcamp instructions compilation
    bootcamp_instructions = build_bootcamp_instructions(
        agent_name="Tori",
        custom_notes="Always confirm duration before finalizing.",
        system_prompt_template="You are Tori, a master scheduling assistant.",
        style_profile={"wit": 3, "warmth": 4, "directness": 4, "sarcasm": 1},
    )

    assert "--- CORE SYSTEM BEHAVIOUR ---" in bootcamp_instructions
    assert "Boot Camp uncertainty rule: use a clarification ladder" in bootcamp_instructions
    assert "--- TENANT / BUSINESS POLICY ---" in bootcamp_instructions
    assert "You are Tori, a master scheduling assistant." in bootcamp_instructions
    assert "--- PROVIDER BEHAVIOUR PROFILE & STYLE LAB ---" in bootcamp_instructions
    assert "Warmth 4/5" in bootcamp_instructions
    assert "Wit 3/5" in bootcamp_instructions
    assert "Always confirm duration before finalizing." in bootcamp_instructions
