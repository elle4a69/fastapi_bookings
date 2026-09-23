"""Tenant-safe hybrid retrieval for accepted durable knowledge only."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.curated_memory import CuratedMemory
from .knowledge_policy import APPROVED_AUTHORITIES, authority_score, is_effective


@dataclass(frozen=True)
class RetrievalDecision:
    """Privacy-safe retrieval evidence; contains no query or answer text."""

    memory_id: int
    authority: str
    scope: str
    semantic_score: float
    lexical_score: float
    combined_score: float
    decision_code: str = "selected_active_durable_knowledge"


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _lexical_score(query: str, memory: CuratedMemory) -> float:
    query_tokens = _tokens(query)
    record_tokens = _tokens(f"{memory.user_query} {memory.ideal_response}")
    if not query_tokens or not record_tokens:
        return 0.0
    return len(query_tokens & record_tokens) / len(query_tokens | record_tokens)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(value * value for value in left))
    norm_right = math.sqrt(sum(value * value for value in right))
    if not norm_left or not norm_right:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_left * norm_right)))


async def retrieve_durable_knowledge(
    db: AsyncSession,
    *,
    tenant_id: int,
    provider_id: Optional[int],
    query: str,
    query_embedding: Optional[list[float]] = None,
    category: Optional[str] = None,
    at: Optional[datetime] = None,
    limit: int = 5,
    min_confidence: float = 0.5,
) -> list[tuple[CuratedMemory, RetrievalDecision]]:
    """Return eligible tenant/provider knowledge ranked by hybrid relevance.

    SQL filters establish the hard security and governance boundary.  Semantic
    and lexical ranking occurs only after status, authority, effective-date,
    scope, confidence and conflict checks have passed.
    """

    if tenant_id <= 0 or limit < 1:
        return []
    now = at or datetime.now(timezone.utc)
    stmt = select(CuratedMemory).where(
        CuratedMemory.tenant_id == tenant_id,
        CuratedMemory.status == "active",
        CuratedMemory.conflict_state == "clear",
        CuratedMemory.authority.in_(APPROVED_AUTHORITIES),
        CuratedMemory.knowledge_kind.in_(
            ("durable_fact", "response_guidance", "style_example")
        ),
        CuratedMemory.confidence_score >= min_confidence,
        CuratedMemory.effective_from <= now,
        or_(CuratedMemory.effective_until.is_(None), CuratedMemory.effective_until > now),
    )
    if provider_id is None:
        stmt = stmt.where(CuratedMemory.provider_id.is_(None))
    else:
        stmt = stmt.where(
            or_(
                CuratedMemory.provider_id == provider_id,
                CuratedMemory.provider_id.is_(None),
            )
        )
    if category:
        stmt = stmt.where(CuratedMemory.category == category)

    result = await db.execute(stmt)
    eligible = [
        memory
        for memory in result.scalars().all()
        if is_effective(
            effective_from=memory.effective_from,
            effective_until=memory.effective_until,
            at=now,
        )
    ]

    ranked: list[tuple[CuratedMemory, RetrievalDecision]] = []
    for memory in eligible:
        lexical = _lexical_score(query, memory)
        semantic = 0.0
        if query_embedding is not None and memory.embedding is not None:
            semantic = max(0.0, _cosine_similarity(query_embedding, list(memory.embedding)))
        authority_component = max(0, authority_score(memory.authority)) / 400.0
        scope_component = 1.0 if provider_id is not None and memory.provider_id == provider_id else 0.8
        combined = (
            0.45 * semantic
            + 0.30 * lexical
            + 0.15 * authority_component
            + 0.10 * scope_component
        )
        ranked.append(
            (
                memory,
                RetrievalDecision(
                    memory_id=memory.id,
                    authority=memory.authority,
                    scope="provider" if memory.provider_id is not None else "tenant",
                    semantic_score=round(semantic, 6),
                    lexical_score=round(lexical, 6),
                    combined_score=round(combined, 6),
                ),
            )
        )

    ranked.sort(
        key=lambda item: (
            item[1].combined_score,
            authority_score(item[0].authority),
            item[0].last_verified_at,
        ),
        reverse=True,
    )
    return ranked[: min(limit, 50)]
