"""Autonomous Knowledge Curator Service.

Implements the Master Spec autonomous curation lifecycle (Specs 21-27, 42-44, 47, 52):
- Autonomous processing of LearningEvents across factual knowledge, corrections, draft edits, and approvals.
- Explicit knowledge curation and supersession tracking with provenance intact (Spec 14, 25).
- System safety guard enforcement fail-closed against unverified dynamic facts (Spec 22).
- Distinguishes factual corrections from behavioural instructions (Specs 17, 27).
- Conservative generalization on draft diffs (Spec 26).
- Positive reinforcement telemetry without canonical pollution (Spec 19).
- Multi-tenant and provider boundary isolation.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models.curated_memory import CuratedMemory, KnowledgeProposal
from ...models.learning_event import LearningEvent, compute_text_diff
from ..curation.knowledge_policy import classify_knowledge_safety
from .pii_scrubber import scrub_pii
from app.services.knowledge.curator import unified_curator

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


BEHAVIOURAL_KEYWORDS = {
    "tone",
    "style",
    "casual",
    "concise",
    "formal",
    "friendly",
    "phrasing",
    "phrase",
    "customer-service",
    "customer service",
    "corporate",
    "brief",
    "polite",
    "wordy",
    "greeting",
    "signoff",
    "sign-off",
    "robotic",
    "natural",
    "humour",
    "humor",
    "slang",
    "abbreviation",
    "manner",
    "short",
    "avoid saying",
    "avoid phrases",
    "don't say",
    "do not say",
    "use language",
    "speak like",
    "sound like",
}

AVAILABILITY_PATTERNS = re.compile(
    r"\b(?:available\s+at|open\s+at|free\s+at|slot\s+available|available\s+tomorrow|"
    r"available\s+today|booked\s+you\s+in|confirmed\s+your\s+appointment|open\s+slot|"
    r"next\s+appointment|book\s+you\s+for|can\s+fit\s+you\s+in)\b",
    re.IGNORECASE,
)


class AutonomousCuratorService:
    """Autonomous Knowledge Curator and Continuous Governance Engine."""

    @classmethod
    def check_safety_violation(
        cls, event: LearningEvent, is_behavioural: bool = False
    ) -> Tuple[bool, str]:
        """Verify correction does not violate immutable system safety boundaries (Spec 22).

        Dynamic facts (availability, prices, dates/times, booking confirmations, links)
        must never become durable memories.
        """
        metadata = event.metadata_payload or {}
        if metadata.get("contains_dynamic_facts") is True:
            return True, "safety_violation"

        query_text = (event.customer_message or "").strip()
        human_text = (event.human_content or "").strip()
        reason_text = str(metadata.get("reason", "")).strip()

        # If it's a behavioural correction, ensure the behavioural instruction itself
        # does not violate safety boundaries (e.g. instructing to fake availability).
        if is_behavioural:
            if AVAILABILITY_PATTERNS.search(reason_text):
                return True, "safety_violation"
            return False, ""

        combined_text = f"{query_text}\n{human_text}\n{reason_text}"

        # 1. Regex check for unverified availability and slot booking claims
        if AVAILABILITY_PATTERNS.search(combined_text):
            return True, "safety_violation"

        # 2. Rejection of dynamic facts via existing fail-closed classifier
        safety = classify_knowledge_safety(
            query_text or "general question",
            human_text,
            category=metadata.get("category"),
        )
        if not safety.durable:
            return True, "safety_violation"

        return False, ""

    @classmethod
    def is_behavioural_correction(
        cls, reason: str, human_content: str, metadata: Dict[str, Any]
    ) -> bool:
        """Determine whether a correction addresses tone/manner vs factual knowledge (Specs 17, 27)."""
        category = str(metadata.get("category", "")).lower()
        if category in ("tone", "style", "behavior", "behaviour", "guidance"):
            return True

        text_to_check = f"{reason} {human_content}".lower()
        for kw in BEHAVIOURAL_KEYWORDS:
            if kw in text_to_check:
                return True
        return False

    @classmethod
    def derive_behavioural_principle(cls, reason: str, human_wording: str) -> str:
        """Derive a canonical, reusable behavioural principle from correction feedback."""
        cleaned_reason = (reason or "").strip()
        if cleaned_reason:
            return cleaned_reason
        cleaned_wording = (human_wording or "").strip()
        return f"Respond concisely and casually, modeled after: '{cleaned_wording}'."

    @classmethod
    def _find_matching_memory(
        cls,
        db: Session,
        tenant_id: int,
        provider_id: Optional[int],
        query_text: str,
        category: Optional[str] = None,
    ) -> Optional[CuratedMemory]:
        """Find active CuratedMemory matching the query/topic within scope."""
        norm_q = (query_text or "").strip().lower()
        if not norm_q:
            return None

        q = (
            db.query(CuratedMemory)
            .filter(
                CuratedMemory.tenant_id == tenant_id,
                CuratedMemory.status == "active",
            )
        )
        if provider_id is not None:
            q = q.filter(CuratedMemory.provider_id == provider_id)
        else:
            q = q.filter(CuratedMemory.provider_id.is_(None))

        candidates = q.all()
        for cand in candidates:
            cand_norm = (cand.user_query or "").strip().lower()
            if cand_norm == norm_q:
                return cand
            # Check high lexical similarity for identical enquiries
            if difflib.SequenceMatcher(None, cand_norm, norm_q).ratio() >= 0.85:
                return cand
            if cand_norm in norm_q or norm_q in cand_norm:
                return cand
        return None

    @classmethod
    def process_event(cls, db: Session, event: LearningEvent) -> Any:
        """Process an individual LearningEvent autonomously according to its event_type.

        Delegates directly to UnifiedCurator.
        """
        return unified_curator.process_learning_event(db, event)


    @classmethod
    def process_pending_events(
        cls, db: Session, tenant_id: int, limit: int = 50
    ) -> Dict[str, Any]:
        """Fetch pending LearningEvent records for the tenant, execute process_event, and commit."""
        return unified_curator.process_pending_learning_events(db, tenant_id, limit)

    @classmethod
    def get_curation_status(
        cls, db: Session, tenant_id: int, provider_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Return curation stats, active vs superseded counts, and breakdown by scope."""
        return unified_curator.get_curation_status(db, tenant_id, provider_id)


# Singleton service instance
curator_service = AutonomousCuratorService()
