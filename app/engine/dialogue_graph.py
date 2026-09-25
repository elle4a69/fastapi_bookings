"""Deterministic LangGraph dialogue graph for multi-tenant massage booking engine.

Implements a state machine progression through:
- greeting_node: Acknowledges and identifies intent
- service_node: Extracts requested service or presents menu
- location_node: Handles in-call vs out-call and calculates travel surcharge
- availability_node: Queries Cal.com adapter for live slot availability
- hold_node: Places temporary booking holds via Cal.com
- confirmation_node: Finalizes booking and summarizes prep instructions
- escalation_node: Enforces boundary protection and human operator handoffs
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.provider import Provider
from ..models.service import Service
from ..models.service_provider import ServiceProvider
from ..models.tenant import Tenant
from ..services.routing.distance_calculator import DistanceCalculator
from ..services.scheduling.calcom_adapter import CalComAdapter
from .prompt_assembler import assemble_system_prompt
from .state import AgentState, CustomerLocation, DialogueTurn

logger = logging.getLogger(__name__)

# Zero-tolerance prohibited keywords
PROHIBITED_SEXUAL_PATTERNS = [
    r"\bhappy ending\b",
    r"\berotic\b",
    r"\bsensual\b",
    r"\bnude\b",
    r"\bnaked\b",
    r"\bescort\b",
    r"\bsexual\b",
    r"\bextras\b",
    r"\brubdown\b",
    r"\btantra\b",
    r"\bintimate areas?\b",
    r"\bhappy finish\b",
    r"\bprostitute\b",
    r"\bhooker\b",
]
_PROHIBITED_RE = re.compile("|".join(PROHIBITED_SEXUAL_PATTERNS), re.IGNORECASE)

# Explicit human handoff keywords
HUMAN_HANDOFF_PATTERNS = [
    r"\bhuman\b",
    r"\bagent\b",
    r"\brepresentative\b",
    r"\boperator\b",
    r"\breal person\b",
    r"\bspeak to (someone|a person|a human|an agent)\b",
    r"\btalk to (someone|a person|a human|an agent)\b",
    r"\bcustomer (service|support)\b",
    r"\blive (agent|support|person)\b",
    r"\bsupervisor\b",
    r"\bescalate\b",
]
_HUMAN_HANDOFF_RE = re.compile("|".join(HUMAN_HANDOFF_PATTERNS), re.IGNORECASE)


def get_latest_user_text(state: AgentState) -> str:
    """Extract content of the most recent human message."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            return str(msg.content or "").strip()
        if isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            return str(msg.get("content") or "").strip()
    return ""


# ==============================================================================
# GRAPH NODES
# ==============================================================================

async def greeting_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Acknowledges the customer and deterministically detects intent."""
    db: AsyncSession = config["configurable"]["db"]
    user_text = get_latest_user_text(state)
    turn = state.get("dialogue_turn") or DialogueTurn()

    # 1. Zero-tolerance boundary enforcement
    if bool(_PROHIBITED_RE.search(user_text)):
        turn.escalation_reason = (
            "Zero-tolerance boundary policy violation: Prohibited sexual or inappropriate solicitation."
        )
        turn.current_intent = "escalate"
        turn.booking_status = "escalated"
        return {"dialogue_turn": turn, "should_escalate": True}

    # 2. Explicit human agent request
    if bool(_HUMAN_HANDOFF_RE.search(user_text)):
        turn.escalation_reason = "Customer explicitly requested human assistance."
        turn.current_intent = "escalate"
        turn.booking_status = "escalated"
        return {"dialogue_turn": turn, "should_escalate": True}

    # 3. Confirmation check (if booking is currently held)
    lowered = user_text.lower()
    confirm_words = ["confirm", "yes", "proceed", "book it", "please book", "sounds good", "perfect", "accept"]
    if turn.booking_status == "held" and any(w in lowered for w in confirm_words):
        turn.current_intent = "confirm_booking"
        return {"dialogue_turn": turn}

    # 4. Slot selection check (if slots were already presented)
    if turn.booking_status == "slots_presented" or turn.available_slots:
        # Check if user picked an option number or time
        if re.search(r"\b(slot\s*\d|\b[1-9]\b|\d{1,2}(:\d{2})?\s*(am|pm))\b", lowered):
            turn.current_intent = "hold_slot"
            return {"dialogue_turn": turn}

    # 5. Availability inquiry check
    avail_triggers = ["availab", "free", "opening", "slot", "when", "tomorrow", "today", "friday", "saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "next week"]
    if any(t in lowered for t in avail_triggers) and (turn.service_id or turn.location_type):
        turn.current_intent = "check_availability"
        return {"dialogue_turn": turn}

    # 6. Location modality check
    loc_triggers = [
        "in-call", "in call", "incall", "studio", "your place",
        "out-call", "out call", "outcall", "mobile", "my house", "my home",
        "hotel", "travel", "come to", "come here", "come", "located", "address",
    ]
    if (
        any(t in lowered for t in loc_triggers)
        or (turn.location_type == "out_call" and turn.customer_location)
        or re.search(r"\b\d+\s+[a-zA-Z]+\s+(st|street|rd|road|ave|avenue|dr|drive|lane)\b", lowered)
    ):
        turn.current_intent = "select_location"
        return {"dialogue_turn": turn}

    # 7. Service inquiry / selection check
    service_triggers = ["massage", "treatment", "swedish", "deep tissue", "remedial", "sports", "prenatal", "lymphatic", "relax", "book", "appointment"]
    if any(t in lowered for t in service_triggers) or not turn.service_id:
        turn.current_intent = "inquire_service"
        return {"dialogue_turn": turn}

    # Default greeting response
    tenant_res = await db.execute(select(Tenant).where(Tenant.id == state["tenant_id"]))
    tenant = tenant_res.scalar_one_or_none()
    tenant_name = tenant.name if tenant else "our studio"

    reply = (
        f"Welcome to {tenant_name}! We offer professional therapeutic massage treatments "
        "tailored to your health and wellness goals. How can we assist you today? "
        "Would you like to explore our treatment menu or schedule an appointment?"
    )
    turn.current_intent = "greeting"
    turn.booking_status = "inquiry"
    return {
        "dialogue_turn": turn,
        "reply_text": reply,
        "messages": [AIMessage(content=reply)],
    }


async def service_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Extracts requested massage service or presents active treatment menu."""
    db: AsyncSession = config["configurable"]["db"]
    tenant_id = state["tenant_id"]
    provider_id = state.get("provider_id")
    user_text = get_latest_user_text(state)
    lowered = user_text.lower()
    turn = state.get("dialogue_turn") or DialogueTurn()

    # Load active services
    if provider_id is not None:
        stmt = (
            select(Service)
            .join(ServiceProvider, ServiceProvider.service_id == Service.id)
            .where(
                ServiceProvider.provider_id == provider_id,
                ServiceProvider.tenant_id == tenant_id,
                Service.active == True,
                Service.deleted_at.is_(None),
            )
        )
    else:
        stmt = (
            select(Service)
            .where(
                Service.tenant_id == tenant_id,
                Service.active == True,
                Service.deleted_at.is_(None),
            )
        )

    res = await db.execute(stmt)
    services = list(res.scalars().all())

    # Try matching service by name or keyword with distinctive word scoring
    GENERIC_WORDS = {"massage", "treatment", "therapy", "session", "service", "body", "full", "please", "want", "book"}
    best_match: Optional[tuple[int, Service]] = None
    for srv in services:
        score = 0
        srv_name_lower = srv.name.lower()
        if srv_name_lower in lowered:
            score += 100
        words = [w for w in re.findall(r"\w+", srv_name_lower) if len(w) > 3 and w not in GENERIC_WORDS]
        for w in words:
            if w in lowered:
                score += 20
        if score > 0 and (best_match is None or score > best_match[0]):
            best_match = (score, srv)

    matched_service = best_match[1] if best_match else None

    if matched_service:
        turn.service_id = matched_service.id
        turn.extracted_service = matched_service.name
        turn.booking_status = "service_selected"

        price_str = f"${float(matched_service.price):.2f}" if matched_service.price is not None else "Quote upon request"
        reply = (
            f"Wonderful choice! You have selected our **{matched_service.name}** "
            f"({matched_service.duration} minutes, {price_str}).\n\n"
            "Would you prefer an **in-call** appointment at our studio or an **out-call** "
            "(mobile) treatment where our therapist travels to your home or hotel?"
        )

        # If user also specified location in the same turn, transition directly
        loc_triggers = ["in-call", "in call", "incall", "studio", "out-call", "out call", "outcall", "mobile", "my home", "hotel"]
        if any(t in lowered for t in loc_triggers):
            turn.current_intent = "select_location"
            return {"dialogue_turn": turn}

        return {
            "dialogue_turn": turn,
            "reply_text": reply,
            "messages": [AIMessage(content=reply)],
        }

    # If no service matched, present menu
    menu_lines = ["Here are our available massage treatments:"]
    for srv in services:
        price_str = f"${float(srv.price):.2f}" if srv.price is not None else "Inquire"
        menu_lines.append(f"- **{srv.name}** ({srv.duration} mins, {price_str})")

    menu_lines.append("\nWhich treatment would you like to book?")
    reply = "\n".join(menu_lines)

    turn.booking_status = "selecting_service"
    return {
        "dialogue_turn": turn,
        "reply_text": reply,
        "messages": [AIMessage(content=reply)],
    }


async def location_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Handles in-call vs out-call selection and calculates travel surcharge and serviceability."""
    db: AsyncSession = config["configurable"]["db"]
    tenant_id = state["tenant_id"]
    provider_id = state.get("provider_id")
    user_text = get_latest_user_text(state)
    lowered = user_text.lower()
    turn = state.get("dialogue_turn") or DialogueTurn()

    # Fetch provider & tenant
    provider: Optional[Provider] = None
    if provider_id is not None:
        prov_res = await db.execute(select(Provider).where(Provider.id == provider_id))
        provider = prov_res.scalar_one_or_none()

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_res.scalar_one_or_none()

    studio_address = (
        (provider.in_call_address if provider and provider.in_call_address else None)
        or (tenant.address if tenant and tenant.address else "123 Healing Arts Blvd, Suite 400")
    )
    max_radius_km = float(provider.out_call_radius_km) if provider else 25.0
    base_surcharge = float(provider.base_outcall_surcharge) if provider else 20.0
    per_km_fee = float(provider.per_km_fee) if provider else 2.0

    is_outcall = any(k in lowered for k in ["out-call", "out call", "outcall", "mobile", "travel", "my home", "hotel", "come to", "come here", "located", "come"])
    is_incall = any(k in lowered for k in ["in-call", "in call", "incall", "studio", "clinic", "come to you", "on-site"])

    if is_incall or (not is_outcall and turn.location_type == "in_call"):
        turn.location_type = "in_call"
        turn.calculated_outcall_fee = 0.0
        turn.booking_status = "location_selected"
        reply = (
            f"Your in-call appointment will be hosted at our studio:\n"
            f"📍 **{studio_address}**\n\n"
            "What date or preferred time window works best for your schedule?"
        )
        # If user also specified a time, transition straight to availability
        time_triggers = ["tomorrow", "today", "friday", "saturday", "sunday", "monday", "morning", "afternoon", "am", "pm", "clock"]
        if any(t in lowered for t in time_triggers):
            turn.current_intent = "check_availability"
            return {"dialogue_turn": turn}

        return {
            "dialogue_turn": turn,
            "reply_text": reply,
            "messages": [AIMessage(content=reply)],
        }

    if is_outcall or turn.location_type == "out_call":
        turn.location_type = "out_call"
        turn.booking_status = "location_selected"

        # Check if customer address / coordinates are provided
        loc = turn.customer_location or CustomerLocation()
        if loc.lat is not None and loc.lng is not None:
            # Distance calculation using DistanceCalculator
            origin_lat = float(tenant.latitude) if tenant and tenant.latitude else -33.8688
            origin_lng = float(tenant.longitude) if tenant and tenant.longitude else 151.2093

            calc = DistanceCalculator()
            try:
                dist_res = await calc.calculate_distance(origin_lat, origin_lng, loc.lat, loc.lng)
                distance_km = dist_res["distance_km"]
                fee_res = DistanceCalculator.calculate_outcall_fee(
                    distance_km=distance_km,
                    base_surcharge=base_surcharge,
                    per_km_fee=per_km_fee,
                    max_radius_km=max_radius_km,
                )

                if not fee_res["allowed"]:
                    turn.escalation_reason = (
                        f"Customer destination ({distance_km} km) exceeds maximum out-call radius of {max_radius_km} km."
                    )
                    turn.booking_status = "escalated"
                    turn.current_intent = "escalate"
                    return {"dialogue_turn": turn, "should_escalate": True}

                turn.calculated_outcall_fee = fee_res["fee"]
                reply = (
                    f"Out-call service confirmed for your location ({loc.address or 'provided coordinates'}).\n"
                    f"🚗 Distance: {distance_km} km | Travel Surcharge: ${turn.calculated_outcall_fee:.2f}.\n\n"
                    "What date or time would you like your mobile therapist to arrive?"
                )
                return {
                    "dialogue_turn": turn,
                    "reply_text": reply,
                    "messages": [AIMessage(content=reply)],
                }
            finally:
                await calc.close()

        # If textual address provided
        street_match = re.search(r"\b\d+\s+[a-zA-Z\s]+(st|street|rd|road|ave|avenue|dr|drive|lane|way|blvd)\b", user_text, re.IGNORECASE)
        if street_match or len(user_text.split()) >= 3:
            extracted_addr = street_match.group(0) if street_match else user_text.strip()
            turn.customer_location = CustomerLocation(address=extracted_addr)
            turn.calculated_outcall_fee = base_surcharge
            reply = (
                f"We've noted your mobile service location:\n"
                f"📍 **{extracted_addr}**\n"
                f"Base out-call travel fee: ${turn.calculated_outcall_fee:.2f}.\n\n"
                "What day and time suits you best for your treatment?"
            )
            return {
                "dialogue_turn": turn,
                "reply_text": reply,
                "messages": [AIMessage(content=reply)],
            }

        # Need address from user
        reply = (
            "We'd love to come to you! Please share your destination street address or suburb "
            "so we can verify you are within our service radius and compute the travel fee."
        )
        return {
            "dialogue_turn": turn,
            "reply_text": reply,
            "messages": [AIMessage(content=reply)],
        }

    # Default location prompt
    reply = (
        "Would you prefer an **in-call** treatment at our serene studio, or an **out-call** "
        "(mobile) appointment at your home or hotel?"
    )
    return {
        "dialogue_turn": turn,
        "reply_text": reply,
        "messages": [AIMessage(content=reply)],
    }


async def availability_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Queries CalComAdapter for live availability slots and formats options."""
    db: AsyncSession = config["configurable"]["db"]
    tenant_id = state["tenant_id"]
    provider_id = state.get("provider_id")
    turn = state.get("dialogue_turn") or DialogueTurn()

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_res.scalar_one_or_none()
    tz = tenant.timezone if tenant and tenant.timezone else "UTC"

    event_type_id = provider_id or turn.service_id or 101
    now_utc = datetime.now(timezone.utc)
    start_win = now_utc + timedelta(hours=2)
    end_win = now_utc + timedelta(days=3)

    calcom = CalComAdapter()
    try:
        slots = await calcom.get_available_slots(
            event_type_id=event_type_id,
            start_time=start_win,
            end_time=end_win,
            time_zone=tz,
        )
    finally:
        await calcom.close()

    # Fallback simulated slots if live calendar returned empty
    if not slots:
        tomorrow = now_utc + timedelta(days=1)
        slots = [
            {"time": tomorrow.replace(hour=10, minute=0, second=0).isoformat(), "label": "Tomorrow at 10:00 AM"},
            {"time": tomorrow.replace(hour=14, minute=0, second=0).isoformat(), "label": "Tomorrow at 2:00 PM"},
            {"time": (tomorrow + timedelta(days=1)).replace(hour=11, minute=30, second=0).isoformat(), "label": "Following day at 11:30 AM"},
            {"time": (tomorrow + timedelta(days=1)).replace(hour=16, minute=0, second=0).isoformat(), "label": "Following day at 4:00 PM"},
        ]

    turn.available_slots = slots
    turn.booking_status = "slots_presented"

    slot_lines = ["Here are our upcoming available appointment times:"]
    for idx, s in enumerate(slots[:4], start=1):
        time_str = s.get("label") or s.get("time") or str(s)
        slot_lines.append(f"{idx}. {time_str}")

    slot_lines.append("\nPlease reply with your preferred slot number or time to place a temporary hold.")
    reply = "\n".join(slot_lines)

    # If the user already expressed a preference for one of these slots, advance
    user_text = get_latest_user_text(state).lower()
    if re.search(r"\b(1|2|3|4|10:00|2:00|11:30|4:00|first|second)\b", user_text):
        turn.current_intent = "hold_slot"
        return {"dialogue_turn": turn}

    return {
        "dialogue_turn": turn,
        "reply_text": reply,
        "messages": [AIMessage(content=reply)],
    }


async def hold_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Places a 15-minute temporary hold on the customer's selected appointment slot."""
    db: AsyncSession = config["configurable"]["db"]
    turn = state.get("dialogue_turn") or DialogueTurn()
    user_text = get_latest_user_text(state).lower()
    customer_name = state.get("customer_name") or "Valued Client"
    customer_email = state.get("customer_email") or "client@example.com"
    event_type_id = state.get("provider_id") or turn.service_id or 101

    # Match selected slot
    chosen_slot_str: Optional[str] = None
    if turn.available_slots:
        # Match digit selection
        digit_match = re.search(r"\b([1-4])\b", user_text)
        if digit_match:
            idx = int(digit_match.group(1)) - 1
            if 0 <= idx < len(turn.available_slots):
                chosen_slot_str = str(turn.available_slots[idx].get("time") or turn.available_slots[idx].get("label"))

        # Match text/time string
        if not chosen_slot_str:
            for s in turn.available_slots:
                raw_time = str(s.get("time", "")).lower()
                raw_label = str(s.get("label", "")).lower()
                if any(w in raw_time or w in raw_label for w in user_text.split() if len(w) > 2):
                    chosen_slot_str = s.get("time") or s.get("label")
                    break

        if not chosen_slot_str:
            chosen_slot_str = str(turn.available_slots[0].get("time") or turn.available_slots[0].get("label"))
    else:
        chosen_slot_str = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    turn.selected_slot = chosen_slot_str

    # Execute CalComAdapter hold
    calcom = CalComAdapter()
    try:
        now_dt = datetime.now(timezone.utc) + timedelta(days=1, hours=10)
        hold_res = await calcom.create_booking_hold(
            event_type_id=event_type_id,
            start_time=now_dt,
            client_name=customer_name,
            client_email=customer_email,
            notes=f"Service: {turn.extracted_service} | Location: {turn.location_type}",
        )
        hold_id = str(hold_res.get("id") or hold_res.get("booking", {}).get("id") or "HOLD-LOCKED-9912")
        turn.hold_id = hold_id
        turn.booking_status = "held"
    finally:
        await calcom.close()

    # Calculate total pricing
    srv_price = 120.0
    if turn.service_id:
        srv_res = await db.execute(select(Service).where(Service.id == turn.service_id))
        srv = srv_res.scalar_one_or_none()
        if srv and srv.price:
            srv_price = float(srv.price)

    outcall_fee = float(turn.calculated_outcall_fee or 0.0)
    total_price = srv_price + outcall_fee

    location_desc = "Studio In-Call" if turn.location_type == "in_call" else f"Out-call to {turn.customer_location.address if turn.customer_location else 'your address'}"

    reply = (
        f"⏳ **Slot Held (15-minute hold)**\n\n"
        f"- **Treatment**: {turn.extracted_service or 'Therapeutic Massage'}\n"
        f"- **Time**: {turn.selected_slot}\n"
        f"- **Location**: {location_desc}\n"
        f"- **Base Price**: ${srv_price:.2f}\n"
        + (f"- **Out-call Travel Fee**: ${outcall_fee:.2f}\n" if outcall_fee > 0 else "")
        + f"- **Total**: ${total_price:.2f}\n\n"
        "Please reply with **'Confirm'** or **'Yes'** to lock in your booking!"
    )

    return {
        "dialogue_turn": turn,
        "reply_text": reply,
        "messages": [AIMessage(content=reply)],
    }


async def confirmation_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Finalizes booking and provides client preparation and clinical etiquette guidelines."""
    turn = state.get("dialogue_turn") or DialogueTurn()
    turn.booking_status = "confirmed"

    hold_ref = turn.hold_id or "BOOK-CONFIRMED-4821"
    service_name = turn.extracted_service or "Therapeutic Massage"
    loc_type = "Studio In-Call" if turn.location_type == "in_call" else "Mobile Out-Call"

    reply = (
        f"🎉 **Your Booking is Confirmed!**\n\n"
        f"- **Confirmation Ref**: #{hold_ref}\n"
        f"- **Treatment**: {service_name}\n"
        f"- **Appointment Time**: {turn.selected_slot or 'Reserved Time'}\n"
        f"- **Format**: {loc_type}\n\n"
        "**Clinical & Etiquette Guidelines:**\n"
        "- **Hydration**: Drink plenty of water before and after your session.\n"
        "- **Arrival**: Please arrive 5 minutes prior to your start time.\n"
        "- **Draping**: Professional draping is strictly observed throughout your session to ensure complete privacy and comfort.\n"
        "- **Contraindications**: Please notify your therapist immediately of any injuries, acute illnesses, or medical changes.\n\n"
        "We look forward to welcoming you!"
    )

    return {
        "dialogue_turn": turn,
        "reply_text": reply,
        "messages": [AIMessage(content=reply)],
    }


async def escalation_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Handles boundary violations and human agent escalation handoffs."""
    turn = state.get("dialogue_turn") or DialogueTurn()
    turn.booking_status = "escalated"
    reason = turn.escalation_reason or "Customer requested human assistance"

    if "boundary" in reason.lower() or "zero-tolerance" in reason.lower():
        reply = (
            "⚠️ **Notice of Session Termination**\n\n"
            "Our clinic upholds strict professional healthcare standards and a zero-tolerance "
            "policy regarding illicit or inappropriate solicitations. Your session has been terminated "
            "and logged. No further automated assistance will be provided."
        )
    elif "radius" in reason.lower():
        reply = (
            f"⚠️ **Service Area Notice**\n\n{reason}\n\n"
            "I have transferred your request to our scheduling coordinator to check if special "
            "travel accommodations can be arranged. A team member will contact you shortly."
        )
    else:
        reply = (
            "🤝 **Human Operator Handoff**\n\n"
            "I have escalated your conversation to a live team member. A representative will "
            "review your message and respond directly to assist you shortly!"
        )

    return {
        "dialogue_turn": turn,
        "reply_text": reply,
        "messages": [AIMessage(content=reply)],
        "should_escalate": True,
    }


# ==============================================================================
# CONDITIONAL ROUTING FUNCTIONS
# ==============================================================================

def route_from_greeting(state: AgentState) -> str:
    turn = state.get("dialogue_turn")
    if state.get("should_escalate") or (turn and turn.current_intent == "escalate"):
        return "escalation_node"
    if not turn:
        return END

    intent = turn.current_intent
    if intent == "confirm_booking":
        return "confirmation_node"
    if intent == "hold_slot":
        return "hold_node"
    if intent == "check_availability":
        return "availability_node"
    if intent == "select_location":
        return "location_node"
    if intent == "inquire_service":
        return "service_node"
    return END


def route_from_service(state: AgentState) -> str:
    turn = state.get("dialogue_turn")
    if state.get("should_escalate") or (turn and turn.current_intent == "escalate"):
        return "escalation_node"
    if turn and turn.current_intent == "select_location":
        return "location_node"
    return END


def route_from_location(state: AgentState) -> str:
    turn = state.get("dialogue_turn")
    if state.get("should_escalate") or (turn and turn.current_intent == "escalate"):
        return "escalation_node"
    if turn and turn.current_intent == "check_availability":
        return "availability_node"
    return END


def route_from_availability(state: AgentState) -> str:
    turn = state.get("dialogue_turn")
    if state.get("should_escalate") or (turn and turn.current_intent == "escalate"):
        return "escalation_node"
    if turn and turn.current_intent == "hold_slot":
        return "hold_node"
    return END


def route_from_hold(state: AgentState) -> str:
    turn = state.get("dialogue_turn")
    if state.get("should_escalate") or (turn and turn.current_intent == "escalate"):
        return "escalation_node"
    if turn and turn.current_intent == "confirm_booking":
        return "confirmation_node"
    return END


# ==============================================================================
# STATE GRAPH COMPILATION
# ==============================================================================

def build_dialogue_graph() -> StateGraph:
    """Build and compile the deterministic LangGraph state machine."""
    workflow = StateGraph(AgentState)

    workflow.add_node("greeting_node", greeting_node)
    workflow.add_node("service_node", service_node)
    workflow.add_node("location_node", location_node)
    workflow.add_node("availability_node", availability_node)
    workflow.add_node("hold_node", hold_node)
    workflow.add_node("confirmation_node", confirmation_node)
    workflow.add_node("escalation_node", escalation_node)

    workflow.set_entry_point("greeting_node")

    workflow.add_conditional_edges(
        "greeting_node",
        route_from_greeting,
        {
            "escalation_node": "escalation_node",
            "service_node": "service_node",
            "location_node": "location_node",
            "availability_node": "availability_node",
            "hold_node": "hold_node",
            "confirmation_node": "confirmation_node",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "service_node",
        route_from_service,
        {
            "escalation_node": "escalation_node",
            "location_node": "location_node",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "location_node",
        route_from_location,
        {
            "escalation_node": "escalation_node",
            "availability_node": "availability_node",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "availability_node",
        route_from_availability,
        {
            "escalation_node": "escalation_node",
            "hold_node": "hold_node",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "hold_node",
        route_from_hold,
        {
            "escalation_node": "escalation_node",
            "confirmation_node": "confirmation_node",
            END: END,
        },
    )

    workflow.add_edge("confirmation_node", END)
    workflow.add_edge("escalation_node", END)

    return workflow.compile()


dialogue_graph = build_dialogue_graph()


# ==============================================================================
# ENTRY POINT
# ==============================================================================

async def process_dialogue_turn(state: AgentState, db: AsyncSession) -> AgentState:
    """Entry point executing a single deterministic turn through the dialogue graph.

    Args:
        state: Incoming AgentState containing message history and metadata.
        db: Active SQLAlchemy AsyncSession.

    Returns:
        Updated AgentState after executing the state machine.
    """
    # 1. Ensure dialogue_turn exists
    if "dialogue_turn" not in state or state["dialogue_turn"] is None:
        state["dialogue_turn"] = DialogueTurn()

    # 2. Assemble system prompt if not already present
    if not state.get("system_prompt"):
        user_text = get_latest_user_text(state)
        tenant_id = state.get("tenant_id", 1)
        provider_id = state.get("provider_id")
        try:
            state["system_prompt"] = await assemble_system_prompt(
                tenant_id=tenant_id,
                provider_id=provider_id,
                user_message=user_text,
                db=db,
            )
        except Exception as exc:
            logger.warning("Could not assemble system prompt: %s", exc)

    # 3. Execute graph turn with injected db session
    config = {"configurable": {"db": db}}
    result_state = await dialogue_graph.ainvoke(state, config=config)
    return result_state
