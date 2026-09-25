"""Comprehensive QA Audit & Verification Test Suite for Track 3.

Audits:
1. Multi-tenant boundary isolation in prompt assembler (Tenant A vs Tenant B).
2. State machine resilience to out-of-order user inputs, nonsensical texts, and rapid turns.
3. Draping and medical contraindication guardrail adherence in prompt templates.
4. LangGraph state serialization, deserialization, and state persistence roundtrips.
5. Chatwoot AgentBot webhook boundary isolation and error handling.
"""

from datetime import datetime, timezone
import json
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage, messages_from_dict, messages_to_dict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routers.chatwoot_agentbot import (
    ChatwootAgentBotPayload,
    ConversationCompletionHookPayload,
    requires_human_handoff,
)
from app.db.async_session import get_async_db
from app.db.database import Base
from app.engine.dialogue_graph import dialogue_graph, process_dialogue_turn
from app.engine.prompt_assembler import (
    PLATFORM_SAFETY_AND_INDUSTRY_RULES,
    assemble_system_prompt,
    build_runtime_profile,
    retrieve_curated_memories,
)
from app.engine.state import AgentState, CustomerLocation, DialogueTurn
from app.main import app
from app.models.curated_memory import CuratedMemory
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.sms_chatwoot import SmsChatwootBinding
from app.models.tenant import Tenant


@pytest_asyncio.fixture
async def audit_session():
    """Provides an isolated in-memory SQLite database populated with two distinct tenants."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        # ======================================================================
        # Tenant 1: Aura Holistic Studio (Sydney)
        # ======================================================================
        tenant1 = Tenant(
            id=1,
            name="Aura Holistic Studio",
            subdomain="aura",
            address="100 George Street, Sydney NSW 2000",
            timezone="Australia/Sydney",
            phone="+61411000111",
            email="bookings@auraholistic.com",
            latitude=-33.8688,
            longitude=151.2093,
        )
        session.add(tenant1)
        await session.flush()

        provider1 = Provider(
            id=1,
            tenant_id=tenant1.id,
            name="Alice Walker",
            in_call_address="100 George Street, Studio 3A, Sydney",
            out_call_radius_km=25.0,
            base_outcall_surcharge=30.00,
            per_km_fee=2.00,
            turnaround_buffer_mins=20,
        )
        session.add(provider1)
        await session.flush()

        service1_active = Service(
            id=1,
            tenant_id=tenant1.id,
            name="Aura Relaxation Massage",
            description="Signature gentle effleurage and aromatherapy for nervous system reboot.",
            duration=60,
            price=120.00,
            allow_in_call=True,
            allow_out_call=True,
            active=True,
        )
        service1_remedial = Service(
            id=2,
            tenant_id=tenant1.id,
            name="Aura Remedial Deep Tissue",
            description="Deep ischemic pressure targeting chronic spinal and postural tension.",
            duration=90,
            price=165.00,
            allow_in_call=True,
            allow_out_call=False,
            active=True,
        )
        service1_inactive = Service(
            id=3,
            tenant_id=tenant1.id,
            name="Aura Hot Stone Discontinued",
            description="Discontinued hot volcanic basalt therapy.",
            duration=60,
            price=140.00,
            allow_in_call=True,
            allow_out_call=False,
            active=False,
        )
        session.add_all([service1_active, service1_remedial, service1_inactive])
        await session.flush()

        session.add_all([
            ServiceProvider(tenant_id=tenant1.id, service_id=service1_active.id, provider_id=provider1.id),
            ServiceProvider(tenant_id=tenant1.id, service_id=service1_remedial.id, provider_id=provider1.id),
        ])
        await session.flush()

        memory1 = CuratedMemory(
            id=1,
            tenant_id=tenant1.id,
            provider_id=provider1.id,
            category="facilities",
            user_query="Where can I park when visiting Aura Holistic?",
            ideal_response="Free dedicated client parking is available in the rear lane behind 100 George Street.",
            confidence_score=0.95,
        )
        session.add(memory1)

        # ======================================================================
        # Tenant 2: Bonsai Zen Massage (Melbourne)
        # ======================================================================
        tenant2 = Tenant(
            id=2,
            name="Bonsai Zen Massage",
            subdomain="bonsai",
            address="450 Flinders Lane, Melbourne VIC 3000",
            timezone="Australia/Melbourne",
            phone="+61422000222",
            email="contact@bonsaizen.com",
            latitude=-37.8175,
            longitude=144.9671,
        )
        session.add(tenant2)
        await session.flush()

        provider2 = Provider(
            id=2,
            tenant_id=tenant2.id,
            name="Bob Tanaka",
            in_call_address="450 Flinders Lane, Floor 2, Melbourne",
            out_call_radius_km=15.0,
            base_outcall_surcharge=40.00,
            per_km_fee=3.50,
            turnaround_buffer_mins=30,
        )
        session.add(provider2)
        await session.flush()

        service2_shiatsu = Service(
            id=4,
            tenant_id=tenant2.id,
            name="Bonsai Shiatsu Acupressure",
            description="Traditional Japanese finger pressure balancing meridian energetic pathways.",
            duration=75,
            price=150.00,
            allow_in_call=True,
            allow_out_call=True,
            active=True,
        )
        session.add(service2_shiatsu)
        await session.flush()

        session.add(ServiceProvider(
            tenant_id=tenant2.id,
            service_id=service2_shiatsu.id,
            provider_id=provider2.id,
        ))
        await session.flush()

        memory2 = CuratedMemory(
            id=2,
            tenant_id=tenant2.id,
            provider_id=provider2.id,
            category="pricing",
            user_query="Do you offer tea service at Bonsai Zen?",
            ideal_response="Every treatment includes ceremonial organic Japanese green tea served after your session.",
            confidence_score=0.99,
        )
        session.add(memory2)

        # Bindings for Chatwoot
        binding1 = SmsChatwootBinding(
            tenant_id=tenant1.id,
            provider_id=provider1.id,
            chatwoot_account_id=101,
            chatwoot_inbox_id=1,
            chatwoot_base_url="https://app.chatwoot.com",
            chatwoot_api_token="dummy_token_1",
            is_enabled=True,
        )
        binding2 = SmsChatwootBinding(
            tenant_id=tenant2.id,
            provider_id=provider2.id,
            chatwoot_account_id=202,
            chatwoot_inbox_id=2,
            chatwoot_base_url="https://app.chatwoot.com",
            chatwoot_api_token="dummy_token_2",
            is_enabled=True,
        )
        session.add_all([binding1, binding2])
        await session.commit()

        yield session

    await engine.dispose()


# ==============================================================================
# AUDIT 1: MULTI-TENANT BOUNDARY ISOLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_multi_tenant_prompt_isolation_strict(audit_session: AsyncSession):
    """Verify zero cross-tenant leakage in prompt assembler for Tenant 1 vs Tenant 2."""
    # Assemble prompt for Tenant 1
    prompt_t1 = await assemble_system_prompt(
        tenant_id=1,
        provider_id=1,
        user_message="Tell me about your services and facilities",
        db=audit_session,
    )

    # 1. Tenant 1 inclusions
    assert "Aura Holistic Studio" in prompt_t1
    assert "Alice Walker" in prompt_t1
    assert "100 George Street" in prompt_t1
    assert "Aura Relaxation Massage" in prompt_t1
    assert "Aura Remedial Deep Tissue" in prompt_t1
    assert "Free dedicated client parking" in prompt_t1

    # 2. Strict Tenant 2 exclusions (ZERO LEAKAGE)
    assert "Bonsai Zen Massage" not in prompt_t1
    assert "Bob Tanaka" not in prompt_t1
    assert "Flinders Lane" not in prompt_t1
    assert "Bonsai Shiatsu" not in prompt_t1
    assert "Japanese green tea" not in prompt_t1

    # 3. Assemble prompt for Tenant 2
    prompt_t2 = await assemble_system_prompt(
        tenant_id=2,
        provider_id=2,
        user_message="Do you serve tea or have shiatsu?",
        db=audit_session,
    )

    # Tenant 2 inclusions
    assert "Bonsai Zen Massage" in prompt_t2
    assert "Bob Tanaka" in prompt_t2
    assert "450 Flinders Lane" in prompt_t2
    assert "Bonsai Shiatsu Acupressure" in prompt_t2
    assert "ceremonial organic Japanese green tea" in prompt_t2

    # Strict Tenant 1 exclusions (ZERO LEAKAGE)
    assert "Aura Holistic Studio" not in prompt_t2
    assert "Alice Walker" not in prompt_t2
    assert "100 George Street" not in prompt_t2
    assert "Aura Relaxation Massage" not in prompt_t2
    assert "Free dedicated client parking" not in prompt_t2


@pytest.mark.asyncio
async def test_multi_tenant_cross_provider_mismatch_isolation(audit_session: AsyncSession):
    """Verify requesting Tenant 1 with Tenant 2's provider does NOT leak Tenant 2's provider data."""
    # Tenant 1, but passing provider_id=2 (which belongs to Tenant 2)
    prompt = await assemble_system_prompt(
        tenant_id=1,
        provider_id=2,
        user_message="What is the therapist name?",
        db=audit_session,
    )

    # Bob Tanaka must NOT be shown as therapist because he belongs to Tenant 2
    assert "Bob Tanaka" not in prompt
    assert "Flinders Lane" not in prompt
    assert "Aura Holistic Studio" in prompt


@pytest.mark.asyncio
async def test_inactive_and_deleted_services_isolation(audit_session: AsyncSession):
    """Verify inactive and deleted services are strictly excluded from prompt."""
    prompt = await assemble_system_prompt(
        tenant_id=1,
        provider_id=None,
        user_message="Can I book the hot stone massage?",
        db=audit_session,
    )

    # Discontinued service must NOT be in available services menu
    assert "Aura Hot Stone Discontinued" not in prompt
    assert "volcanic basalt" not in prompt


@pytest.mark.asyncio
async def test_memory_retrieval_tenant_isolation(audit_session: AsyncSession):
    """Verify memory retrieval never crosses tenant boundaries."""
    memories_t1 = await retrieve_curated_memories(
        tenant_id=1,
        provider_id=1,
        user_message="tea service parking",
        db=audit_session,
    )
    assert all(m.tenant_id == 1 for m in memories_t1)
    queries_t1 = [m.user_query for m in memories_t1]
    assert any("park" in q.lower() for q in queries_t1)
    assert not any("tea" in q.lower() for q in queries_t1)

    memories_t2 = await retrieve_curated_memories(
        tenant_id=2,
        provider_id=2,
        user_message="tea service parking",
        db=audit_session,
    )
    assert all(m.tenant_id == 2 for m in memories_t2)
    queries_t2 = [m.user_query for m in memories_t2]
    assert any("tea" in q.lower() for q in queries_t2)
    assert not any("park" in q.lower() for q in queries_t2)


# ==============================================================================
# AUDIT 2: STATE MACHINE RESILIENCE & OUT-OF-ORDER INPUTS
# ==============================================================================

@pytest.mark.asyncio
async def test_out_of_order_confirmation_without_hold(audit_session: AsyncSession):
    """Verify saying 'confirm' or 'yes' when no hold is active does NOT confirm a booking."""
    turn = DialogueTurn(booking_status="inquiry")
    state: AgentState = {
        "messages": [HumanMessage(content="Yes, please confirm immediately!")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": turn,
    }

    result = await process_dialogue_turn(state, audit_session)
    updated_turn = result["dialogue_turn"]

    # Must NOT jump to confirmed
    assert updated_turn.booking_status != "confirmed"
    assert updated_turn.hold_id is None
    assert "confirmed" not in result.get("reply_text", "").lower() or "menu" in result.get("reply_text", "").lower()


@pytest.mark.asyncio
async def test_out_of_order_slot_selection_without_slots(audit_session: AsyncSession):
    """Verify picking slot number when no slots were offered does not crash or falsely hold."""
    turn = DialogueTurn(booking_status=None, available_slots=[])
    state: AgentState = {
        "messages": [HumanMessage(content="I want slot 2 please")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": turn,
    }

    result = await process_dialogue_turn(state, audit_session)
    updated_turn = result["dialogue_turn"]

    # Must not hold slot
    assert updated_turn.booking_status != "held"
    assert updated_turn.hold_id is None


@pytest.mark.asyncio
async def test_nonsensical_and_adversarial_user_inputs(audit_session: AsyncSession):
    """Test state machine stability when subjected to gibberish, empty, or emoji inputs."""
    adversarial_inputs = [
        "asdfghjk qwertyuiop zxcvbnm",
        "!@#$%^&*()_+=-~`[]{}|;:',.<>/?",
        "         ",
        "💆💆💆✨🔥🎉",
        "1234567890",
        "NaN null undefined True False",
    ]

    for user_input in adversarial_inputs:
        state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "tenant_id": 1,
            "provider_id": 1,
            "dialogue_turn": DialogueTurn(),
        }

        result = await process_dialogue_turn(state, audit_session)
        assert result is not None
        assert "dialogue_turn" in result
        reply = result.get("reply_text", "")
        assert isinstance(reply, str)
        # Should gracefully reply with greeting or treatment menu
        assert len(reply) > 0


@pytest.mark.asyncio
async def test_rapid_full_dialogue_turn_lifecycle(audit_session: AsyncSession):
    """Execute a realistic multi-turn booking progression including adversarial deviations."""
    # Turn 1: Initial Greeting
    state1: AgentState = {
        "messages": [HumanMessage(content="Hello there")],
        "tenant_id": 1,
        "provider_id": 1,
        "customer_name": "Clara Oswald",
        "customer_email": "clara@example.com",
        "dialogue_turn": DialogueTurn(),
    }
    r1 = await process_dialogue_turn(state1, audit_session)
    assert r1["dialogue_turn"].current_intent in ("greeting", "inquire_service")

    # Turn 2: Non-sequitur input (Verify recovery)
    state2: AgentState = {
        "messages": r1["messages"] + [HumanMessage(content="Can birds dream in purple?")],
        "tenant_id": 1,
        "provider_id": 1,
        "customer_name": "Clara Oswald",
        "dialogue_turn": r1["dialogue_turn"],
    }
    r2 = await process_dialogue_turn(state2, audit_session)
    assert not r2.get("should_escalate")

    # Turn 3: Service Selection
    state3: AgentState = {
        "messages": r2["messages"] + [HumanMessage(content="I want to book an Aura Relaxation Massage")],
        "tenant_id": 1,
        "provider_id": 1,
        "customer_name": "Clara Oswald",
        "dialogue_turn": r2["dialogue_turn"],
    }
    r3 = await process_dialogue_turn(state3, audit_session)
    assert r3["dialogue_turn"].booking_status == "service_selected"
    assert "Aura Relaxation" in r3["dialogue_turn"].extracted_service

    # Turn 4: Premature confirmation attempt (Must be rejected)
    state4: AgentState = {
        "messages": r3["messages"] + [HumanMessage(content="Confirm it now")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": r3["dialogue_turn"],
    }
    r4 = await process_dialogue_turn(state4, audit_session)
    assert r4["dialogue_turn"].booking_status != "confirmed"

    # Turn 5: Location Selection (In-call)
    state5: AgentState = {
        "messages": r4["messages"] + [HumanMessage(content="I prefer an in-call session at your studio")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": r4["dialogue_turn"],
    }
    r5 = await process_dialogue_turn(state5, audit_session)
    assert r5["dialogue_turn"].location_type == "in_call"
    assert r5["dialogue_turn"].calculated_outcall_fee == 0.0

    # Turn 6: Availability Check
    state6: AgentState = {
        "messages": r5["messages"] + [HumanMessage(content="What slots are free tomorrow?")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": r5["dialogue_turn"],
    }
    r6 = await process_dialogue_turn(state6, audit_session)
    assert len(r6["dialogue_turn"].available_slots) > 0
    assert r6["dialogue_turn"].booking_status == "slots_presented"

    # Turn 7: Hold Slot 1
    state7: AgentState = {
        "messages": r6["messages"] + [HumanMessage(content="Hold slot 1")],
        "tenant_id": 1,
        "provider_id": 1,
        "customer_name": "Clara Oswald",
        "customer_email": "clara@example.com",
        "dialogue_turn": r6["dialogue_turn"],
    }
    r7 = await process_dialogue_turn(state7, audit_session)
    assert r7["dialogue_turn"].booking_status == "held"
    assert r7["dialogue_turn"].hold_id is not None

    # Turn 8: Confirmation
    state8: AgentState = {
        "messages": r7["messages"] + [HumanMessage(content="Yes, please confirm my booking!")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": r7["dialogue_turn"],
    }
    r8 = await process_dialogue_turn(state8, audit_session)
    assert r8["dialogue_turn"].booking_status == "confirmed"
    assert "Confirmed" in r8.get("reply_text", "")


@pytest.mark.asyncio
async def test_mid_dialogue_boundary_escalation(audit_session: AsyncSession):
    """Verify that an inappropriate prompt at any stage terminates session immediately."""
    turn = DialogueTurn(
        service_id=1,
        extracted_service="Aura Relaxation Massage",
        location_type="in_call",
        booking_status="held",
        hold_id="HOLD-TEMPORARY-123",
    )
    state: AgentState = {
        "messages": [HumanMessage(content="Before I confirm, can I request a happy ending with nude escort?")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": turn,
    }

    result = await process_dialogue_turn(state, audit_session)
    assert result["should_escalate"] is True
    assert result["dialogue_turn"].booking_status == "escalated"
    assert "zero-tolerance" in result.get("reply_text", "").lower() or "terminated" in result.get("reply_text", "").lower()


# ==============================================================================
# AUDIT 3: DRAPING & MEDICAL CONTRAINDICATION GUARDRAIL ADHERENCE
# ==============================================================================

def test_draping_and_contraindication_guardrails():
    """Verify all required clinical safety rules exist in platform rules."""
    rules = PLATFORM_SAFETY_AND_INDUSTRY_RULES

    # 1. Draping standards
    assert "Strict Professional Draping" in rules
    assert "sheets/towels" in rules or "clean sheets" in rules
    assert "modesty and privacy" in rules

    # 2. Absolute contraindications
    assert "Absolute Contraindications" in rules
    assert "Acute fever" in rules
    assert "deep vein thrombosis" in rules or "DVT" in rules
    assert "blood clot" in rules
    assert "uncontrolled hypertension" in rules
    assert "open wounds" in rules
    assert "intoxication" in rules
    assert "respectfully decline" in rules

    # 3. Relative contraindications
    assert "Local / Relative Contraindications" in rules
    assert "varicose veins" in rules
    assert "pregnancy" in rules
    assert "osteoporosis" in rules

    # 4. Therapist safety & autonomy
    assert "Therapist Safety & Autonomy" in rules
    assert "absolute right to refuse service" in rules or "refuse service" in rules
    assert "zero-tolerance" in rules.lower()


@pytest.mark.asyncio
async def test_assembled_prompt_includes_all_clinical_guardrails(audit_session: AsyncSession):
    """Verify runtime assembled prompt carries full clinical and draping guardrails."""
    prompt = await assemble_system_prompt(
        tenant_id=1,
        provider_id=1,
        user_message="I have acute fever, can I come in?",
        db=audit_session,
    )

    assert "Strict Professional Draping" in prompt
    assert "Acute fever or systemic infections" in prompt
    assert "deep vein thrombosis (DVT)" in prompt
    assert "respectfully decline the appointment for client safety" in prompt
    assert "ZERO TOLERANCE" in prompt


# ==============================================================================
# AUDIT 4: STATE SERIALIZATION & DESERIALIZATION
# ==============================================================================

def test_dialogue_turn_serialization_roundtrip():
    """Verify DialogueTurn serialization and deserialization via Pydantic v2."""
    original_turn = DialogueTurn(
        current_intent="hold_slot",
        extracted_service="Aura Relaxation Massage",
        service_id=1,
        location_type="out_call",
        customer_location=CustomerLocation(
            address="200 George St, Sydney",
            lat=-33.864,
            lng=151.208,
        ),
        calculated_outcall_fee=34.50,
        available_slots=[
            {"time": "2026-09-11T10:00:00Z", "label": "Tomorrow 10:00 AM"},
            {"time": "2026-09-11T14:00:00Z", "label": "Tomorrow 2:00 PM"},
        ],
        selected_slot="2026-09-11T10:00:00Z",
        hold_id="HOLD-XYZ-9988",
        booking_status="held",
        escalation_reason=None,
    )

    # 1. Model dump to dict
    data = original_turn.model_dump()
    assert isinstance(data, dict)
    assert data["customer_location"]["lat"] == -33.864
    assert len(data["available_slots"]) == 2

    # 2. JSON dump
    json_str = original_turn.model_dump_json()
    assert isinstance(json_str, str)
    parsed_json = json.loads(json_str)
    assert parsed_json["hold_id"] == "HOLD-XYZ-9988"

    # 3. Model reconstruction
    reconstructed_turn = DialogueTurn.model_validate(parsed_json)
    assert reconstructed_turn.current_intent == original_turn.current_intent
    assert reconstructed_turn.extracted_service == original_turn.extracted_service
    assert reconstructed_turn.customer_location.address == "200 George St, Sydney"
    assert reconstructed_turn.customer_location.lat == -33.864
    assert reconstructed_turn.calculated_outcall_fee == 34.50
    assert reconstructed_turn.hold_id == "HOLD-XYZ-9988"
    assert reconstructed_turn.booking_status == "held"


def test_agent_state_full_serialization_roundtrip():
    """Verify full AgentState can be serialized across network/sessions and reconstructed."""
    turn = DialogueTurn(
        current_intent="select_location",
        extracted_service="Swedish Relaxation",
        service_id=1,
        location_type="in_call",
        booking_status="service_selected",
    )
    messages = [
        HumanMessage(content="Hello I'd like a massage"),
        AIMessage(content="Welcome to our clinic! Which treatment do you prefer?"),
        HumanMessage(content="Swedish Relaxation please"),
    ]

    agent_state: AgentState = {
        "messages": messages,
        "tenant_id": 1,
        "provider_id": 2,
        "customer_name": "Jane Doe",
        "customer_phone": "+61400000000",
        "customer_email": "jane@example.com",
        "conversation_id": 999,
        "dialogue_turn": turn,
        "reply_text": "In-call or out-call?",
        "should_escalate": False,
        "system_prompt": "Platform safety rules...",
    }

    # Serialize to persistent dict format
    serialized: dict = {
        "messages": messages_to_dict(agent_state["messages"]),
        "tenant_id": agent_state["tenant_id"],
        "provider_id": agent_state["provider_id"],
        "customer_name": agent_state["customer_name"],
        "customer_phone": agent_state["customer_phone"],
        "customer_email": agent_state["customer_email"],
        "conversation_id": agent_state["conversation_id"],
        "dialogue_turn": agent_state["dialogue_turn"].model_dump(),
        "reply_text": agent_state["reply_text"],
        "should_escalate": agent_state["should_escalate"],
        "system_prompt": agent_state["system_prompt"],
    }

    # Verify JSON encoding/decoding
    serialized_json = json.dumps(serialized)
    deserialized_raw = json.loads(serialized_json)

    # Reconstitute into typed AgentState
    reconstituted_state: AgentState = {
        "messages": messages_from_dict(deserialized_raw["messages"]),
        "tenant_id": deserialized_raw["tenant_id"],
        "provider_id": deserialized_raw["provider_id"],
        "customer_name": deserialized_raw["customer_name"],
        "customer_phone": deserialized_raw["customer_phone"],
        "customer_email": deserialized_raw["customer_email"],
        "conversation_id": deserialized_raw["conversation_id"],
        "dialogue_turn": DialogueTurn.model_validate(deserialized_raw["dialogue_turn"]),
        "reply_text": deserialized_raw["reply_text"],
        "should_escalate": deserialized_raw["should_escalate"],
        "system_prompt": deserialized_raw["system_prompt"],
    }

    assert len(reconstituted_state["messages"]) == 3
    assert reconstituted_state["messages"][0].content == "Hello I'd like a massage"
    assert reconstituted_state["dialogue_turn"].extracted_service == "Swedish Relaxation"
    assert reconstituted_state["customer_email"] == "jane@example.com"
    assert reconstituted_state["tenant_id"] == 1


# ==============================================================================
# AUDIT 5: CHATWOOT AGENTBOT WEBHOOK MULTI-TENANT ROUTING
# ==============================================================================

@pytest.mark.asyncio
async def test_chatwoot_webhook_resolves_correct_tenant_binding(audit_session: AsyncSession):
    """Verify Chatwoot webhook resolves binding to route Tenant 1 vs Tenant 2 independently."""
    app.dependency_overrides[get_async_db] = lambda: audit_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Message to Account 101 (Binds to Tenant 1: Aura)
        resp1 = await client.post(
            "/api/v1/chatwoot/webhook",
            json={
                "event": "message_created",
                "id": 5001,
                "content": "What treatments do you offer?",
                "message_type": "incoming",
                "conversation": {"id": 1001, "inbox_id": 1, "status": "pending"},
                "account": {"id": 101, "name": "Aura Chatwoot"},
                "sender": {"id": 11, "name": "Sarah", "type": "contact"},
            },
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "handled"
        assert "Aura Relaxation Massage" in data1["reply_sent"] or "Aura Remedial" in data1["reply_sent"]
        assert "Shiatsu" not in data1["reply_sent"]

        # Message to Account 202 (Binds to Tenant 2: Bonsai)
        resp2 = await client.post(
            "/api/v1/chatwoot/webhook",
            json={
                "event": "message_created",
                "id": 5002,
                "content": "What treatments do you offer?",
                "message_type": "incoming",
                "conversation": {"id": 2001, "inbox_id": 2, "status": "pending"},
                "account": {"id": 202, "name": "Bonsai Chatwoot"},
                "sender": {"id": 22, "name": "Kenji", "type": "contact"},
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "handled"
        assert "Bonsai Shiatsu Acupressure" in data2["reply_sent"]
        assert "Aura Relaxation" not in data2["reply_sent"]

    app.dependency_overrides.clear()
