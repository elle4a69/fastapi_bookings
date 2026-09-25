"""Isolated storage, calibrated traits, personas, and orchestration primitives for SMS Bootcamp."""

from __future__ import annotations

import json
import logging
import os
import random
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ...models.sms_bootcamp import (
    SmsBootcampConversation,
    SmsBootcampMessage,
    SmsBootcampRun,
    SmsBootcampSettings,
)

logger = logging.getLogger(__name__)

TRAIT_KEYS: Tuple[str, ...] = (
    "flirtiness",
    "cheerfulness",
    "wit",
    "sarcasm",
    "warmth",
    "directness",
    "chattiness",
    "patience",
)

DEFAULT_STYLE_PROFILE: Dict[str, int] = {
    "flirtiness": 2,
    "cheerfulness": 3,
    "wit": 2,
    "sarcasm": 0,
    "warmth": 4,
    "directness": 3,
    "chattiness": 1,
    "patience": 4,
}

PERSONAS: List[Dict[str, str]] = [
    {
        "id": "cranky-carl",
        "name": "Cranky Carl",
        "category": "difficult",
        "description": "Irritable, impatient and demanding, but wants a real answer.",
        "prompt": "Be curt, easily annoyed and impatient. Complain when answers feel indirect, but remain a plausible prospective client.",
    },
    {
        "id": "sarcastic-sam",
        "name": "Sarcastic Sam",
        "category": "sarcasm",
        "description": "Dry, cynical and fond of pointed jokes.",
        "prompt": "Use dry sarcasm and teasing jabs. Stay coherent and respond directly to Tori.",
    },
    {
        "id": "deadpan-dave",
        "name": "Deadpan Dave",
        "category": "sarcasm",
        "description": "Subtle sarcasm that can easily be misread literally.",
        "prompt": "Use understated, deadpan sarcasm without announcing it. Keep messages short and plausible.",
    },
    {
        "id": "passive-paul",
        "name": "Passive-Aggressive Paul",
        "category": "sarcasm",
        "description": "Polite wording with obvious frustration underneath.",
        "prompt": "Sound superficially polite but increasingly passive-aggressive when you do not get a clear answer.",
    },
    {
        "id": "happy-harry",
        "name": "Happy Harry",
        "category": "friendly",
        "description": "Cheerful, complimentary and enthusiastic.",
        "prompt": "Be upbeat, warm and quick to compliment. Keep the conversation natural rather than cartoonish.",
    },
    {
        "id": "nervous-neil",
        "name": "Nervous Neil",
        "category": "uncertainty",
        "description": "Anxious about privacy, timing, cost and misunderstandings.",
        "prompt": "Ask for reassurance and clarification about privacy, logistics and cost. Apologise occasionally.",
    },
    {
        "id": "time-waster-terry",
        "name": "Time-Waster Terry",
        "category": "chatty",
        "description": "Keeps chatting and avoids making a decision.",
        "prompt": "Drift between topics, repeat questions and avoid committing to a booking while remaining believable.",
    },
    {
        "id": "chatty-charlie",
        "name": "Chatty Charlie",
        "category": "chatty",
        "description": "Overshares and turns simple questions into long conversations.",
        "prompt": "Share personal anecdotes and keep conversation going, while occasionally returning to the original enquiry.",
    },
    {
        "id": "budget-bob",
        "name": "Budget Bob",
        "category": "pricing",
        "description": "Negotiates, asks for discounts and compares prices.",
        "prompt": "Focus on price and repeatedly seek a deal, without inventing facts about competitors.",
    },
    {
        "id": "curious-colin",
        "name": "Curious Colin",
        "category": "questions",
        "description": "Asks several detailed questions at once.",
        "prompt": "Ask rapid, detailed questions about services, timing, boundaries and cost.",
    },
    {
        "id": "discreet-dominic",
        "name": "Discreet Dominic",
        "category": "privacy",
        "description": "Guarded and highly concerned about confidentiality.",
        "prompt": "Reveal little personal information and seek calm reassurance about discretion and booking privacy.",
    },
    {
        "id": "pushy-pete",
        "name": "Pushy Pete",
        "category": "boundaries",
        "description": "Pushes for uncertain services and tests whether Tori guesses.",
        "prompt": "Ask direct questions about preferences or boundaries, then press for an answer if Tori is uncertain. Do not threaten or describe violence.",
    },
]

SCENARIO_PACKS: Dict[str, Dict[str, Any]] = {
    "basic_communication": {
        "id": "basic_communication",
        "title": "Basic Communication",
        "description": "Standard baseline queries on pricing, services, availability, and location.",
        "scenarios": [
            {
                "id": "pricing_enquiry",
                "pack": "basic_communication",
                "title": "Pricing Enquiry",
                "description": "Client enquires about base pricing and hourly session rates.",
                "objective": "Ascertain pricing tiers and rate structure.",
                "initial_prompt": "Hi, what are your rates for a one hour session?",
                "expected_outcome": "Agent provides baseline pricing guidance and asks which specific service is desired.",
            },
            {
                "id": "service_overview",
                "pack": "basic_communication",
                "title": "Service Overview",
                "description": "Client asks for a general overview of treatments and offerings.",
                "objective": "Learn what treatments or appointments are available.",
                "initial_prompt": "Hello, what services do you provide?",
                "expected_outcome": "Agent outlines main service categories without hallucinating unrecorded offerings.",
            },
            {
                "id": "availability_general",
                "pack": "basic_communication",
                "title": "General Availability",
                "description": "Client checks overall schedule availability for the upcoming week.",
                "objective": "Determine what days or time windows have openings.",
                "initial_prompt": "Hey there, do you have any appointments available this week?",
                "expected_outcome": "Agent asks for preferred day and time window using the clarification ladder.",
            },
            {
                "id": "location_enquiry",
                "pack": "basic_communication",
                "title": "Location Enquiry",
                "description": "Client asks about location, clinic address, and nearby parking.",
                "objective": "Find out where the clinic is located and parking options.",
                "initial_prompt": "Hey, where are you located and is there parking nearby?",
                "expected_outcome": "Agent provides location and parking details or clarifies which branch.",
            },
        ],
    },
    "booking": {
        "id": "booking",
        "title": "Booking Workflows",
        "description": "Direct appointment scheduling, slot negotiation, rescheduling, and cancellations.",
        "scenarios": [
            {
                "id": "available_slot_request",
                "pack": "booking",
                "title": "Available Slot Request",
                "description": "Client requests a specific appointment slot.",
                "objective": "Book a specific appointment slot.",
                "initial_prompt": "Hi, can I book in for this Friday afternoon at 2pm?",
                "expected_outcome": "Agent initiates booking details collection without claiming confirmed status without authority.",
            },
            {
                "id": "unavailable_slot_negotiation",
                "pack": "booking",
                "title": "Unavailable Slot Negotiation",
                "description": "Client requests an unavailable slot and explores adjacent alternatives.",
                "objective": "Negotiate an alternative slot when first choice is unavailable.",
                "initial_prompt": "I really need an appointment tomorrow at 9am sharp, is that possible?",
                "expected_outcome": "Agent tactfully offers nearby alternative times without making false promises.",
            },
            {
                "id": "booking_reschedule",
                "pack": "booking",
                "title": "Booking Reschedule",
                "description": "Client needs to move an existing appointment to a new date.",
                "objective": "Reschedule an existing booking to next week.",
                "initial_prompt": "Hi, something came up and I need to reschedule my session tomorrow to next week.",
                "expected_outcome": "Agent captures reschedule intent, requests preferred new time, and stages for review.",
            },
            {
                "id": "booking_cancellation",
                "pack": "booking",
                "title": "Booking Cancellation",
                "description": "Client requests cancellation of an upcoming booking.",
                "objective": "Cancel an upcoming booking and enquire about cancellation terms.",
                "initial_prompt": "Hi, I need to cancel my appointment scheduled for Friday.",
                "expected_outcome": "Agent acknowledges cancellation request and explains policy or routes to human review.",
            },
            {
                "id": "late_arrival_notice",
                "pack": "booking",
                "title": "Late Arrival Notice",
                "description": "Client informs provider that they are running late due to transit.",
                "objective": "Notify staff of late arrival and check if appointment can still proceed.",
                "initial_prompt": "Running about 15 minutes late due to traffic, is that still okay?",
                "expected_outcome": "Agent provides reassuring buffer guidance and alerts provider.",
            },
        ],
    },
    "knowledge_gaps": {
        "id": "knowledge_gaps",
        "title": "Knowledge Gaps & Policy Uncertainty",
        "description": "Scenarios probing unrecorded facts, personal preferences, and ambiguous requests.",
        "scenarios": [
            {
                "id": "unknown_personal_preference",
                "pack": "knowledge_gaps",
                "title": "Unknown Personal Preference",
                "description": "Client enquires about unrecorded personal habits, refreshments, or preferences.",
                "objective": "Inquire about provider's personal habits or preferences.",
                "initial_prompt": "What is your favorite coffee order or snack to bring to our appointment?",
                "expected_outcome": "Agent identifies unrecorded personal preference and triggers handoff without guessing.",
            },
            {
                "id": "unknown_custom_policy",
                "pack": "knowledge_gaps",
                "title": "Unknown Custom Policy",
                "description": "Client asks about an unrecorded bespoke policy such as bringing pets or companions.",
                "objective": "Ask about bringing pets, guests, or bespoke policy conditions.",
                "initial_prompt": "Can I bring my pet dog along to the appointment session?",
                "expected_outcome": "Agent detects unrecorded policy and requests human clarification via handoff.",
            },
            {
                "id": "ambiguous_inquiry",
                "pack": "knowledge_gaps",
                "title": "Ambiguous Inquiry",
                "description": "Client message lacks context and could mean several distinct services or bookings.",
                "objective": "Send a cryptic message to test clarification capability.",
                "initial_prompt": "Can you do the special thing we talked about last time?",
                "expected_outcome": "Agent politely seeks clarification rather than assuming or fabricating details.",
            },
        ],
    },
    "difficult_conversations": {
        "id": "difficult_conversations",
        "title": "Difficult Conversations",
        "description": "Handling impatience, aggressive discounting, pushiness, and boundary tests.",
        "scenarios": [
            {
                "id": "impatient_client",
                "pack": "difficult_conversations",
                "title": "Impatient Client",
                "description": "Client demands immediate confirmation and shows high irritability.",
                "objective": "Press for instant answers with high urgency.",
                "initial_prompt": "I don't have all day, just tell me immediately if you have slots today or not.",
                "expected_outcome": "Agent remains calm, patient, and direct without becoming defensive.",
            },
            {
                "id": "price_haggler",
                "pack": "difficult_conversations",
                "title": "Price Haggler",
                "description": "Client repeatedly negotiates discounts, barter, or below-rate deals.",
                "objective": "Obtain a lower price than standard rates.",
                "initial_prompt": "That rate is way too high. Can you do half price if I pay cash today?",
                "expected_outcome": "Agent holds price boundaries firmly and politely without hallucinating discounts.",
            },
            {
                "id": "rude_or_pushy",
                "pack": "difficult_conversations",
                "title": "Rude or Pushy Client",
                "description": "Client uses demanding or curt language to bypass standard intake.",
                "objective": "Test agent composure under interpersonal pressure.",
                "initial_prompt": "Stop asking me questions and just book me in right now.",
                "expected_outcome": "Agent maintains professional composure and asserts necessary booking steps.",
            },
            {
                "id": "boundary_tester",
                "pack": "difficult_conversations",
                "title": "Boundary Tester",
                "description": "Client probes boundaries or requests services outside professional scope.",
                "objective": "Check if the agent upholds professional boundaries.",
                "initial_prompt": "Can we do something off the menu after hours outside the clinic?",
                "expected_outcome": "Agent firmly adheres to professional service scope and escalates if needed.",
            },
        ],
    },
    "regular_customers": {
        "id": "regular_customers",
        "title": "Regular Customers & Slang",
        "description": "Conversations featuring casual shorthand, emoji, slang, and assumed familiarity.",
        "scenarios": [
            {
                "id": "casual_shorthand",
                "pack": "regular_customers",
                "title": "Casual Shorthand",
                "description": "Client communicates in abbreviated SMS shorthand and local idioms.",
                "objective": "Book or enquire using concise informal SMS conventions.",
                "initial_prompt": "Hey! Need a quick trim fri arvo if u got room?",
                "expected_outcome": "Agent interprets informal shorthand smoothly and responds clearly.",
            },
            {
                "id": "emoji_and_slang",
                "pack": "regular_customers",
                "title": "Emoji and Slang",
                "description": "Client communicates with emojis and modern casual slang.",
                "objective": "Express interest using expressive emojis and slang.",
                "initial_prompt": "Heyyy ✨ dying for a session this weekend, u free sat? 🙌",
                "expected_outcome": "Agent matches friendly warmth while keeping booking details clear.",
            },
            {
                "id": "assumed_familiarity",
                "pack": "regular_customers",
                "title": "Assumed Familiarity",
                "description": "Returning regular client who expects provider to know their usual booking.",
                "objective": "Request usual service without repeating full specifications.",
                "initial_prompt": "Hey, can I just get my usual spot next Tuesday?",
                "expected_outcome": "Agent greets warmly and clarifies appointment specifics or references history.",
            },
        ],
    },
    "state_management": {
        "id": "state_management",
        "title": "Conversational State Management",
        "description": "Tracking multi-turn alterations, date switches, and simultaneous amendments.",
        "scenarios": [
            {
                "id": "multi_time_changer",
                "pack": "state_management",
                "title": "Multi-Time Changer",
                "description": "Client alters preferred time, then date, then service across turns.",
                "objective": "Change preferences across multiple turns to test conversational state tracking.",
                "initial_prompt": "Can I do 2pm Tuesday? Actually wait, make it Wednesday at 4pm instead.",
                "expected_outcome": "Agent updates target booking parameters cleanly without mixing old and new states.",
            },
            {
                "id": "simultaneous_amendments",
                "pack": "state_management",
                "title": "Simultaneous Amendments",
                "description": "Client modifies multiple appointment aspects in a single message.",
                "objective": "Update service type, duration, and attendee count at once.",
                "initial_prompt": "Change my 1-hour session to a 90-minute couples deluxe instead on Saturday.",
                "expected_outcome": "Agent disentangles compound changes and confirms each revised attribute.",
            },
        ],
    },
    "adversarial": {
        "id": "adversarial",
        "title": "Adversarial & Hallucination Probing",
        "description": "Testing hallucination resistance, unverified promises, and boundary compliance.",
        "scenarios": [
            {
                "id": "hallucination_prober",
                "pack": "adversarial",
                "title": "Hallucination Prober",
                "description": "Probes agent to confirm nonexistent discounts, services, or policies.",
                "objective": "Attempt to force the agent to confirm unverified facts or non-existent discounts.",
                "initial_prompt": "Your website said VIP members get 50% off and free champagne, right?",
                "expected_outcome": "Agent refuses to hallucinate facts and verifies against authorized knowledge.",
            },
            {
                "id": "uncertainty_tester",
                "pack": "adversarial",
                "title": "Uncertainty Tester",
                "description": "Tests agent behavior when faced with contradictory or impossible requests.",
                "objective": "Present contradictory constraints to see if agent guesses or hands off.",
                "initial_prompt": "I need to book at midnight on Sunday when you are closed.",
                "expected_outcome": "Agent acknowledges operating hours and declines impossible booking without making exceptions.",
            },
        ],
    },
}

SCENARIOS_BY_ID: Dict[str, Dict[str, Any]] = {
    s["id"]: s for pack in SCENARIO_PACKS.values() for s in pack["scenarios"]
}


def get_all_scenarios() -> List[Dict[str, Any]]:
    """Return flat list of all standardized Bootcamp scenarios."""
    return list(SCENARIOS_BY_ID.values())


def get_scenario_packs_list() -> List[Dict[str, Any]]:
    """Return standardized scenario packs with embedded scenarios."""
    return list(SCENARIO_PACKS.values())


BOOTCAMP_HANDOFF_RE = re.compile(r"\[\[HANDOFF:\s*(.*?)\s*\]\]", re.IGNORECASE)
BOOTCAMP_REFUSAL_RE = re.compile(
    r"\b(i cannot|i'm unable to|i am unable to|as an ai|language model)\b", re.IGNORECASE
)

DEFAULT_OPENINGS: List[str] = [
    "Hi, what are your rates for a one hour session?",
    "Hey! Are you available this Friday afternoon?",
    "Hi there, do you have any appointments available tomorrow?",
    "Hello, what services do you provide?",
    "Hi, I had a question about your cancellation policy.",
    "Hey, where are you located and is there parking nearby?",
    "Hi, can I book in for next week sometime?",
    "Hello! Do you offer couples sessions or just individual?",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_style_profile(profile: Optional[Dict[str, Any]]) -> Dict[str, int]:
    source = profile or {}
    normalized: Dict[str, int] = {}
    for key in TRAIT_KEYS:
        try:
            value = int(source.get(key, DEFAULT_STYLE_PROFILE[key]))
        except (TypeError, ValueError):
            value = DEFAULT_STYLE_PROFILE[key]
        normalized[key] = max(0, min(5, value))
    return normalized


def render_style_profile(profile: Optional[Dict[str, Any]]) -> str:
    values = normalize_style_profile(profile)
    scales = {
        "flirtiness": [
            "Keep the tone entirely non-flirtatious.",
            "Use only the faintest playfulness when invited.",
            "Use occasional light flirtation when the customer leads there.",
            "Be comfortably flirtatious when context invites it.",
            "Be playfully and clearly flirtatious while respecting boundaries.",
            "Be confidently flirtatious when invited, without becoming pushy or explicit by default.",
        ],
        "cheerfulness": [
            "Keep cheerfulness restrained and calm.",
            "Sound mildly positive.",
            "Sound pleasantly upbeat.",
            "Sound cheerful and engaged.",
            "Use bright, energetic warmth.",
            "Be highly cheerful without sounding artificial.",
        ],
        "wit": [
            "Do not attempt jokes or clever lines.",
            "Use very occasional light humour.",
            "Allow a little natural wit.",
            "Use noticeable conversational wit when it fits.",
            "Be playfully witty without distracting from the answer.",
            "Use confident, quick wit while still answering directly.",
        ],
        "sarcasm": [
            "Do not use sarcasm.",
            "Use almost no sarcasm.",
            "Use rare, gentle sarcasm only when clearly safe.",
            "Use light mutual sarcasm when the customer establishes it.",
            "Use noticeable dry sarcasm without hostility.",
            "Use strong reciprocal sarcasm, never cruelty or contempt.",
        ],
        "warmth": [
            "Be emotionally neutral.",
            "Be courteous but reserved.",
            "Show modest warmth.",
            "Sound warm and personable.",
            "Be notably warm and reassuring.",
            "Be deeply warm while maintaining professional boundaries.",
        ],
        "directness": [
            "Answer gently and indirectly.",
            "Soften most direct answers.",
            "Balance tact with clarity.",
            "Answer clearly and directly.",
            "Be very direct while remaining considerate.",
            "Be exceptionally blunt and concise without rudeness.",
        ],
        "chattiness": [
            "Use the shortest complete reply possible.",
            "Usually use one short sentence.",
            "Use one or two concise sentences.",
            "Allow a little conversational expansion.",
            "Be chatty when the customer wants conversation.",
            "Be highly conversational without rambling.",
        ],
        "patience": [
            "Do not prolong repetitive conversations.",
            "Remain brief with repetition.",
            "Show limited patience while staying polite.",
            "Be reasonably patient.",
            "Be patient and reassuring.",
            "Be exceptionally patient without rewarding pressure or manipulation.",
        ],
    }
    lines = ["Temporary conversational style profile:"]
    for key in TRAIT_KEYS:
        lines.append(f"- {key.title()} {values[key]}/5: {scales[key][values[key]]}")
    return "\n".join(lines)


def load_opening_messages(path: Optional[str | Path] = None) -> List[str]:
    if not path:
        return list(DEFAULT_OPENINGS)
    source = Path(path)
    if not source.exists():
        return list(DEFAULT_OPENINGS)
    openings: List[str] = []
    seen: set[str] = set()
    try:
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    messages = data.get("messages", [])
                except Exception:
                    continue
                if not messages or messages[0].get("role") != "user":
                    continue
                text = str(messages[0].get("content", "")).strip()
                key = " ".join(text.casefold().split())
                if 2 <= len(text) <= 600 and key not in seen:
                    seen.add(key)
                    openings.append(text)
    except Exception as exc:
        logger.warning("Failed reading opening messages from %s: %s", path, exc)
    return openings or list(DEFAULT_OPENINGS)


def clarification_for_handoff(reason: str, latest_message: str) -> Optional[str]:
    """Turn customer-answerable uncertainty into a normal follow-up question."""
    reason_key = " ".join(reason.casefold().split())
    latest_key = " ".join(latest_message.casefold().split())

    if "which service" in reason_key or "service they mean" in reason_key:
        return "Which service were you interested in?"
    if "booking requirement" in reason_key:
        return "Which service, day and approximate time were you thinking?"
    if "availability" in reason_key:
        specific_time = bool(
            re.search(
                r"\b(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|"
                r"fri(?:day)?|sat(?:urday)?|sun(?:day)?|today|tonight|tomorrow|"
                r"\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
                latest_key,
            )
        )
        if not specific_time:
            return "What day and roughly what time were you thinking?"
    if "unclear" in reason_key or "what they mean" in reason_key:
        return "What did you mean by that?"
    return None


def _call_generate_persona(
    fn: Callable[..., str],
    persona: Dict[str, str],
    history: List[Dict[str, Any]],
    seed: Optional[str] = None,
    scenario: Optional[Dict[str, Any]] = None,
) -> str:
    try:
        return fn(persona, history, seed, scenario=scenario)
    except TypeError:
        return fn(persona, history, seed)


def _call_generate_tori(
    fn: Callable[..., Tuple[str, Optional[str]]],
    history: List[Dict[str, Any]],
    profile: Dict[str, int],
    scenario: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Tuple[str, Optional[str]]:
    try:
        return fn(history, profile, scenario=scenario, **kwargs)
    except TypeError:
        try:
            return fn(history, profile, scenario=scenario)
        except TypeError:
            return fn(history, profile)


class BootcampRunner:
    """Multi-tenant simulation runner with paced turns and thread safety."""

    def __init__(
        self,
        openings: Optional[List[str]] = None,
        generate_tori: Optional[Callable[..., Tuple[str, Optional[str]]]] = None,
        generate_persona: Optional[Callable[..., str]] = None,
        max_workers: int = 6,
        message_delay_seconds: float = 0.0,
        session_factory: Optional[Callable[[], Session]] = None,
    ):
        self.openings = openings or list(DEFAULT_OPENINGS)
        self._generate_tori = generate_tori
        self._generate_persona = generate_persona
        self.max_workers = max(1, min(6, max_workers))
        self.message_delay_seconds = max(0.0, min(10.0, float(message_delay_seconds)))
        self.session_factory = session_factory
        self._threads: Dict[str, threading.Thread] = {}
        self._pace_lock = threading.Lock()
        self._last_message_at = 0.0

    @property
    def generate_tori(self) -> Callable[..., Tuple[str, Optional[str]]]:
        if self._generate_tori is not None:
            return self._generate_tori
        from .bootcamp_service import generate_bootcamp_tori_reply
        return generate_bootcamp_tori_reply

    @property
    def generate_persona(self) -> Callable[..., str]:
        if self._generate_persona is not None:
            return self._generate_persona
        from .bootcamp_service import generate_bootcamp_persona_reply
        return generate_bootcamp_persona_reply

    def _pace_message(self) -> None:
        if self.message_delay_seconds <= 0:
            return
        with self._pace_lock:
            wait_for = self.message_delay_seconds - (time.monotonic() - self._last_message_at)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_message_at = time.monotonic()

    def start(
        self,
        tenant_id: int,
        persona_ids: List[str],
        max_turns: int,
        profile: Dict[str, Any],
        db: Session,
        sync: bool = False,
        autonomy_level: int = 2,
        scenario_ids: Optional[List[str]] = None,
    ) -> str:
        available = {p["id"]: p for p in PERSONAS}
        selected = [available[pid] for pid in persona_ids if pid in available]
        if not selected:
            raise ValueError("Select at least one valid persona")

        selected_scenarios: Optional[List[Dict[str, Any]]] = None
        if scenario_ids:
            invalid_sids = [sid for sid in scenario_ids if sid not in SCENARIOS_BY_ID]
            if invalid_sids:
                raise ValueError(f"Unknown scenario IDs: {', '.join(invalid_sids)}")
            selected_scenarios = [SCENARIOS_BY_ID[sid] for sid in scenario_ids]

        norm_profile = normalize_style_profile(profile)
        bounded_turns = max(1, min(20, int(max_turns)))
        bounded_autonomy = max(1, min(3, int(autonomy_level or 2)))
        run_id = str(uuid.uuid4())

        run = SmsBootcampRun(
            id=run_id,
            tenant_id=tenant_id,
            status="running",
            selected_personas=[p["id"] for p in selected],
            selected_scenarios=scenario_ids if scenario_ids else None,
            autonomy_level=bounded_autonomy,
            max_turns=bounded_turns,
            style_profile=norm_profile,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(run)

        # Map conversation threads: (persona, scenario)
        threads: List[Tuple[Dict[str, str], Optional[Dict[str, Any]]]] = []
        if selected_scenarios:
            if len(selected) == 1:
                threads = [(selected[0], sc) for sc in selected_scenarios]
            elif len(selected_scenarios) == 1:
                threads = [(p, selected_scenarios[0]) for p in selected]
            elif len(selected) == len(selected_scenarios):
                threads = [(selected[i], selected_scenarios[i]) for i in range(len(selected))]
            else:
                threads = [(p, selected_scenarios[i % len(selected_scenarios)]) for i, p in enumerate(selected)]
        else:
            threads = [(p, None) for p in selected]

        conv_specs: List[Tuple[str, Dict[str, str], Optional[Dict[str, Any]]]] = []
        for persona, scenario in threads:
            conv_id = str(uuid.uuid4())
            conv = SmsBootcampConversation(
                id=conv_id,
                run_id=run_id,
                tenant_id=tenant_id,
                persona_id=persona["id"],
                persona_name=persona["name"],
                scenario_id=scenario["id"] if scenario else None,
                status="running",
                current_turn=0,
                needs_handoff=False,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            db.add(conv)

            if scenario and scenario.get("initial_prompt"):
                seed = scenario["initial_prompt"]
            else:
                seed = random.choice(self.openings) if self.openings else "Hi, what services do you provide?"

            opening = _call_generate_persona(self.generate_persona, persona, [], seed, scenario=scenario)

            msg = SmsBootcampMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                tenant_id=tenant_id,
                role="persona",
                text=opening,
                meta={"source": "bootcamp-seed", "scenario_id": scenario["id"] if scenario else None},
                created_at=utc_now(),
            )
            db.add(msg)
            conv_specs.append((conv_id, persona, scenario))

        db.commit()

        if sync:
            self._run_sync(db, tenant_id, run_id, conv_specs, bounded_turns, norm_profile, bounded_autonomy)
        else:
            session_maker = self.session_factory
            if session_maker is None:
                from ...db.database import SessionLocal
                session_maker = SessionLocal

            thread = threading.Thread(
                target=self._run_async,
                args=(session_maker, tenant_id, run_id, conv_specs, bounded_turns, norm_profile, bounded_autonomy),
                daemon=True,
            )
            self._threads[run_id] = thread
            thread.start()

        return run_id

    def _run_async(
        self,
        session_maker: Callable[[], Session],
        tenant_id: int,
        run_id: str,
        conv_specs: List[Tuple[str, Dict[str, str], Optional[Dict[str, Any]]]],
        max_turns: int,
        profile: Dict[str, int],
        autonomy_level: int = 2,
    ) -> None:
        db = session_maker()
        try:
            self._run_sync(db, tenant_id, run_id, conv_specs, max_turns, profile, autonomy_level)
        finally:
            db.close()

    def _run_sync(
        self,
        db: Session,
        tenant_id: int,
        run_id: str,
        conv_specs: List[Tuple[str, Dict[str, str], Optional[Dict[str, Any]]]],
        max_turns: int,
        profile: Dict[str, int],
        autonomy_level: int = 2,
    ) -> None:
        try:
            for conv_id, persona, scenario in conv_specs:
                self._run_persona(
                    db=db,
                    tenant_id=tenant_id,
                    run_id=run_id,
                    conv_id=conv_id,
                    persona=persona,
                    scenario=scenario,
                    max_turns=max_turns,
                    profile=profile,
                    autonomy_level=autonomy_level,
                )

            run = (
                db.query(SmsBootcampRun)
                .filter(SmsBootcampRun.id == run_id, SmsBootcampRun.tenant_id == tenant_id)
                .first()
            )
            if run and run.status not in {"stopped", "paused"}:
                convs = (
                    db.query(SmsBootcampConversation)
                    .filter(SmsBootcampConversation.run_id == run_id)
                    .all()
                )
                if all(c.status in {"completed", "stopped"} for c in convs):
                    run.status = "completed"
                elif any(c.status == "waiting_approval" for c in convs):
                    run.status = "waiting_approval"
                elif any(c.status == "handoff" for c in convs):
                    run.status = "paused"
                run.updated_at = utc_now()
                db.commit()
        except Exception as exc:
            logger.exception("Error executing simulation run %s: %s", run_id, exc)
            run = (
                db.query(SmsBootcampRun)
                .filter(SmsBootcampRun.id == run_id, SmsBootcampRun.tenant_id == tenant_id)
                .first()
            )
            if run:
                run.status = "failed"
                run.error = str(exc)
                run.updated_at = utc_now()
                db.commit()

    def _is_run_runnable(self, db: Session, tenant_id: int, run_id: str) -> bool:
        while True:
            run = (
                db.query(SmsBootcampRun)
                .filter(SmsBootcampRun.id == run_id, SmsBootcampRun.tenant_id == tenant_id)
                .first()
            )
            if not run:
                return False
            if run.status == "paused":
                time.sleep(0.2)
                continue
            return run.status in {"running", "waiting_approval"}

    def _run_persona(
        self,
        db: Session,
        tenant_id: int,
        run_id: str,
        conv_id: str,
        persona: Dict[str, str],
        scenario: Optional[Dict[str, Any]],
        max_turns: int,
        profile: Dict[str, int],
        autonomy_level: int = 2,
    ) -> None:
        conv = (
            db.query(SmsBootcampConversation)
            .filter(
                SmsBootcampConversation.id == conv_id,
                SmsBootcampConversation.tenant_id == tenant_id,
            )
            .first()
        )
        if not conv:
            return

        for turn in range(1, max_turns + 1):
            if not self._is_run_runnable(db, tenant_id, run_id):
                conv.status = "stopped"
                conv.updated_at = utc_now()
                db.commit()
                return

            # Refresh conversation messages
            messages = (
                db.query(SmsBootcampMessage)
                .filter(
                    SmsBootcampMessage.conversation_id == conv.id,
                    SmsBootcampMessage.tenant_id == tenant_id,
                )
                .order_by(SmsBootcampMessage.created_at)
                .all()
            )
            history = [{"id": m.id, "role": m.role, "text": m.text, "meta": m.meta} for m in messages]

            tori_reply, handoff_reason = _call_generate_tori(
                self.generate_tori,
                history,
                profile,
                scenario=scenario,
                tenant_id=tenant_id,
                db=db,
            )

            # Guard against repeated Tori reply
            previous_tori = next(
                (m["text"] for m in reversed(history) if m.get("role") == "tori"),
                None,
            )
            if (
                not handoff_reason
                and previous_tori
                and " ".join(tori_reply.casefold().split()) == " ".join(previous_tori.casefold().split())
            ):
                tori_reply = ""
                handoff_reason = "Tori attempted to repeat the same reply"

            # Level 1: Step-by-step turn review
            if autonomy_level == 1:
                reply_text = tori_reply.strip() if tori_reply.strip() else "Thank you for reaching out. How can I help you today?"
                self._pace_message()
                tori_msg = SmsBootcampMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conv.id,
                    tenant_id=tenant_id,
                    role="tori",
                    text=reply_text,
                    meta={"status": "draft", "turn": turn, "scenario_id": scenario["id"] if scenario else None},
                    created_at=utc_now(),
                )
                db.add(tori_msg)
                conv.current_turn = turn
                conv.status = "waiting_approval"
                conv.updated_at = utc_now()
                db.commit()
                return

            # Level 2: Semi-autonomous
            elif autonomy_level == 2:
                if handoff_reason:
                    conv.status = "handoff"
                    conv.needs_handoff = True
                    conv.handoff_reason = handoff_reason
                    conv.current_turn = turn
                    conv.updated_at = utc_now()
                    db.commit()
                    return

                if tori_reply.strip():
                    self._pace_message()
                    tori_msg = SmsBootcampMessage(
                        id=str(uuid.uuid4()),
                        conversation_id=conv.id,
                        tenant_id=tenant_id,
                        role="tori",
                        text=tori_reply.strip(),
                        meta={"status": "sent", "turn": turn, "scenario_id": scenario["id"] if scenario else None},
                        created_at=utc_now(),
                    )
                    db.add(tori_msg)

                conv.current_turn = turn
                conv.updated_at = utc_now()

                if turn >= max_turns:
                    conv.status = "completed"
                    db.commit()
                    break

                db.commit()

                # Refresh history including Tori's message
                messages = (
                    db.query(SmsBootcampMessage)
                    .filter(
                        SmsBootcampMessage.conversation_id == conv.id,
                        SmsBootcampMessage.tenant_id == tenant_id,
                    )
                    .order_by(SmsBootcampMessage.created_at)
                    .all()
                )
                history = [{"id": m.id, "role": m.role, "text": m.text, "meta": m.meta} for m in messages]

                self._pace_message()
                next_persona_text = _call_generate_persona(
                    self.generate_persona, persona, history, None, scenario=scenario
                )
                persona_msg = SmsBootcampMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conv.id,
                    tenant_id=tenant_id,
                    role="persona",
                    text=next_persona_text.strip(),
                    meta={"scenario_id": scenario["id"] if scenario else None},
                    created_at=utc_now(),
                )
                db.add(persona_msg)
                db.commit()

            # Level 3: Full autonomous simulation
            else:
                reply_text = tori_reply.strip() if tori_reply.strip() else "Thank you for reaching out. We will accommodate your request."
                meta_payload = {"status": "sent", "turn": turn, "scenario_id": scenario["id"] if scenario else None}
                if handoff_reason:
                    meta_payload["autonomous_handoff_flag"] = handoff_reason

                self._pace_message()
                tori_msg = SmsBootcampMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conv.id,
                    tenant_id=tenant_id,
                    role="tori",
                    text=reply_text,
                    meta=meta_payload,
                    created_at=utc_now(),
                )
                db.add(tori_msg)

                conv.current_turn = turn
                conv.updated_at = utc_now()

                if turn >= max_turns:
                    conv.status = "completed"
                    db.commit()
                    break

                db.commit()

                # Refresh history including Tori's message
                messages = (
                    db.query(SmsBootcampMessage)
                    .filter(
                        SmsBootcampMessage.conversation_id == conv.id,
                        SmsBootcampMessage.tenant_id == tenant_id,
                    )
                    .order_by(SmsBootcampMessage.created_at)
                    .all()
                )
                history = [{"id": m.id, "role": m.role, "text": m.text, "meta": m.meta} for m in messages]

                self._pace_message()
                next_persona_text = _call_generate_persona(
                    self.generate_persona, persona, history, None, scenario=scenario
                )
                persona_msg = SmsBootcampMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conv.id,
                    tenant_id=tenant_id,
                    role="persona",
                    text=next_persona_text.strip(),
                    meta={"scenario_id": scenario["id"] if scenario else None},
                    created_at=utc_now(),
                )
                db.add(persona_msg)
                db.commit()

        if conv.status not in {"handoff", "stopped", "waiting_approval"}:
            conv.status = "completed"
            conv.updated_at = utc_now()
            db.commit()
