"""Unit and integration tests for Track 3: LangGraph Dialogue Engine & Multi-Tenant Prompt Assembler."""

from datetime import datetime, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routers.chatwoot_agentbot import requires_human_handoff
from app.db.async_session import get_async_db
from app.db.database import Base
from app.engine.dialogue_graph import dialogue_graph, process_dialogue_turn
from app.engine.prompt_assembler import assemble_system_prompt
from app.engine.state import AgentState, CustomerLocation, DialogueTurn
from app.main import app
from app.models.curated_memory import CuratedMemory
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.sms_chatwoot import SmsChatwootBinding
from app.models.tenant import Tenant


@pytest_asyncio.fixture
async def async_test_session():
    """Provides an isolated in-memory SQLite database session for unit testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        # Seed test Tenant
        tenant = Tenant(
            name="Serenity Wellness Spa",
            subdomain="serenity",
            address="78 Oceanview Avenue, Sydney",
            timezone="Australia/Sydney",
            phone="+61400111222",
            email="info@serenitywellness.test",
            latitude=-33.8688,
            longitude=151.2093,
        )
        session.add(tenant)
        await session.flush()

        # Seed test Provider
        provider = Provider(
            tenant_id=tenant.id,
            name="Sarah Jenkins",
            in_call_address="78 Oceanview Avenue, Suite 4, Sydney",
            out_call_radius_km=30.0,
            base_outcall_surcharge=25.00,
            per_km_fee=2.50,
            turnaround_buffer_mins=15,
        )
        session.add(provider)
        await session.flush()

        # Seed test Services
        service_swedish = Service(
            tenant_id=tenant.id,
            name="Swedish Relaxation Massage",
            description="Gentle full body relaxation to calm the nervous system.",
            duration=60,
            price=110.00,
            allow_in_call=True,
            allow_out_call=True,
            active=True,
        )
        service_deep = Service(
            tenant_id=tenant.id,
            name="Deep Tissue & Remedial Massage",
            description="Therapeutic targeted pressure for chronic tension and aches.",
            duration=90,
            price=155.00,
            allow_in_call=True,
            allow_out_call=True,
            active=True,
        )
        session.add_all([service_swedish, service_deep])
        await session.flush()

        # Associate Provider with Services
        session.add_all([
            ServiceProvider(tenant_id=tenant.id, service_id=service_swedish.id, provider_id=provider.id),
            ServiceProvider(tenant_id=tenant.id, service_id=service_deep.id, provider_id=provider.id),
        ])
        await session.flush()

        # Seed Curated Memory
        dummy_vector = [0.01] * 1536
        memory = CuratedMemory(
            tenant_id=tenant.id,
            provider_id=provider.id,
            category="policy",
            user_query="What is your cancellation and draping policy?",
            ideal_response="Cancellations require 24 hours notice. Professional sheet draping is strictly observed throughout the treatment.",
            embedding=dummy_vector,
            confidence_score=0.98,
        )
        session.add(memory)
        await session.commit()

        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_assembler(async_test_session: AsyncSession):
    """Verify composite prompt engine combines platform rules, dynamic profile, and memories."""
    prompt = await assemble_system_prompt(
        tenant_id=1,
        provider_id=1,
        user_message="What services do you offer and what is your cancellation policy?",
        db=async_test_session,
    )

    # 1. Platform rules assertions
    assert "IMMUTABLE PLATFORM RULES" in prompt
    assert "Strict Professional Draping" in prompt
    assert "Medical Contraindications" in prompt
    assert "Strict Zero-Tolerance Boundary Policies" in prompt

    # 2. Dynamic profile assertions
    assert "Serenity Wellness Spa" in prompt
    assert "Sarah Jenkins" in prompt
    assert "78 Oceanview Avenue" in prompt
    assert "Max Out-call Radius: 30.0 km" in prompt
    assert "Base Out-call Travel Surcharge: $25.00" in prompt
    assert "Per-KM Travel Fee: $2.50/km" in prompt

    # 3. Services assertions
    assert "Swedish Relaxation Massage" in prompt
    assert "Deep Tissue & Remedial Massage" in prompt
    assert "$110.00" in prompt
    assert "$155.00" in prompt

    # 4. Curated memory assertions
    assert "VERIFIED BUSINESS KNOWLEDGE" in prompt
    assert "What is your cancellation and draping policy?" in prompt
    assert "Cancellations require 24 hours notice" in prompt


def test_dialogue_state_schema():
    """Verify DialogueTurn and AgentState Pydantic v2 schemas and validation."""
    turn = DialogueTurn(
        current_intent="inquire_service",
        extracted_service="Swedish Relaxation Massage",
        service_id=1,
        location_type="in_call",
        calculated_outcall_fee=0.0,
        booking_status="service_selected",
    )
    assert turn.current_intent == "inquire_service"
    assert turn.extracted_service == "Swedish Relaxation Massage"
    assert turn.location_type == "in_call"
    assert turn.calculated_outcall_fee == 0.0

    # CustomerLocation
    loc = CustomerLocation(address="120 George St, Sydney", lat=-33.86, lng=151.21)
    turn.customer_location = loc
    assert turn.customer_location.address == "120 George St, Sydney"


@pytest.mark.asyncio
async def test_greeting_and_service_menu(async_test_session: AsyncSession):
    """Test initial greeting and presenting available services menu."""
    state: AgentState = {
        "messages": [HumanMessage(content="Hello, I'd like some information about massages")],
        "tenant_id": 1,
        "provider_id": 1,
        "customer_name": "David",
        "dialogue_turn": DialogueTurn(),
    }

    result = await process_dialogue_turn(state, async_test_session)
    reply = result.get("reply_text", "")
    turn = result["dialogue_turn"]

    assert "Swedish Relaxation Massage" in reply or "Deep Tissue" in reply or "Welcome to" in reply
    assert not result.get("should_escalate")


@pytest.mark.asyncio
async def test_service_selection_and_location_prompt(async_test_session: AsyncSession):
    """Test selecting a specific service prompts for in-call vs out-call location."""
    state: AgentState = {
        "messages": [HumanMessage(content="I want to book a Deep Tissue massage please")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": DialogueTurn(),
    }

    result = await process_dialogue_turn(state, async_test_session)
    reply = result.get("reply_text", "")
    turn = result["dialogue_turn"]

    assert "Deep Tissue" in turn.extracted_service
    assert turn.booking_status == "service_selected"
    assert "in-call" in reply.lower()
    assert "out-call" in reply.lower()


@pytest.mark.asyncio
async def test_location_selection_incall(async_test_session: AsyncSession):
    """Test selecting in-call sets studio address and zero out-call fee."""
    turn = DialogueTurn(
        service_id=2,
        extracted_service="Deep Tissue & Remedial Massage",
        booking_status="service_selected",
    )
    state: AgentState = {
        "messages": [HumanMessage(content="I'd prefer an in-call session at your studio")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": turn,
    }

    result = await process_dialogue_turn(state, async_test_session)
    reply = result.get("reply_text", "")
    turn = result["dialogue_turn"]

    assert turn.location_type == "in_call"
    assert turn.calculated_outcall_fee == 0.0
    assert "studio" in reply.lower() or "oceanview" in reply.lower()


@pytest.mark.asyncio
async def test_location_selection_outcall(async_test_session: AsyncSession):
    """Test selecting out-call calculates travel fee."""
    turn = DialogueTurn(
        service_id=2,
        extracted_service="Deep Tissue & Remedial Massage",
        booking_status="service_selected",
    )
    state: AgentState = {
        "messages": [HumanMessage(content="Can you do out-call to 200 George Street, Sydney?")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": turn,
    }

    result = await process_dialogue_turn(state, async_test_session)
    reply = result.get("reply_text", "")
    turn = result["dialogue_turn"]

    assert turn.location_type == "out_call"
    assert turn.calculated_outcall_fee is not None
    assert turn.calculated_outcall_fee >= 25.0


@pytest.mark.asyncio
async def test_outcall_radius_exceeded_escalation(async_test_session: AsyncSession):
    """Test that customer location exceeding max travel radius triggers escalation."""
    turn = DialogueTurn(
        service_id=1,
        extracted_service="Swedish Relaxation Massage",
        location_type="out_call",
        # Melbourne coordinates relative to Sydney (~700km)
        customer_location=CustomerLocation(address="Melbourne CBD", lat=-37.8136, lng=144.9631),
    )
    state: AgentState = {
        "messages": [HumanMessage(content="I'm located in Melbourne, can you come here?")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": turn,
    }

    result = await process_dialogue_turn(state, async_test_session)
    assert result.get("should_escalate") is True
    assert result["dialogue_turn"].booking_status == "escalated"
    assert "radius" in (result["dialogue_turn"].escalation_reason or "").lower()


@pytest.mark.asyncio
async def test_availability_and_hold_progression(async_test_session: AsyncSession):
    """Test slot presentation and temporary hold placement."""
    turn = DialogueTurn(
        service_id=1,
        extracted_service="Swedish Relaxation Massage",
        location_type="in_call",
        calculated_outcall_fee=0.0,
        booking_status="location_selected",
    )
    # 1. Ask for availability
    state_avail: AgentState = {
        "messages": [HumanMessage(content="When are your available times tomorrow?")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": turn,
    }
    res_avail = await process_dialogue_turn(state_avail, async_test_session)
    assert len(res_avail["dialogue_turn"].available_slots) > 0
    assert "available appointment times" in res_avail.get("reply_text", "").lower()

    # 2. Select slot 1 to hold
    state_hold: AgentState = {
        "messages": [HumanMessage(content="Please hold slot 1 for me")],
        "tenant_id": 1,
        "provider_id": 1,
        "customer_name": "David Miller",
        "customer_email": "david@example.com",
        "dialogue_turn": res_avail["dialogue_turn"],
    }
    res_hold = await process_dialogue_turn(state_hold, async_test_session)
    turn_hold = res_hold["dialogue_turn"]
    assert turn_hold.booking_status == "held"
    assert turn_hold.hold_id is not None
    assert "Slot Held" in res_hold.get("reply_text", "")

    # 3. Confirm held booking
    state_confirm: AgentState = {
        "messages": [HumanMessage(content="Yes, please confirm this booking!")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": turn_hold,
    }
    res_confirm = await process_dialogue_turn(state_confirm, async_test_session)
    assert res_confirm["dialogue_turn"].booking_status == "confirmed"
    assert "Your Booking is Confirmed!" in res_confirm.get("reply_text", "")
    assert "Draping" in res_confirm.get("reply_text", "")


@pytest.mark.asyncio
async def test_zero_tolerance_boundary_violation(async_test_session: AsyncSession):
    """Test immediate escalation and session termination on sexual/illicit solicitation."""
    state: AgentState = {
        "messages": [HumanMessage(content="Do your therapists offer sensual massage with a happy ending?")],
        "tenant_id": 1,
        "provider_id": 1,
        "dialogue_turn": DialogueTurn(),
    }

    result = await process_dialogue_turn(state, async_test_session)
    assert result.get("should_escalate") is True
    turn = result["dialogue_turn"]
    assert turn.booking_status == "escalated"
    assert "boundary" in (turn.escalation_reason or "").lower()
    assert "zero-tolerance" in result.get("reply_text", "").lower() or "terminated" in result.get("reply_text", "").lower()


@pytest.mark.asyncio
async def test_chatwoot_agentbot_webhook_integration(async_test_session: AsyncSession):
    """Verify Chatwoot AgentBot webhook invokes dialogue engine and handles escalation."""
    app.dependency_overrides[get_async_db] = lambda: async_test_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Normal customer message
        payload_normal = {
            "event": "message_created",
            "id": 1001,
            "content": "Hi! What massage treatments do you offer?",
            "message_type": "incoming",
            "conversation": {"id": 501, "inbox_id": 1, "status": "pending"},
            "account": {"id": 1, "name": "Serenity Wellness"},
            "sender": {"id": 42, "name": "Emma Watson", "type": "contact"},
        }

        resp = await client.post("/api/v1/chatwoot/webhook", json=payload_normal)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "handled"
        assert data["action"] == "agent_execution"
        assert "reply_sent" in data
        assert len(data["reply_sent"]) > 0

        # 2. Prohibited message -> triggers escalation
        payload_violation = {
            "event": "message_created",
            "id": 1002,
            "content": "Do you provide sensual happy finish services?",
            "message_type": "incoming",
            "conversation": {"id": 501, "inbox_id": 1, "status": "pending"},
            "account": {"id": 1, "name": "Serenity Wellness"},
            "sender": {"id": 42, "name": "Emma Watson", "type": "contact"},
        }

        resp_viol = await client.post("/api/v1/chatwoot/webhook", json=payload_violation)
        assert resp_viol.status_code == 200
        data_viol = resp_viol.json()
        assert data_viol["status"] == "handled"
        assert data_viol["action"] == "human_handoff"
        assert "Zero-tolerance" in data_viol["reason"]

    app.dependency_overrides.clear()
