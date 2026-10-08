"""Inline conversational interview flow for voice-first onboarding.

Manages conversational question progression across all 8 onboarding domains in
Australian English, resolves spoken/clicked/typed inputs idempotently, detects
interruptions and questions with polite Australian resumptions, and generates
smooth topic transitions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.models.onboarding import OnboardingPlan, OnboardingStep
from app.services.business_assistant.onboarding.normalizer import IntentNormalizer
from app.services.business_assistant.onboarding.plan_service import (
    DOMAIN_CONFIGS,
    OnboardingPlanService,
)


class InlineChoice(BaseModel):
    """Suggested quick-select choice for inline tap/click UI."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique choice identifier")
    label: str = Field(..., description="Human-friendly label in Australian English")
    value: Any = Field(..., description="Structured value passed upon selection")


class InterviewQuestion(BaseModel):
    """Structured question presented during the conversational interview."""

    model_config = ConfigDict(extra="ignore")

    question_id: str = Field(..., description="Stable question identifier")
    domain: int = Field(..., ge=1, le=8, description="Target domain (1 to 8)")
    step_id: str = Field(..., description="Associated onboarding step ID")
    fact_key: str = Field(..., description="Key of the required fact being gathered")
    prompt: str = Field(..., description="Spoken prompt in Australian English")
    inline_choices: List[InlineChoice] = Field(
        default_factory=list,
        description="Optional quick-tap choices rendered near the active form",
    )
    helper_text: Optional[str] = Field(
        default=None,
        description="Concise explanatory helper text for UI",
    )


# Domain-specific question banks in Australian English
QUESTION_BANK: Dict[str, Dict[str, Any]] = {
    "business_name": {
        "question_id": "q_domain1_business_name",
        "domain": 1,
        "step_id": "step_1_identity",
        "fact_key": "business_name",
        "prompt": "G'day! What is the official name of your business?",
        "inline_choices": [],
        "helper_text": "Enter your registered or trading business name.",
    },
    "business_description": {
        "question_id": "q_domain1_description",
        "domain": 1,
        "step_id": "step_1_identity",
        "fact_key": "business_description",
        "prompt": "Could you give me a brief description of what your business does?",
        "inline_choices": [],
        "helper_text": "A short summary of your core offering and speciality.",
    },
    "business_phone": {
        "question_id": "q_domain1_phone",
        "domain": 1,
        "step_id": "step_1_identity",
        "fact_key": "business_phone",
        "prompt": "What's the best Australian phone number for customer enquiries?",
        "inline_choices": [],
        "helper_text": "E.g. (02) 9123 4567 or 0412 345 678.",
    },
    "business_email": {
        "question_id": "q_domain1_email",
        "domain": 1,
        "step_id": "step_1_identity",
        "fact_key": "business_email",
        "prompt": "And what email address should clients use to get in touch?",
        "inline_choices": [],
        "helper_text": "Public email address displayed on your profile and booking receipts.",
    },
    "address": {
        "question_id": "q_domain2_address",
        "domain": 2,
        "step_id": "step_2_locations",
        "fact_key": "address",
        "prompt": "Where are you based? Could you tell me your street address or suburb?",
        "inline_choices": [],
        "helper_text": "Physical studio, salon address, or base operating suburb.",
    },
    "timezone": {
        "question_id": "q_domain2_timezone",
        "domain": 2,
        "step_id": "step_2_locations",
        "fact_key": "timezone",
        "prompt": "Which time zone does your business operate in?",
        "inline_choices": [
            InlineChoice(id="syd_melb", label="Sydney / Melbourne (AEST/AEDT)", value="Australia/Sydney"),
            InlineChoice(id="brisbane", label="Brisbane (AEST)", value="Australia/Brisbane"),
            InlineChoice(id="adelaide", label="Adelaide (ACST/ACDT)", value="Australia/Adelaide"),
            InlineChoice(id="perth", label="Perth (AWST)", value="Australia/Perth"),
        ],
        "helper_text": "Ensures booking calendar time slots match your local clock.",
    },
    "service_name": {
        "question_id": "q_domain3_service_name",
        "domain": 3,
        "step_id": "step_3_services",
        "fact_key": "service_name",
        "prompt": "Let's set up your primary service. What is the name of your main service offering?",
        "inline_choices": [],
        "helper_text": "E.g. Full Grooming & Wash, 60-Minute Consultation, Standard Appointment.",
    },
    "duration_minutes": {
        "question_id": "q_domain3_duration",
        "domain": 3,
        "step_id": "step_3_services",
        "fact_key": "duration_minutes",
        "prompt": "How long does a standard session usually take?",
        "inline_choices": [
            InlineChoice(id="30m", label="30 minutes", value="30"),
            InlineChoice(id="45m", label="45 minutes", value="45"),
            InlineChoice(id="60m", label="1 hour", value="60"),
            InlineChoice(id="90m", label="90 minutes", value="90"),
        ],
        "helper_text": "Duration in minutes used for calendar block calculation.",
    },
    "price_amount": {
        "question_id": "q_domain3_price",
        "domain": 3,
        "step_id": "step_3_services",
        "fact_key": "price_amount",
        "prompt": "What is the fee or price in Australian Dollars (AUD) for this service?",
        "inline_choices": [],
        "helper_text": "Price in AUD, e.g. $85 or $120.50.",
    },
    "provider_name": {
        "question_id": "q_domain4_provider",
        "domain": 4,
        "step_id": "step_4_providers",
        "fact_key": "provider_name",
        "prompt": "Are you working as a solo operator, or do you have team members providing services?",
        "inline_choices": [
            InlineChoice(id="solo", label="Solo operator (just me)", value="Solo Operator"),
            InlineChoice(id="team", label="Team with staff", value="Team Operator"),
        ],
        "helper_text": "Select your operational staffing structure.",
    },
    "operating_hours": {
        "question_id": "q_domain5_hours",
        "domain": 5,
        "step_id": "step_5_hours",
        "fact_key": "operating_hours",
        "prompt": "What days and hours are you typically open for appointments?",
        "inline_choices": [
            InlineChoice(id="mon_fri_9_5", label="Mon – Fri: 9:00 AM – 5:00 PM", value="Mon-Fri 9:00 AM - 5:00 PM"),
            InlineChoice(id="mon_sat_8_6", label="Mon – Sat: 8:00 AM – 6:00 PM", value="Mon-Sat 8:00 AM - 6:00 PM"),
            InlineChoice(id="seven_days", label="7 Days a week", value="7 Days 9:00 AM - 5:00 PM"),
        ],
        "helper_text": "Defines bookable schedule slots on your calendar.",
    },
    "cancellation_policy": {
        "question_id": "q_domain6_cancellation",
        "domain": 6,
        "step_id": "step_6_settings",
        "fact_key": "cancellation_policy",
        "prompt": "What notice period do you require if a client needs to cancel or reschedule?",
        "inline_choices": [
            InlineChoice(id="24h", label="24 hours notice", value="24 hours notice required"),
            InlineChoice(id="48h", label="48 hours notice", value="48 hours notice required"),
            InlineChoice(id="flexible", label="Flexible / same-day", value="Flexible notice"),
        ],
        "helper_text": "Communicated on customer booking confirmation receipts.",
    },
    "website_headline": {
        "question_id": "q_domain7_headline",
        "domain": 7,
        "step_id": "step_7_website",
        "fact_key": "website_headline",
        "prompt": "Would you like me to generate a starter website draft showcasing your business and services?",
        "inline_choices": [
            InlineChoice(id="yes_draft", label="Yes, create website draft", value="generate_draft"),
            InlineChoice(id="skip_website", label="Skip website for now", value="skip"),
        ],
        "helper_text": "Creates a private starter draft you can preview before publishing.",
    },
}

# Domain transition greetings in Australian English
DOMAIN_TRANSITIONS: Dict[int, str] = {
    1: "No worries! Let's get started with your business identity.",
    2: "Beauty! That's your business details sorted. Let's look at your location and time zone.",
    3: "Right on. Now let's set up the services you'll be offering to clients.",
    4: "Spot on! Next up, let's configure your team and staffing setup.",
    5: "Terrific! Now we'll set up your regular operating hours and weekly availability.",
    6: "Almost there! Let's lock in your booking rules and cancellation policy.",
    7: "Great job! Let's put together your online presence and website draft.",
    8: "Fantastic! All eight domains are wrapped up. Let's do a quick final review.",
}

# Common user interruptions or side questions with helpful Australian English responses
INTERRUPTION_PATTERNS: List[Dict[str, Any]] = [
    {
        "pattern": r"(abn|tax|business number|gst)",
        "answer": "No stress! You don't need to enter your ABN right this second; you can easily add or update your tax details anytime in Settings.",
    },
    {
        "pattern": r"(payment|stripe|credit card|eftpos|charge clients)",
        "answer": "Payments can be connected later via the Stripe integration in Settings. Right now we're just locking in your core service details.",
    },
    {
        "pattern": r"(add more services|multiple services|change price later)",
        "answer": "You can add as many extra services and tweak your prices whenever you like from the Services catalogue.",
    },
    {
        "pattern": r"(cancel|stop|pause|hold on|wait a second)",
        "answer": "Too easy! We can pause right here. You can take over manually at any point or pick back up whenever you're ready.",
    },
    {
        "pattern": r"(cost|pricing for this software|subscription|plan price)",
        "answer": "You can review subscription tiers and billing under Account Settings. Your current onboarding workspace is ready to set up.",
    },
]


class InlineInterviewFlow:
    """Manages natural conversational interview progression across the 8 domains."""

    def __init__(self, normalizer: Optional[IntentNormalizer] = None) -> None:
        self.normalizer = normalizer or IntentNormalizer()
        self._last_processed_answer: Dict[str, Any] = {}

    def get_next_question(self, plan: OnboardingPlan) -> Optional[InterviewQuestion]:
        """Determine and return the next unanswered question across the 8 domains."""
        # Find active step or first incomplete step
        steps = sorted(plan.steps, key=lambda s: s.domain)
        for step in steps:
            if step.status in ("saved", "skipped"):
                continue

            # Check required facts for this step
            req_facts = step.required_facts or []
            answered = step.answered_facts or {}
            staged = step.staged_fields or {}

            for fact_key in req_facts:
                if fact_key not in answered and fact_key not in staged:
                    cfg = QUESTION_BANK.get(fact_key)
                    if cfg:
                        return InterviewQuestion(**cfg)
                    # Generic fallback if not explicitly in question bank
                    return InterviewQuestion(
                        question_id=f"q_{step.step_id}_{fact_key}",
                        domain=step.domain,
                        step_id=step.step_id,
                        fact_key=fact_key,
                        prompt=f"Could you please share your {fact_key.replace('_', ' ')}?",
                        inline_choices=[],
                        helper_text=f"Please provide your {fact_key.replace('_', ' ')}.",
                    )

        return None

    def detect_interruption(self, utterance: str) -> Optional[Dict[str, str]]:
        """Check if user utterance is an interruption or side question.

        Returns answer and resumption hint if matched.
        """
        if not utterance or not utterance.strip():
            return None

        clean_text = utterance.lower()
        for item in INTERRUPTION_PATTERNS:
            if re.search(item["pattern"], clean_text):
                return {
                    "is_interruption": True,
                    "matched_pattern": item["pattern"],
                    "answer": item["answer"],
                }

        # Check for interrogative query patterns (e.g. "Do I have to...", "Can I...")
        if clean_text.startswith(("can i", "do i have to", "what if", "wait,", "hang on", "is it possible")):
            return {
                "is_interruption": True,
                "matched_pattern": "general_query",
                "answer": "Good question! Everything we set up here is fully editable afterwards in your admin dashboard.",
            }

        return None

    def process_response(
        self,
        db: Session,
        plan: OnboardingPlan,
        input_type: str,  # 'spoken', 'clicked', 'typed'
        value: Any,
        fact_key: Optional[str] = None,
        utterance: Optional[str] = None,
        actor: str = "agent",
    ) -> Dict[str, Any]:
        """Process user response idempotently across spoken, clicked, or typed modalities.

        Suppresses duplicate answers across modalities in the same turn.
        """
        # Resolve target question & fact key
        target_question = self.get_next_question(plan)
        target_fact = fact_key or (target_question.fact_key if target_question else None)
        target_step_id = target_question.step_id if target_question else (plan.current_step_id or "step_1_identity")

        if not target_fact:
            return {
                "status": "ok",
                "message": "All required facts for this step have already been gathered.",
                "advanced": False,
            }

        # Deduplication check: if identical answer was just processed for this fact key within this plan
        dedup_key = f"{plan.id}_{target_step_id}_{target_fact}_{str(value).strip().lower()}"
        if self._last_processed_answer.get("key") == dedup_key:
            return {
                "status": "ok",
                "duplicate_suppressed": True,
                "fact_key": target_fact,
                "message": f"Answer for '{target_fact}' already recorded.",
                "advanced": False,
            }

        # Normalize value
        norm_res = self.normalizer.normalize_field(field_key=target_fact, utterance=str(value))
        if norm_res.normalized_value is not None:
            normalized_str = str(norm_res.normalized_value)
        elif target_fact in ("timezone", "business_name", "business_email", "business_phone", "service_name", "price_amount", "duration_minutes"):
            normalized_str = str(value).strip()
        else:
            normalized_str = self.normalizer.enforce_australian_spelling(str(value))

        # Stage field in plan
        fields_to_stage = {target_fact: normalized_str}
        facts_to_record = {target_fact: normalized_str}

        step = OnboardingPlanService.stage_step_fields(
            db=db,
            plan=plan,
            step_id=target_step_id,
            fields=fields_to_stage,
            facts=facts_to_record,
            actor=actor,
        )

        # Mark deduplication key
        self._last_processed_answer = {
            "key": dedup_key,
            "fact": target_fact,
            "val": normalized_str,
        }

        # Check if step has fulfilled all required facts
        req_facts = step.required_facts or []
        answered = step.answered_facts or {}
        staged = step.staged_fields or {}
        all_facts_gathered = all(k in answered or k in staged for k in req_facts)

        next_q = self.get_next_question(plan)
        transition_text = None
        if all_facts_gathered and next_q and next_q.domain != step.domain:
            transition_text = DOMAIN_TRANSITIONS.get(next_q.domain)

        return {
            "status": "ok",
            "duplicate_suppressed": False,
            "fact_key": target_fact,
            "normalized_value": normalized_str,
            "input_type": input_type,
            "step_id": target_step_id,
            "all_facts_gathered": all_facts_gathered,
            "transition": transition_text,
            "next_question": next_q.model_dump() if next_q else None,
        }

    def resolve_inline_choice(
        self,
        db: Session,
        plan: OnboardingPlan,
        choice_id: str,
        value: Any,
        fact_key: Optional[str] = None,
        actor: str = "agent",
    ) -> Dict[str, Any]:
        """Resolve a clicked/tapped inline choice component into the setup plan idempotently."""
        return self.process_response(
            db=db,
            plan=plan,
            input_type="clicked",
            value=value,
            fact_key=fact_key,
            actor=actor,
        )

    def handle_user_message(
        self,
        db: Session,
        plan: OnboardingPlan,
        utterance: str,
        input_type: str = "spoken",
    ) -> Dict[str, Any]:
        """High-level conversational handler supporting interruption detection and Australian resumption."""
        # 1. Check for interruption or clarification question
        interruption = self.detect_interruption(utterance)
        if interruption:
            active_q = self.get_next_question(plan)
            resumption = ""
            if active_q:
                resumption = f" Right, getting back to where we were: {active_q.prompt}"
            return {
                "is_interruption": True,
                "spoken_response": f"{interruption['answer']}{resumption}",
                "answer": interruption["answer"],
                "active_question": active_q.model_dump() if active_q else None,
            }

        # 2. Process as direct answer
        result = self.process_response(
            db=db,
            plan=plan,
            input_type=input_type,
            value=utterance,
            utterance=utterance,
        )

        next_q = result.get("next_question")
        transition = result.get("transition")
        spoken_response = "No worries, recorded!"
        if transition and next_q:
            spoken_response = f"{transition} {next_q['prompt']}"
        elif next_q:
            spoken_response = f"Got it. {next_q['prompt']}"
        elif result.get("all_facts_gathered"):
            spoken_response = "Beauty! That covers all the essential details for this step."

        result["spoken_response"] = spoken_response
        return result
