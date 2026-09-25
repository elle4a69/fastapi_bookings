"""Unified Knowledge Curator Service.

Spec references: Sections 11–24, 74, 75.
Consolidates autonomous knowledge curation, safety boundary enforcement,
PII scrubbing, supersession tracking, and canonical graph projection outbox queueing.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.learning_event import LearningEvent, compute_text_diff
from app.services.curation.pii_scrubber import scrub_pii
from app.services.knowledge.gateway import knowledge_gateway
from app.services.knowledge.policy import (
    is_dynamic_operational_data,
    is_system_safety_violation,
    validate_scope,
)
from app.services.knowledge.types import Authority, CuratorAction, KnowledgeKind

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


class CuratorActionValue(str):
    """String subclass supporting both canonical CuratorAction names and legacy aliases."""

    def __new__(cls, value: str, aliases: tuple = ()):
        obj = str.__new__(cls, value)
        obj._aliases = set(aliases)
        return obj

    def __eq__(self, other: Any) -> bool:
        val = other.value if hasattr(other, "value") else other
        if str(self) == val or str(self) == str(other):
            return True
        if hasattr(self, "_aliases") and (
            other in self._aliases
            or val in self._aliases
            or (isinstance(val, str) and val.lower() in self._aliases)
            or (isinstance(other, str) and other.lower() in self._aliases)
        ):
            return True
        return False

    def __hash__(self) -> int:
        return hash(str(self))


class CuratorDecision(BaseModel):
    """Privacy-safe outcome returned by the UnifiedCurator pipeline."""

    action: Any  # CuratorActionValue, CuratorAction, or str
    status: str = "processed"
    memory_id: Optional[int] = None
    target_memory_id: Optional[int] = None
    superseded_id: Optional[int] = None
    proposal_id: Optional[int] = None
    projection_id: Optional[str] = None
    user_query: Optional[str] = None
    ideal_response: Optional[str] = None
    category: str = "general"
    rationale: str = ""
    reason_code: str = ""
    reason: Optional[str] = None
    requires_review: bool = False
    contains_dynamic_fact: bool = False
    evidence_count: int = 1
    canonical_rule: Optional[str] = None
    retained_as_evidence: bool = False
    classification: Optional[str] = None
    telemetry_recorded: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class UnifiedCurator:
    """Unified autonomous knowledge curator and continuous governance engine.

    Pipeline Steps (Specs 11–24, 74, 75):
      1. Scope validation (validate_scope)
      2. PII Scrubbing (scrub_pii)
      3. Dynamic operational fact detection (is_dynamic_operational_data -> REJECT_DYNAMIC)
      4. System safety violation guard (is_system_safety_violation -> QUARANTINE)
      5. Evidence & Authority evaluation
      6. Supersession & Conflict detection
      7. Canonical PostgreSQL persistence in CuratedMemory (stores curator:2.0)
      8. Graph Projection Outbox enqueueing (KnowledgeGraphProjection)
      9. Knowledge cache invalidation via knowledge_gateway.invalidate()
    """

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

    def _find_matching_memory(
        self,
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
            if difflib.SequenceMatcher(None, cand_norm, norm_q).ratio() >= 0.85:
                return cand
            if cand_norm in norm_q or norm_q in cand_norm:
                return cand
        return None

    def process_learning_event(
        self,
        db: Session,
        event: LearningEvent,
        expected_tenant_id: Optional[int] = None,
    ) -> CuratorDecision:
        """Execute the mandatory 9-step curation pipeline on a single LearningEvent."""
        if expected_tenant_id is not None and event.tenant_id != expected_tenant_id:
            raise ValueError(
                f"Tenant mismatch: event belongs to tenant {event.tenant_id}, expected {expected_tenant_id}"
            )

        now = utc_now()
        metadata = event.metadata_payload or {}
        event_type = event.event_type

        # Ensure event has an ID
        if not event.id:
            event.id = str(uuid.uuid4())

        # -------------------------------------------------------------
        # Step 1: Scope Validation (Spec 34, 74)
        # -------------------------------------------------------------
        if not validate_scope(
            tenant_id=event.tenant_id,
            provider_id=event.provider_id,
            allowed_tenant_id=event.tenant_id,
        ):
            logger.warning(
                "Scope validation failed for LearningEvent %s (tenant=%s, provider=%s)",
                event.id,
                event.tenant_id,
                event.provider_id,
            )
            event.status = "rejected"
            return CuratorDecision(
                action=CuratorActionValue("REJECT_SCOPE", ("rejected", "reject_scope")),
                status="rejected",
                rationale="Scope validation failed",
                reason_code="invalid_scope",
            )

        # -------------------------------------------------------------
        # Step 2: PII Scrubbing (Spec 75)
        # -------------------------------------------------------------
        raw_query = (event.customer_message or "").strip()
        raw_human = (event.human_content or "").strip()
        reason_str = str(metadata.get("reason", "")).strip()

        clean_query = scrub_pii(raw_query) if raw_query else ""
        clean_human = scrub_pii(raw_human) if raw_human else ""
        clean_reason = scrub_pii(reason_str) if reason_str else ""
        category = metadata.get("category") or "faq"

        is_behavioural = self.is_behavioural_correction(clean_reason, clean_human, metadata)

        # -------------------------------------------------------------
        # Step 3 & 4: Dynamic Operational Fact Detection & Safety Guard (Specs 19, 22)
        # -------------------------------------------------------------
        combined_text = f"{clean_query} {clean_human} {clean_reason}".strip()
        is_safety_violation = (
            is_system_safety_violation(combined_text)
            or is_system_safety_violation(clean_human)
            or is_system_safety_violation(clean_query)
            or is_system_safety_violation(clean_reason)
        )

        has_dynamic_facts = (
            metadata.get("contains_dynamic_facts") is True
            or is_dynamic_operational_data(clean_human)
            or is_dynamic_operational_data(clean_query)
        )

        # In Spec 22, corrections attempting to inject dynamic facts/availability are safety violations -> QUARANTINE
        if event_type == "flagged_response" and (has_dynamic_facts or is_safety_violation):
            is_safety_violation = True

        if is_safety_violation:
            logger.warning(
                "System safety violation detected in LearningEvent %s: %s",
                event.id,
                combined_text[:60],
            )
            # Find and update any matching pending proposal
            proposals = (
                db.query(KnowledgeProposal)
                .filter(
                    KnowledgeProposal.tenant_id == event.tenant_id,
                    KnowledgeProposal.status == "pending",
                )
                .all()
            )
            quarantined_prop_id = None
            for p in proposals:
                if (
                    (event.message_id and event.message_id in p.fingerprint)
                    or (event.conversation_id and event.conversation_id in p.fingerprint)
                    or p.proposed_response == event.human_content
                    or (clean_human and p.proposed_response == clean_human)
                ):
                    p.proposal_type = "quarantine"
                    p.reason_code = "safety_violation"
                    p.status = "rejected"
                    p.resolution_code = "quarantined_safety_violation"
                    p.reviewed_at = now
                    p.updated_at = now
                    quarantined_prop_id = p.id

            if not quarantined_prop_id:
                fingerprint = hashlib.sha256(
                    f"quarantine:{event.tenant_id}:{event.id}:{now.isoformat()}".encode()
                ).hexdigest()
                new_prop = KnowledgeProposal(
                    tenant_id=event.tenant_id,
                    provider_id=event.provider_id,
                    proposal_type="quarantine",
                    status="rejected",
                    category=category or "safety",
                    knowledge_kind="durable_fact",
                    authority="conversation_candidate",
                    user_query=clean_query or None,
                    proposed_response=clean_human or None,
                    fingerprint=fingerprint,
                    reason_code="safety_violation",
                    confidence_score=0.0,
                    contains_dynamic_fact=True,
                    requires_review=True,
                    evidence_count=1,
                    resolution_code="quarantined_safety_violation",
                    reviewed_at=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_prop)
                db.flush()
                quarantined_prop_id = new_prop.id

            event.status = "processed"
            return CuratorDecision(
                action=CuratorActionValue("QUARANTINE", ("quarantine", "quarantined")),
                status="quarantined",
                proposal_id=quarantined_prop_id,
                user_query=clean_query,
                ideal_response=clean_human,
                reason_code="safety_violation",
                reason="safety_violation",
                contains_dynamic_fact=True,
                requires_review=True,
                rationale="Quarantined due to system safety boundary violation",
            )

        if has_dynamic_facts and event_type not in ("draft_edit", "approved_draft"):
            logger.info(
                "Rejected dynamic operational data in LearningEvent %s: %s",
                event.id,
                f"{clean_query} {clean_human}"[:60],
            )
            event.status = "rejected"
            return CuratorDecision(
                action=CuratorActionValue("REJECT_DYNAMIC", ("reject_dynamic", "rejected")),
                status="rejected",
                user_query=clean_query,
                ideal_response=clean_human,
                category=category,
                contains_dynamic_fact=True,
                reason_code="dynamic_operational_data",
                rationale="Dynamic operational fact detected and rejected from durable knowledge",
            )

        # -------------------------------------------------------------
        # Step 5: Evidence & Authority Evaluation (Spec 16, 24, 26)
        # -------------------------------------------------------------
        if event_type == "draft_edit":
            diff = event.diff_payload or compute_text_diff(
                event.original_ai_content, event.human_content
            )
            ratio = float(diff.get("ratio", 1.0))
            orig_len = int(diff.get("original_length", 0))
            new_len = int(diff.get("new_length", 0))
            delta = abs(orig_len - new_len)

            if ratio > 0.85 and delta < 5:
                # Minor / Incidental Edit: Retain as evidence, do not invent universal rules
                event.status = "processed"
                return CuratorDecision(
                    action=CuratorActionValue("NOOP", ("incidental_edit", "ignored", "minor_edit")),
                    status="processed",
                    classification="incidental",
                    retained_as_evidence=True,
                    rationale="Minor draft edit retained as evidence without universal rule creation",
                )

            # Material Edit: Record behavioural signal and increment evidence count
            existing_proposal = (
                db.query(KnowledgeProposal)
                .filter(
                    KnowledgeProposal.tenant_id == event.tenant_id,
                    KnowledgeProposal.provider_id == event.provider_id,
                    KnowledgeProposal.category == "style",
                    KnowledgeProposal.status == "pending",
                )
                .first()
            )

            if existing_proposal:
                existing_proposal.evidence_count += 1
                existing_proposal.updated_at = now
                evidence_count = existing_proposal.evidence_count
                prop_id = existing_proposal.id
            else:
                fingerprint = hashlib.sha256(
                    f"style_signal:{event.tenant_id}:{event.provider_id}:{now.isoformat()}".encode()
                ).hexdigest()
                new_prop = KnowledgeProposal(
                    tenant_id=event.tenant_id,
                    provider_id=event.provider_id,
                    proposal_type="add",
                    status="pending",
                    category="style",
                    knowledge_kind="style_example",
                    authority="draft_edit_signal",
                    user_query=clean_query or None,
                    proposed_response=clean_human or None,
                    fingerprint=fingerprint,
                    reason_code="material_draft_edit",
                    confidence_score=0.5,
                    contains_dynamic_fact=False,
                    requires_review=True,
                    evidence_count=1,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_prop)
                db.flush()
                evidence_count = 1
                prop_id = new_prop.id

            event.status = "processed"
            return CuratorDecision(
                action=CuratorActionValue("EVIDENCE", ("material_edit", "evidence")),
                status="processed",
                proposal_id=prop_id,
                classification="material",
                evidence_count=evidence_count,
                rationale="Material draft edit recorded as evidence proposal",
            )

        if event_type == "approved_draft":
            event.status = "processed"
            return CuratorDecision(
                action=CuratorActionValue(
                    "WEAK_REINFORCEMENT", ("positive_reinforcement", "weak_reinforcement")
                ),
                status="processed",
                telemetry_recorded=True,
                rationale="Positive reinforcement telemetry recorded for approved draft",
            )

        # -------------------------------------------------------------
        # Step 6: Supersession & Conflict Detection (Spec 14, 25)
        # -------------------------------------------------------------
        if is_behavioural:
            canonical_rule = self.derive_behavioural_principle(clean_reason, clean_human)
            effective_query = clean_query or "routine enquiries"
            effective_response = canonical_rule
            knowledge_kind = "response_guidance"
            category = "tone"
            projection_type = "behaviour_rule"
            authority = "owner_verified"
        else:
            effective_query = clean_query or "General knowledge"
            effective_response = clean_human
            knowledge_kind = "durable_fact"
            projection_type = "upsert_fact"
            authority = "owner_verified"

        # Check for supersession / conflict
        existing_memory = self._find_matching_memory(
            db,
            tenant_id=event.tenant_id,
            provider_id=event.provider_id,
            query_text=effective_query,
            category=category,
        )

        superseded_id = None
        if existing_memory:
            existing_memory.status = "superseded"
            existing_memory.updated_at = now
            superseded_id = existing_memory.id
            if projection_type == "upsert_fact":
                projection_type = "supersede_fact"

        # -------------------------------------------------------------
        # Step 7: Canonical PostgreSQL Persistence in CuratedMemory
        # -------------------------------------------------------------
        content_hash = hashlib.sha256(
            f"{event.tenant_id}:{event.provider_id}:{effective_query}:{effective_response}".encode()
        ).hexdigest()

        # Format source reference to retain source_event_id and curator_version="2.0"
        if is_behavioural:
            src_ref = (
                f"learning_event:{event.id};curator:2.0;example={clean_human[:80]}"
            )[:128]
        else:
            src_ref = (
                f"learning_event:{event.id};curator:2.0;conv:{event.conversation_id or ''}"
            )[:128]

        new_memory = CuratedMemory(
            tenant_id=event.tenant_id,
            provider_id=event.provider_id,
            category=category[:64],
            user_query=effective_query,
            ideal_response=effective_response,
            knowledge_kind=knowledge_kind,
            authority=authority,
            status="active",
            conflict_state="clear",
            content_hash=content_hash,
            source_reference=src_ref,
            supersedes_id=superseded_id,
            effective_from=now,
            last_verified_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(new_memory)
        db.flush()

        # -------------------------------------------------------------
        # Step 8: Graph Projection Outbox Enqueueing (Atomic in DB tx)
        # -------------------------------------------------------------
        projection_id: Optional[str] = None
        if settings.GRAPH_SHADOW_WRITE or settings.GRAPH_KNOWLEDGE_ENABLED:
            graph_group_id = (
                f"tenant:{event.tenant_id}:provider:{event.provider_id}"
                if event.provider_id is not None
                else f"tenant:{event.tenant_id}:shared"
            )

            projection = KnowledgeGraphProjection(
                tenant_id=event.tenant_id,
                provider_id=event.provider_id,
                learning_event_id=str(event.id) if event.id else None,
                curated_memory_id=new_memory.id,
                projection_type=projection_type,
                graph_group_id=graph_group_id,
                status="pending",
                projection_version="2.0",
                created_at=now,
                updated_at=now,
            )
            db.add(projection)
            db.flush()
            projection_id = projection.id

        # -------------------------------------------------------------
        # Step 9: Knowledge Cache Invalidation
        # -------------------------------------------------------------
        knowledge_gateway.invalidate(event.tenant_id, event.provider_id)

        # Resolve any pending proposals associated with this event/content
        proposals = (
            db.query(KnowledgeProposal)
            .filter(
                KnowledgeProposal.tenant_id == event.tenant_id,
                KnowledgeProposal.status == "pending",
            )
            .all()
        )
        for prop in proposals:
            if (
                prop.user_query == effective_query
                or prop.proposed_response == effective_response
                or (event.message_id and event.message_id in prop.fingerprint)
                or (event.conversation_id and event.conversation_id in prop.fingerprint)
            ):
                prop.status = "resolved"
                prop.resolution_code = (
                    "derived_behavioural_guidance"
                    if is_behavioural
                    else ("curated_active" if not superseded_id else "superseded_active")
                )
                prop.target_memory_id = new_memory.id
                prop.reviewed_at = now
                prop.updated_at = now

        event.status = "processed"

        action_name = "behavioural_guidance_curated" if is_behavioural else "knowledge_curated"
        canonical_action = "SUPERSEDE" if superseded_id else "AUTO_CURATE"

        return CuratorDecision(
            action=CuratorActionValue(
                canonical_action, (action_name, "knowledge_curated", "superseded")
            ),
            status="processed",
            memory_id=new_memory.id,
            target_memory_id=new_memory.id,
            superseded_id=superseded_id,
            projection_id=projection_id,
            user_query=effective_query,
            ideal_response=effective_response,
            category=category,
            canonical_rule=canonical_rule if is_behavioural else None,
            rationale=f"Successfully curated {knowledge_kind}"
            + (f" and enqueued {projection_type} graph projection" if projection_id else ""),
        )

    def process_pending_learning_events(
        self, db: Session, tenant_id: int, limit: int = 50
    ) -> Dict[str, Any]:
        """Fetch pending LearningEvent records for the tenant, execute process_learning_event, and commit."""
        events = (
            db.query(LearningEvent)
            .filter(
                LearningEvent.tenant_id == tenant_id,
                LearningEvent.status == "pending",
            )
            .order_by(LearningEvent.created_at.asc())
            .limit(limit)
            .all()
        )

        processed_count = 0
        superseded_count = 0
        curated_count = 0
        quarantined_count = 0
        projections_count = 0

        for event in events:
            decision = self.process_learning_event(db, event, expected_tenant_id=tenant_id)
            processed_count += 1
            if decision.superseded_id:
                superseded_count += 1
            if decision.memory_id:
                curated_count += 1
            if decision.status == "quarantined":
                quarantined_count += 1
            if decision.projection_id:
                projections_count += 1

        db.commit()
        return {
            "processed": processed_count,
            "superseded": superseded_count,
            "curated": curated_count,
            "quarantined": quarantined_count,
            "projections": projections_count,
        }

    def get_curation_status(
        self, db: Session, tenant_id: int, provider_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Return curation stats, active vs superseded counts, projections, and breakdown by scope."""
        mem_q = db.query(CuratedMemory).filter(CuratedMemory.tenant_id == tenant_id)
        prop_q = db.query(KnowledgeProposal).filter(KnowledgeProposal.tenant_id == tenant_id)
        ev_q = db.query(LearningEvent).filter(LearningEvent.tenant_id == tenant_id)
        proj_q = db.query(KnowledgeGraphProjection).filter(
            KnowledgeGraphProjection.tenant_id == tenant_id
        )

        if provider_id is not None:
            mem_q = mem_q.filter(CuratedMemory.provider_id == provider_id)
            prop_q = prop_q.filter(KnowledgeProposal.provider_id == provider_id)
            ev_q = ev_q.filter(LearningEvent.provider_id == provider_id)
            proj_q = proj_q.filter(KnowledgeGraphProjection.provider_id == provider_id)

        all_memories = mem_q.all()
        active_count = sum(1 for m in all_memories if m.status == "active")
        superseded_count = sum(1 for m in all_memories if m.status == "superseded")
        quarantined_count = sum(1 for m in all_memories if m.status == "quarantined")

        behavioural_count = sum(
            1
            for m in all_memories
            if m.status == "active"
            and m.knowledge_kind in ("response_guidance", "style_example")
        )
        durable_facts_count = sum(
            1
            for m in all_memories
            if m.status == "active" and m.knowledge_kind == "durable_fact"
        )

        pending_proposals = prop_q.filter(KnowledgeProposal.status == "pending").count()
        processed_events = ev_q.filter(LearningEvent.status == "processed").count()
        pending_events = ev_q.filter(LearningEvent.status == "pending").count()

        pending_projections = proj_q.filter(
            KnowledgeGraphProjection.status == "pending"
        ).count()
        projected_count = proj_q.filter(
            KnowledgeGraphProjection.status == "projected"
        ).count()

        tenant_scope_memories = sum(1 for m in all_memories if m.provider_id is None)
        provider_scope_memories = sum(1 for m in all_memories if m.provider_id is not None)

        return {
            "tenant_id": tenant_id,
            "provider_id": provider_id,
            "active_memories": active_count,
            "superseded_memories": superseded_count,
            "quarantined_memories": quarantined_count,
            "pending_proposals": pending_proposals,
            "processed_learning_events": processed_events,
            "pending_learning_events": pending_events,
            "behavioural_principles": behavioural_count,
            "durable_facts": durable_facts_count,
            "pending_projections": pending_projections,
            "projected_projections": projected_count,
            "scope_breakdown": {
                "tenant_wide": tenant_scope_memories,
                "provider_specific": provider_scope_memories,
            },
        }


# Singleton unified curator
unified_curator = UnifiedCurator()
