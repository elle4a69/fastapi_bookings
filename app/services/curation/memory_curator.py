"""Governed, proposal-first tenant knowledge curator.

Conversation transcripts can produce review proposals, but never directly
create, update or delete responder knowledge.  Dynamic facts are rejected and
must be resolved from the live FastAPI Bookings domain.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.audit import AuditLog
from ...models.curated_memory import CuratedMemory, KnowledgeProposal
from ...models.provider import Provider
from ...models.user import User
from .knowledge_policy import APPROVED_AUTHORITIES, classify_knowledge_safety
from .pii_scrubber import scrub_pii
from ...core.config import settings
from ...models.knowledge_projection import KnowledgeGraphProjection
from app.services.knowledge.gateway import knowledge_gateway


class CuratorPolicy(BaseModel):
    """Explicit curator autonomy configuration; proposal-only is the default."""

    mode: Literal["proposal_only", "safe_housekeeping", "trusted_ingestion"] = (
        "proposal_only"
    )
    allow_non_destructive_housekeeping: bool = False
    allow_trusted_owner_ingestion: bool = False
    trusted_confidence_threshold: float = Field(default=0.95, ge=0.9, le=1.0)


class CuratorDecision(BaseModel):
    """Privacy-safe outcome returned to workers and observability code."""

    action: Literal[
        "PROPOSE_ADD",
        "PROPOSE_DUPLICATE",
        "PROPOSE_CONFLICT",
        "PROPOSE_STALE",
        "PROPOSE_SUPERSEDE",
        "PROPOSE_GAP",
        "REJECT_DYNAMIC",
        "NOOP",
        # Accepted for backwards-compatible deserialisation only; this service
        # never generates these legacy auto-mutation actions.
        "ADD",
        "UPDATE",
        "DELETE",
    ]
    proposal_id: Optional[int] = None
    target_memory_id: Optional[int] = None
    ideal_response: Optional[str] = None
    category: str = "general"
    rationale: str
    user_query: Optional[str] = None
    requires_review: bool = True
    contains_dynamic_fact: bool = False
    reason_code: str = "proposal_created"

    model_config = ConfigDict(extra="forbid")


class CuratorIssue(BaseModel):
    """Structural queue signal with no knowledge or customer content."""

    issue_type: Literal["duplicate", "invalid", "conflict", "stale", "supersession"]
    memory_ids: list[int]
    reason_code: str
    requires_review: bool = True


_TRIVIAL_USER_RE = re.compile(
    r"^(?:hi|hello|hey|g'day|thanks|thank you|cheers|ok|okay|bye|yes|no)[\s!.]*$",
    re.IGNORECASE,
)
_HUMAN_ESCALATION_RE = re.compile(
    r"\b(?:speak to (?:someone|a human|an agent)|representative|operator|real person|escalate)\b",
    re.IGNORECASE,
)


def extract_qa_candidates(
    transcript: list[dict[str, Any]],
) -> list[tuple[str, str, list[str]]]:
    """Extract adjacent customer/assistant Q&A pairs from supported formats."""

    customer_names: list[str] = []
    normalized: list[tuple[str, str]] = []
    for message in transcript:
        sender = message.get("sender")
        sender_name = sender.get("name") if isinstance(sender, dict) else message.get("sender_name")
        if isinstance(sender_name, str) and sender_name.strip():
            customer_names.append(sender_name.strip())

        content = str(message.get("content") or "").strip()
        if not content:
            continue
        role = str(message.get("role") or "").lower()
        message_type = str(message.get("message_type") or "").lower()
        if role in {"user", "customer", "client"} or message_type == "incoming":
            normalized.append(("user", content))
        elif role in {"assistant", "agent", "bot", "staff"} or message_type == "outgoing":
            normalized.append(("assistant", content))

    candidates: list[tuple[str, str, list[str]]] = []
    index = 0
    while index < len(normalized):
        if normalized[index][0] != "user":
            index += 1
            continue
        question = normalized[index][1]
        index += 1
        answers: list[str] = []
        while index < len(normalized) and normalized[index][0] == "assistant":
            answers.append(normalized[index][1])
            index += 1
        if answers:
            candidates.append((question, "\n".join(answers), customer_names))
    return candidates


def is_valuable_qa(user_query: str, assistant_response: str) -> bool:
    """Exclude trivial, empty and human-escalation dialogue."""

    query = user_query.strip()
    response = assistant_response.strip()
    return bool(
        len(query) >= 5
        and len(response) >= 10
        and not _TRIVIAL_USER_RE.match(query)
        and not _HUMAN_ESCALATION_RE.search(query)
        and "transferred your request to a team member" not in response.lower()
    )


def generate_deterministic_embedding(text: str, dim: int = 1536) -> list[float]:
    """Generate a stable local embedding without disclosing text externally."""

    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    vector = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else [0.0] * dim


async def compute_embedding(text: str) -> list[float]:
    """Return a deterministic local embedding of scrubbed text.

    External embedding calls are deliberately excluded from the curator path;
    callers that use an approved privacy gateway may pass their own vectors to
    retrieval separately.
    """

    return generate_deterministic_embedding(scrub_pii(text))


def compute_cosine_distance(left: list[float], right: list[float]) -> float:
    """Return bounded cosine distance."""

    if len(left) != len(right) or not left:
        return 1.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 1.0
    return max(0.0, min(2.0, 1.0 - dot / (left_norm * right_norm)))


def _text_similarity(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"\w+", left.lower()))
    right_tokens = set(re.findall(r"\w+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def detect_category(query: str, response: str) -> str:
    """Classify a candidate category without declaring it safe to persist."""

    combined = f"{query} {response}".lower()
    if any(word in combined for word in ("price", "cost", "fee", "$", "payment")):
        return "pricing"
    if any(word in combined for word in ("available", "slot", "appointment time")):
        return "availability"
    if any(word in combined for word in ("cancel", "refund", "reschedule", "policy", "notice")):
        return "policy"
    if any(word in combined for word in ("service", "treatment", "duration", "specialist")):
        return "service_info"
    return "faq"


async def find_candidate_memories(
    db: AsyncSession,
    tenant_id: int,
    embedding: list[float],
    provider_id: Optional[int] = None,
    limit: int = 5,
) -> list[tuple[CuratedMemory, float]]:
    """Find tenant/scope candidates locally without unsafe transaction rollback."""

    stmt = select(CuratedMemory).where(CuratedMemory.tenant_id == tenant_id)
    if provider_id is None:
        stmt = stmt.where(CuratedMemory.provider_id.is_(None))
    else:
        stmt = stmt.where(
            or_(CuratedMemory.provider_id == provider_id, CuratedMemory.provider_id.is_(None))
        )
    result = await db.execute(stmt)
    ranked: list[tuple[CuratedMemory, float]] = []
    for memory in result.scalars().all():
        if memory.embedding is not None:
            distance = compute_cosine_distance(embedding, list(memory.embedding))
        else:
            distance = 1.0
        ranked.append((memory, distance))
    ranked.sort(key=lambda item: item[1])
    return ranked[: max(1, min(limit, 50))]


def _fingerprint(*parts: str) -> str:
    normalized = "\n".join(" ".join(part.lower().split()) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def _validate_provider_scope(
    db: AsyncSession, *, tenant_id: int, provider_id: Optional[int]
) -> None:
    if provider_id is None:
        return
    result = await db.execute(
        select(Provider.id).where(
            Provider.id == provider_id,
            Provider.tenant_id == tenant_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("provider is not available in the tenant scope")


async def _require_owner_admin(
    db: AsyncSession, *, tenant_id: int, actor_user_id: int, claimed_role: str
) -> str:
    result = await db.execute(
        select(User).where(User.id == actor_user_id, User.tenant_id == tenant_id)
    )
    actor = result.scalar_one_or_none()
    if actor is None or actor.role.lower() not in {"owner", "admin"}:
        raise PermissionError("operation requires a tenant owner or admin")
    if claimed_role.lower() != actor.role.lower():
        raise PermissionError("claimed role does not match the authenticated tenant user")
    return actor.role.lower()


async def _audit(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: Optional[int],
    action: str,
    target_type: str,
    target_id: Optional[int],
    metadata: dict[str, Any],
) -> None:
    """Persist structural-only audit evidence."""

    safe_keys = {
        "proposal_type",
        "reason_code",
        "resolution_code",
        "authority",
        "knowledge_kind",
        "contains_dynamic_fact",
        "requires_review",
    }
    details = {key: metadata[key] for key in safe_keys if key in metadata}
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=json.dumps(details, sort_keys=True),
        )
    )


async def _persist_proposal(
    db: AsyncSession,
    *,
    tenant_id: int,
    provider_id: Optional[int],
    proposal_type: str,
    category: str,
    user_query: Optional[str],
    proposed_response: Optional[str],
    target_memory_id: Optional[int],
    reason_code: str,
    confidence_score: float,
    contains_dynamic_fact: bool,
    status: str = "pending",
) -> KnowledgeProposal:
    fingerprint = _fingerprint(
        proposal_type,
        str(provider_id or "tenant"),
        user_query or "redacted",
        proposed_response or reason_code,
        str(target_memory_id or "none"),
    )
    result = await db.execute(
        select(KnowledgeProposal).where(
            KnowledgeProposal.tenant_id == tenant_id,
            KnowledgeProposal.fingerprint == fingerprint,
            KnowledgeProposal.status == status,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.evidence_count += 1
        existing.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return existing

    proposal = KnowledgeProposal(
        tenant_id=tenant_id,
        provider_id=provider_id,
        proposal_type=proposal_type,
        status=status,
        category=category,
        knowledge_kind="durable_fact",
        authority="conversation_candidate",
        user_query=user_query,
        proposed_response=proposed_response,
        target_memory_id=target_memory_id,
        fingerprint=fingerprint,
        reason_code=reason_code,
        confidence_score=confidence_score,
        contains_dynamic_fact=contains_dynamic_fact,
        requires_review=True,
    )
    db.add(proposal)
    await db.flush()
    await _audit(
        db,
        tenant_id=tenant_id,
        user_id=None,
        action="knowledge_proposal_created",
        target_type="knowledge_proposal",
        target_id=proposal.id,
        metadata={
            "proposal_type": proposal_type,
            "reason_code": reason_code,
            "contains_dynamic_fact": contains_dynamic_fact,
            "requires_review": True,
        },
    )
    return proposal


async def evaluate_curator_decision(
    scrubbed_query: str,
    scrubbed_response: str,
    candidates: list[tuple[CuratedMemory, float]],
    category: str,
) -> CuratorDecision:
    """Return a proposal decision without mutating durable knowledge."""

    safety = classify_knowledge_safety(
        scrubbed_query, scrubbed_response, category=category
    )
    if not safety.durable:
        return CuratorDecision(
            action="REJECT_DYNAMIC",
            category=category,
            rationale="Candidate requires authoritative live data.",
            contains_dynamic_fact=True,
            reason_code=safety.reason_code,
        )
    if not candidates:
        return CuratorDecision(
            action="PROPOSE_ADD",
            category=category,
            rationale="No scoped durable candidate exists.",
            user_query=scrubbed_query,
            ideal_response=scrubbed_response,
            reason_code="new_durable_candidate",
        )

    best, distance = candidates[0]
    answer_similarity = _text_similarity(best.ideal_response, scrubbed_response)
    query_similarity = _text_similarity(best.user_query, scrubbed_query)
    if distance < 0.2 or query_similarity >= 0.8:
        if answer_similarity >= 0.8:
            action = "PROPOSE_DUPLICATE"
            reason = "probable_duplicate"
        else:
            action = "PROPOSE_CONFLICT"
            reason = "same_scope_conflicting_answer"
        return CuratorDecision(
            action=action,
            target_memory_id=best.id,
            category=category,
            rationale="Candidate overlaps existing scoped knowledge and requires review.",
            user_query=scrubbed_query,
            ideal_response=scrubbed_response,
            reason_code=reason,
        )
    return CuratorDecision(
        action="PROPOSE_ADD",
        category=category,
        rationale="Candidate appears distinct but requires review.",
        user_query=scrubbed_query,
        ideal_response=scrubbed_response,
        reason_code="new_durable_candidate",
    )


async def curate_conversation(
    tenant_id: int,
    transcript: list[dict[str, Any]],
    db: AsyncSession,
    provider_id: Optional[int] = None,
    *,
    policy: Optional[CuratorPolicy] = None,
) -> list[CuratorDecision]:
    """Create review proposals from a transcript; never mutate memory."""

    if tenant_id <= 0:
        raise ValueError("tenant_id must be a positive database identifier")
    await _validate_provider_scope(db, tenant_id=tenant_id, provider_id=provider_id)
    active_policy = policy or CuratorPolicy()
    # The mode is recorded by configuration, but conversation learning is
    # proposal-only in every mode.  Trusted ingestion is a separate explicit API.
    _ = active_policy
    decisions: list[CuratorDecision] = []
    for raw_query, raw_response, customer_names in extract_qa_candidates(transcript):
        if not is_valuable_qa(raw_query, raw_response):
            continue
        query = scrub_pii(raw_query, customer_names=customer_names)
        response = scrub_pii(raw_response, customer_names=customer_names)
        category = detect_category(query, response)
        safety = classify_knowledge_safety(query, response, category=category)
        if not safety.durable:
            # Retain only structural rejection evidence. Raw dynamic/customer
            # content is deliberately absent even from the proposal table.
            proposal = await _persist_proposal(
                db,
                tenant_id=tenant_id,
                provider_id=provider_id,
                proposal_type="quarantine",
                category=category,
                user_query=None,
                proposed_response=None,
                target_memory_id=None,
                reason_code=safety.reason_code,
                confidence_score=0.0,
                contains_dynamic_fact=True,
                status="rejected",
            )
            decisions.append(
                CuratorDecision(
                    action="REJECT_DYNAMIC",
                    proposal_id=proposal.id,
                    category=category,
                    rationale="Dynamic content rejected; use the live domain source.",
                    contains_dynamic_fact=True,
                    reason_code=safety.reason_code,
                )
            )
            continue

        embedding = await compute_embedding(query)
        candidates = await find_candidate_memories(
            db, tenant_id, embedding, provider_id=provider_id
        )
        decision = await evaluate_curator_decision(
            query, response, candidates, category
        )
        proposal_type = {
            "PROPOSE_ADD": "add",
            "PROPOSE_DUPLICATE": "duplicate",
            "PROPOSE_CONFLICT": "conflict",
        }[decision.action]
        proposal = await _persist_proposal(
            db,
            tenant_id=tenant_id,
            provider_id=provider_id,
            proposal_type=proposal_type,
            category=category,
            user_query=query,
            proposed_response=response,
            target_memory_id=decision.target_memory_id,
            reason_code=decision.reason_code,
            confidence_score=0.75,
            contains_dynamic_fact=False,
        )
        decision.proposal_id = proposal.id
        decisions.append(decision)

    await db.commit()
    return decisions


async def ingest_trusted_knowledge(
    db: AsyncSession,
    *,
    tenant_id: int,
    provider_id: Optional[int],
    actor_user_id: int,
    actor_role: str,
    user_query: str,
    ideal_response: str,
    category: str,
    confidence_score: float,
    authority: str,
    policy: CuratorPolicy,
) -> CuratedMemory:
    """Explicit high-confidence owner/admin ingestion, disabled by default."""

    if not policy.allow_trusted_owner_ingestion or policy.mode != "trusted_ingestion":
        raise PermissionError("trusted ingestion is disabled")
    verified_role = await _require_owner_admin(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        claimed_role=actor_role,
    )
    await _validate_provider_scope(db, tenant_id=tenant_id, provider_id=provider_id)
    if authority not in APPROVED_AUTHORITIES:
        raise ValueError("authority is not approved for durable retrieval")
    if verified_role == "admin" and authority == "owner_verified":
        raise PermissionError("an admin cannot assign owner authority")
    if confidence_score < policy.trusted_confidence_threshold:
        raise ValueError("confidence is below the trusted ingestion threshold")
    safety = classify_knowledge_safety(user_query, ideal_response, category=category)
    if not safety.durable:
        raise ValueError(safety.reason_code)
    scrubbed_query = scrub_pii(user_query)
    scrubbed_response = scrub_pii(ideal_response)
    embedding = await compute_embedding(scrubbed_query)
    candidates = await find_candidate_memories(
        db, tenant_id, embedding, provider_id=provider_id
    )
    for candidate, _distance in candidates:
        if _text_similarity(candidate.user_query, scrubbed_query) >= 0.8:
            raise ValueError("conflict_or_replacement_requires_proposal_review")

    now = datetime.now(timezone.utc)
    memory = CuratedMemory(
        tenant_id=tenant_id,
        provider_id=provider_id,
        category=category,
        user_query=scrubbed_query,
        ideal_response=scrubbed_response,
        embedding=embedding,
        confidence_score=confidence_score,
        knowledge_kind="durable_fact",
        authority=authority,
        status="active",
        conflict_state="clear",
        content_hash=_fingerprint(scrubbed_query, scrubbed_response),
        verified_by_user_id=actor_user_id,
        effective_from=now,
        last_verified_at=now,
    )
    db.add(memory)
    await db.flush()

    if settings.GRAPH_SHADOW_WRITE or settings.GRAPH_KNOWLEDGE_ENABLED:
        graph_group_id = (
            f"tenant:{tenant_id}:provider:{provider_id}"
            if provider_id is not None
            else f"tenant:{tenant_id}:shared"
        )
        proj = KnowledgeGraphProjection(
            tenant_id=tenant_id,
            provider_id=provider_id,
            curated_memory_id=memory.id,
            projection_type="upsert_fact",
            graph_group_id=graph_group_id,
            status="pending",
            projection_version="2.0",
            created_at=now,
            updated_at=now,
        )
        db.add(proj)
    knowledge_gateway.invalidate(tenant_id, provider_id)

    await _audit(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        action="trusted_knowledge_ingested",
        target_type="curated_memory",
        target_id=memory.id,
        metadata={"authority": authority, "knowledge_kind": "durable_fact"},
    )
    await db.commit()
    await db.refresh(memory)
    return memory


async def review_proposal(
    db: AsyncSession,
    *,
    tenant_id: int,
    proposal_id: int,
    actor_user_id: int,
    actor_role: str,
    decision: Literal["accept", "reject", "dismiss", "resolve"],
    resolution_code: str,
    explicit_conflict_resolution: bool = False,
) -> tuple[KnowledgeProposal, Optional[CuratedMemory]]:
    """Accept/reject/dismiss/resolve a proposal with tenant and role gates."""

    verified_role = await _require_owner_admin(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        claimed_role=actor_role,
    )
    result = await db.execute(
        select(KnowledgeProposal).where(
            KnowledgeProposal.id == proposal_id,
            KnowledgeProposal.tenant_id == tenant_id,
        )
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise LookupError("knowledge proposal not found")
    if proposal.status != "pending":
        raise ValueError("knowledge proposal is not pending")
    if decision == "accept" and proposal.contains_dynamic_fact:
        raise ValueError("dynamic facts cannot be accepted as durable knowledge")
    if decision == "accept" and proposal.proposal_type in {"conflict", "supersede"} and not explicit_conflict_resolution:
        raise ValueError("conflict or replacement requires explicit resolution")

    now = datetime.now(timezone.utc)
    created_memory: Optional[CuratedMemory] = None
    if decision == "accept":
        if not proposal.user_query or not proposal.proposed_response:
            raise ValueError("proposal has no reusable knowledge content")
        safety = classify_knowledge_safety(
            proposal.user_query, proposal.proposed_response, category=proposal.category
        )
        if not safety.durable:
            raise ValueError(safety.reason_code)
        if proposal.proposal_type == "duplicate":
            proposal.status = "resolved"
        else:
            if proposal.target_memory_id is not None:
                target_result = await db.execute(
                    select(CuratedMemory).where(
                        CuratedMemory.id == proposal.target_memory_id,
                        CuratedMemory.tenant_id == tenant_id,
                    )
                )
                target = target_result.scalar_one_or_none()
                if target is None:
                    raise LookupError("target memory not found in tenant")
                target.status = "superseded"
                target.effective_until = now
            created_memory = CuratedMemory(
                tenant_id=tenant_id,
                provider_id=proposal.provider_id,
                category=proposal.category,
                user_query=proposal.user_query,
                ideal_response=proposal.proposed_response,
                embedding=await compute_embedding(proposal.user_query),
                confidence_score=max(0.9, proposal.confidence_score),
                knowledge_kind=proposal.knowledge_kind,
                authority="owner_verified" if verified_role == "owner" else "admin_verified",
                status="active",
                conflict_state="clear",
                content_hash=_fingerprint(proposal.user_query, proposal.proposed_response),
                supersedes_id=proposal.target_memory_id,
                verified_by_user_id=actor_user_id,
                effective_from=now,
                last_verified_at=now,
            )
            db.add(created_memory)
            await db.flush()

            if settings.GRAPH_SHADOW_WRITE or settings.GRAPH_KNOWLEDGE_ENABLED:
                graph_group_id = (
                    f"tenant:{tenant_id}:provider:{proposal.provider_id}"
                    if proposal.provider_id is not None
                    else f"tenant:{tenant_id}:shared"
                )
                proj = KnowledgeGraphProjection(
                    tenant_id=tenant_id,
                    provider_id=proposal.provider_id,
                    curated_memory_id=created_memory.id,
                    projection_type="supersede_fact" if proposal.target_memory_id is not None else "upsert_fact",
                    graph_group_id=graph_group_id,
                    status="pending",
                    projection_version="2.0",
                    created_at=now,
                    updated_at=now,
                )
                db.add(proj)
            knowledge_gateway.invalidate(tenant_id, proposal.provider_id)

            proposal.status = "accepted"
    else:
        proposal.status = {
            "reject": "rejected",
            "dismiss": "dismissed",
            "resolve": "resolved",
        }[decision]

    proposal.reviewed_by_user_id = actor_user_id
    proposal.reviewed_at = now
    proposal.resolution_code = resolution_code[:64]
    await _audit(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        action=f"knowledge_proposal_{proposal.status}",
        target_type="knowledge_proposal",
        target_id=proposal.id,
        metadata={
            "proposal_type": proposal.proposal_type,
            "resolution_code": proposal.resolution_code,
            "contains_dynamic_fact": proposal.contains_dynamic_fact,
        },
    )
    await db.commit()
    await db.refresh(proposal)
    if created_memory is not None:
        await db.refresh(created_memory)
    return proposal, created_memory


def analyze_knowledge_records(
    records: list[CuratedMemory], *, stale_after_days: int = 365
) -> list[CuratorIssue]:
    """Detect invalid, duplicate, conflicting, stale and superseded records."""

    issues: list[CuratorIssue] = []
    now = datetime.now(timezone.utc)
    active = [record for record in records if record.status == "active"]
    for record in records:
        safety = classify_knowledge_safety(
            record.user_query, record.ideal_response, category=record.category
        )
        if not safety.durable:
            issues.append(
                CuratorIssue(
                    issue_type="invalid",
                    memory_ids=[record.id],
                    reason_code=safety.reason_code,
                )
            )
        verified = record.last_verified_at
        if verified.tzinfo is None:
            verified = verified.replace(tzinfo=timezone.utc)
        if verified < now - timedelta(days=stale_after_days):
            issues.append(
                CuratorIssue(
                    issue_type="stale",
                    memory_ids=[record.id],
                    reason_code="verification_expired",
                )
            )
        if record.status == "superseded":
            issues.append(
                CuratorIssue(
                    issue_type="supersession",
                    memory_ids=[record.id],
                    reason_code="superseded_record_retained_for_audit",
                )
            )

    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if left.tenant_id != right.tenant_id or left.provider_id != right.provider_id:
                continue
            if _text_similarity(left.user_query, right.user_query) < 0.8:
                continue
            answer_similarity = _text_similarity(left.ideal_response, right.ideal_response)
            issues.append(
                CuratorIssue(
                    issue_type="duplicate" if answer_similarity >= 0.8 else "conflict",
                    memory_ids=[left.id, right.id],
                    reason_code=(
                        "probable_duplicate" if answer_similarity >= 0.8 else "same_scope_conflicting_answer"
                    ),
                )
            )
    return issues


async def record_unanswered_gap(
    db: AsyncSession,
    *,
    tenant_id: int,
    provider_id: Optional[int],
    question: str,
) -> CuratorDecision:
    """Record a scrubbed unanswered gap for operator review."""

    scrubbed = scrub_pii(question)
    await _validate_provider_scope(db, tenant_id=tenant_id, provider_id=provider_id)
    safety = classify_knowledge_safety(scrubbed, "Unanswered knowledge gap")
    if not safety.durable:
        proposal = await _persist_proposal(
            db,
            tenant_id=tenant_id,
            provider_id=provider_id,
            proposal_type="quarantine",
            category="gap",
            user_query=None,
            proposed_response=None,
            target_memory_id=None,
            reason_code=safety.reason_code,
            confidence_score=0.0,
            contains_dynamic_fact=True,
            status="rejected",
        )
        action = "REJECT_DYNAMIC"
    else:
        proposal = await _persist_proposal(
            db,
            tenant_id=tenant_id,
            provider_id=provider_id,
            proposal_type="gap",
            category="gap",
            user_query=scrubbed,
            proposed_response=None,
            target_memory_id=None,
            reason_code="unanswered_reusable_question",
            confidence_score=0.0,
            contains_dynamic_fact=False,
        )
        action = "PROPOSE_GAP"
    await db.commit()
    return CuratorDecision(
        action=action,
        proposal_id=proposal.id,
        category="gap",
        rationale="Unanswered question recorded for review.",
        reason_code=proposal.reason_code,
        contains_dynamic_fact=proposal.contains_dynamic_fact,
    )
