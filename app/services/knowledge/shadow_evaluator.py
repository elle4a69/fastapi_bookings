"""Shadow Knowledge Retrieval and Canary Evaluation Service.

Spec references: Sections 62, 63, 64, 65, 88, 89.
Executes shadow retrieval comparison alongside legacy retrieval, evaluates
privacy-safe metrics without exposing customer PII or raw text, and gates live
Graphiti context via multi-tenant and provider canary controls.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.knowledge.gateway import knowledge_gateway
from app.services.knowledge.types import (
    Authority,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeScope,
    RetrievalQuery,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


def is_canary_active(tenant_id: int, provider_id: Optional[int] = None) -> bool:
    """Determine whether live Graphiti canary retrieval is active for a scope.

    Spec 64: Canary is active if master GRAPH_KNOWLEDGE_ENABLED is True,
    or if tenant_id is in GRAPH_CANARY_TENANT_IDS, or if provider_id
    is in GRAPH_CANARY_PROVIDER_IDS.
    """
    if getattr(settings, "GRAPH_KNOWLEDGE_ENABLED", False):
        return True
    canary_tenants = getattr(settings, "GRAPH_CANARY_TENANT_IDS", []) or []
    if tenant_id in canary_tenants:
        return True
    if provider_id is not None:
        canary_providers = getattr(settings, "GRAPH_CANARY_PROVIDER_IDS", []) or []
        if provider_id in canary_providers:
            return True
    return False


def resolve_rollout_mode(tenant_id: int, provider_id: Optional[int] = None) -> str:
    """Resolve rollout identification mode: 'graph_live', 'canary', or 'fallback'.

    Sections 31, 32, 33:
    - 'graph_live': When GRAPH_KNOWLEDGE_ENABLED is True (General Availability).
    - 'canary': When GRAPH_KNOWLEDGE_ENABLED is False, but tenant or provider is enrolled in canary.
    - 'fallback': When neither master GA nor canary is active for this scope.
    """
    if getattr(settings, "GRAPH_KNOWLEDGE_ENABLED", False):
        return "graph_live"
    if is_canary_active(tenant_id, provider_id):
        return "canary"
    return "fallback"


def _extract_tokens(texts: List[str]) -> Set[str]:
    """Extract lowercased word tokens of length >= 3 for privacy-safe overlap comparison."""
    tokens: Set[str] = set()
    for text in texts:
        if not text:
            continue
        words = re.findall(r"\w+", text.lower())
        tokens.update(w for w in words if len(w) >= 3)
    return tokens


def compute_overlap_ratio(legacy_result: RetrievalResult, graph_result: RetrievalResult) -> float:
    """Compute token Jaccard similarity between retrieved facts without exposing text.

    Spec 63, 88: Compares token sets between legacy knowledge and Graphiti results.
    Returns a float in [0.0, 1.0]. Zero customer text or PII is returned or retained.
    """
    legacy_texts = list(legacy_result.facts) + list(legacy_result.behavioural_rules) + list(legacy_result.examples)
    graph_texts = list(graph_result.facts) + list(graph_result.behavioural_rules) + list(graph_result.examples)

    if not legacy_texts and not graph_texts:
        return 1.0
    if not legacy_texts or not graph_texts:
        return 0.0

    legacy_tokens = _extract_tokens(legacy_texts)
    graph_tokens = _extract_tokens(graph_texts)

    if not legacy_tokens and not graph_tokens:
        return 1.0
    if not legacy_tokens or not graph_tokens:
        return 0.0

    intersection = len(legacy_tokens & graph_tokens)
    union = len(legacy_tokens | graph_tokens)
    return round(intersection / union, 4) if union > 0 else 0.0


def build_legacy_retrieval_result(
    legacy_knowledge: Dict[str, Any],
    tenant_id: int,
    provider_id: Optional[int] = None,
) -> RetrievalResult:
    """Transform legacy knowledge data (shared/provider entries and curated memories) into a RetrievalResult."""
    facts: List[str] = []
    rules: List[str] = []
    examples: List[str] = []
    items: List[KnowledgeItem] = []

    shared_entries = legacy_knowledge.get("shared_entries") or legacy_knowledge.get("shared_knowledge") or []
    provider_entries = legacy_knowledge.get("provider_entries") or legacy_knowledge.get("provider_knowledge") or []
    curated_memories = legacy_knowledge.get("curated_memories") or []

    for entry in shared_entries:
        txt = getattr(entry, "text", None) or (entry.get("text") if isinstance(entry, dict) else str(entry))
        txt = (txt or "").strip()
        if not txt:
            continue
        cat = str(getattr(entry, "category", "") or (entry.get("category", "") if isinstance(entry, dict) else "")).lower()
        if cat in ("tone", "behaviour", "behavior", "rule"):
            rules.append(txt)
            kind = KnowledgeKind.behaviour_rule
        elif cat in ("example", "style", "few_shot"):
            examples.append(txt)
            kind = KnowledgeKind.style_example
        else:
            facts.append(txt)
            kind = KnowledgeKind.durable_fact

        items.append(
            KnowledgeItem(
                scope=KnowledgeScope(tenant_id=tenant_id, provider_id=None, is_tenant_shared=True),
                kind=kind,
                text=txt,
                authority=Authority.system_import,
                metadata={"source": "legacy_shared"},
            )
        )

    for entry in provider_entries:
        txt = getattr(entry, "text", None) or (entry.get("text") if isinstance(entry, dict) else str(entry))
        txt = (txt or "").strip()
        if not txt:
            continue
        cat = str(getattr(entry, "category", "") or (entry.get("category", "") if isinstance(entry, dict) else "")).lower()
        if cat in ("tone", "behaviour", "behavior", "rule"):
            rules.append(txt)
            kind = KnowledgeKind.behaviour_rule
        elif cat in ("example", "style", "few_shot"):
            examples.append(txt)
            kind = KnowledgeKind.style_example
        else:
            facts.append(txt)
            kind = KnowledgeKind.durable_fact

        items.append(
            KnowledgeItem(
                scope=KnowledgeScope(tenant_id=tenant_id, provider_id=provider_id, is_tenant_shared=False),
                kind=kind,
                text=txt,
                authority=Authority.explicit_provider_instruction,
                metadata={"source": "legacy_provider"},
            )
        )

    for mem in curated_memories:
        ans = getattr(mem, "ideal_response", None) or (mem.get("ideal_response") if isinstance(mem, dict) else "")
        q = getattr(mem, "user_query", None) or (mem.get("user_query") if isinstance(mem, dict) else "")
        cat = str(getattr(mem, "category", "") or (mem.get("category", "") if isinstance(mem, dict) else "")).lower()
        k = str(getattr(mem, "knowledge_kind", "") or (mem.get("knowledge_kind", "") if isinstance(mem, dict) else "")).lower()

        content = f"[{cat}] {q}: {ans}" if q and ans else (ans or q or str(mem))
        content = content.strip()
        if not content:
            continue

        if k in ("behaviour_rule", "behavior_rule", "behavior", "behaviour") or cat in ("tone", "behaviour", "behavior", "rule"):
            rules.append(content)
            kind = KnowledgeKind.behaviour_rule
        elif k in ("style_example", "style", "response_guidance") or cat in ("example", "style", "dialogue", "few_shot"):
            examples.append(content)
            kind = KnowledgeKind.style_example
        else:
            facts.append(content)
            kind = KnowledgeKind.durable_fact

        mem_prov_id = getattr(mem, "provider_id", None) if not isinstance(mem, dict) else mem.get("provider_id")
        items.append(
            KnowledgeItem(
                scope=KnowledgeScope(
                    tenant_id=tenant_id,
                    provider_id=mem_prov_id,
                    is_tenant_shared=(mem_prov_id is None),
                ),
                kind=kind,
                text=content,
                authority=Authority.explicit_provider_instruction,
                metadata={"source": "legacy_curated_memory"},
            )
        )

    return RetrievalResult(
        facts=facts,
        behavioural_rules=rules,
        examples=examples,
        items=items,
        metadata={"source": "legacy", "is_canary": False},
    )


class ShadowEvaluator:
    """Evaluates Graphiti retrieval against legacy knowledge and resolves canary routing."""

    def is_canary_active(self, tenant_id: int, provider_id: Optional[int] = None) -> bool:
        """Helper to determine whether canary retrieval is active."""
        return is_canary_active(tenant_id, provider_id)

    def evaluate_and_resolve(
        self,
        db: Optional[Session],
        tenant_id: int,
        provider_id: Optional[int],
        message_text: str,
        legacy_knowledge: Dict[str, Any],
        legacy_latency_ms: float = 0.0,
    ) -> Tuple[RetrievalResult, Dict[str, Any]]:
        """Execute shadow comparison and resolve active retrieval result.

        1. Determines canary status (Spec 64).
        2. Assembles legacy items as a RetrievalResult baseline.
        3. Executes Graphiti retrieval if shadow read or canary is enabled (Spec 62).
        4. Calculates privacy-safe evaluation metrics (Spec 63, 88).
        5. Logs evaluation metrics via low-cardinality structured logging (Spec 89).
        6. Resolves active result: Graphiti for canary scopes (with safe legacy fallback on error),
           or legacy baseline for non-canary scopes (Spec 64, 65).
        """
        canary = self.is_canary_active(tenant_id, provider_id)
        legacy_result = build_legacy_retrieval_result(legacy_knowledge, tenant_id, provider_id)

        legacy_shared = legacy_knowledge.get("shared_entries") or legacy_knowledge.get("shared_knowledge") or []
        legacy_provider = legacy_knowledge.get("provider_entries") or legacy_knowledge.get("provider_knowledge") or []
        legacy_memories = legacy_knowledge.get("curated_memories") or []
        legacy_items_count = len(legacy_shared) + len(legacy_provider) + len(legacy_memories)

        should_query_graph = (
            getattr(settings, "GRAPH_SHADOW_READ", True)
            or getattr(settings, "GRAPH_KNOWLEDGE_ENABLED", False)
            or canary
        )

        graphiti_result: Optional[RetrievalResult] = None
        graphiti_latency_ms = 0.0
        graph_error: Optional[str] = None
        cache_hit = False

        if should_query_graph:
            t0 = time.perf_counter()
            try:
                query_obj = RetrievalQuery(
                    tenant_id=tenant_id,
                    provider_id=provider_id,
                    query=message_text,
                )
                graphiti_result = knowledge_gateway.retrieve(query_obj, db=db)
                cache_hit = bool(graphiti_result.metadata.get("cache_hit", False))
                if graphiti_result.metadata.get("error"):
                    graph_error = str(graphiti_result.metadata.get("error"))
            except Exception as exc:
                graph_error = str(type(exc).__name__)
                logger.warning(
                    "Graphiti retrieval error during shadow evaluation: %s (tenant_id=%s)",
                    type(exc).__name__,
                    tenant_id,
                )
            graphiti_latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        if graphiti_result is None:
            graphiti_result = RetrievalResult(
                facts=[],
                behavioural_rules=[],
                examples=[],
                items=[],
                metadata={"error": graph_error or "not_retrieved", "cache_hit": False},
            )

        graphiti_items_count = (
            len(graphiti_result.facts)
            + len(graphiti_result.behavioural_rules)
            + len(graphiti_result.examples)
        )

        overlap = compute_overlap_ratio(legacy_result, graphiti_result)

        rollout_mode = resolve_rollout_mode(tenant_id, provider_id)

        metrics: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "provider_id": provider_id,
            "rollout_mode": rollout_mode,
            "legacy_items_count": legacy_items_count,
            "graphiti_items_count": graphiti_items_count,
            "overlap_ratio": overlap,
            "legacy_latency_ms": round(float(legacy_latency_ms), 2),
            "graphiti_latency_ms": graphiti_latency_ms,
            "cache_hit": cache_hit,
            "is_canary": canary,
        }
        if graph_error:
            metrics["graph_error"] = graph_error

        # Spec 89: Structured logging - zero customer PII or raw knowledge text in logs
        logger.info(
            "Knowledge shadow evaluation complete: tenant_id=%s provider_id=%s rollout_mode=%s "
            "legacy_items_count=%d graphiti_items_count=%d overlap_ratio=%.4f "
            "graphiti_latency_ms=%.2f legacy_latency_ms=%.2f cache_hit=%s is_canary=%s",
            tenant_id,
            provider_id,
            rollout_mode,
            legacy_items_count,
            graphiti_items_count,
            overlap,
            graphiti_latency_ms,
            metrics["legacy_latency_ms"],
            cache_hit,
            canary,
        )

        # Spec 64 & 65: Routing decision
        if canary:
            # If Graphiti retrieval succeeded (no fatal error), route to Graphiti result
            if not graph_error:
                active_result = graphiti_result
            else:
                # Safe degradation to legacy baseline (Spec 66)
                metrics["fallback_to_legacy"] = True
                active_result = legacy_result
                logger.warning(
                    "Canary retrieval degraded to legacy baseline: tenant_id=%s provider_id=%s",
                    tenant_id,
                    provider_id,
                )
        else:
            active_result = legacy_result

        if hasattr(active_result, "metadata") and isinstance(active_result.metadata, dict):
            active_result.metadata["rollout_mode"] = rollout_mode

        return active_result, metrics


shadow_evaluator = ShadowEvaluator()
