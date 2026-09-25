"""Bounded Knowledge Retrieval Subsystem and Channel Router.

Spec references: Sections 46, 47, 48, 53, 54, 55, 66, 96.
Implements bounded retrieval channels (Facts, Behaviour, Examples) with
strict multi-tenant/provider isolation and safe PostgreSQL fallback.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy import or_, and_, desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.curated_memory import CuratedMemory
from app.models.sms_knowledge import SmsKnowledgeEntry
from app.services.knowledge.types import (
    Authority,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeScope,
    RetrievalQuery,
    RetrievalResult,
)
from app.services.knowledge.policy import (
    is_dynamic_operational_data,
    is_system_safety_violation,
    validate_scope,
)
from app.services.knowledge.cache import (
    get_composite_epoch,
)
from app.services.knowledge.graphiti_client import (
    get_graphiti_client,
    resolve_query_group_ids,
)

logger = logging.getLogger(__name__)

# Channel Kinds definition according to Master Spec 47 & 48
FACT_KINDS: Set[KnowledgeKind] = {
    KnowledgeKind.durable_fact,
    KnowledgeKind.policy_guidance,
    KnowledgeKind.preference,
    KnowledgeKind.boundary,
}

BEHAVIOUR_KINDS: Set[KnowledgeKind] = {
    KnowledgeKind.behaviour_rule,
}

EXAMPLE_KINDS: Set[KnowledgeKind] = {
    KnowledgeKind.style_example,
    KnowledgeKind.response_guidance,
}


def _normalize_query(
    query: Union[RetrievalQuery, str],
    tenant_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> RetrievalQuery:
    """Normalize input query to RetrievalQuery model."""
    if isinstance(query, RetrievalQuery):
        return query
    if tenant_id is None:
        raise ValueError("tenant_id is required when query is a string")
    return RetrievalQuery(
        tenant_id=tenant_id,
        provider_id=provider_id,
        query=query,
        limit=limit or 10,
    )


def _compute_relevance_score(
    text: str,
    query_tokens: List[str],
    is_provider_specific: bool = False,
) -> int:
    """Score text relevance against query tokens (Spec 96)."""
    if not query_tokens:
        return 1 if is_provider_specific else 0

    lower_text = text.lower()
    score = 0
    for token in query_tokens:
        if token in lower_text:
            score += 10

    if is_provider_specific:
        score += 2  # Provider-specific knowledge prioritised over shared

    return score


class BoundedKnowledgeRetriever:
    """Orchestrates bounded multi-channel retrieval with safe PostgreSQL fallback."""

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def retrieve_facts(
        self,
        query: Union[RetrievalQuery, str],
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        db: Optional[Session] = None,
        limit: Optional[int] = None,
        as_strings: bool = False,
    ) -> Union[List[KnowledgeItem], List[str]]:
        """Retrieve bounded factual knowledge items (Spec 47, 48).

        Channel 1: Factual knowledge (durable_fact, policy_guidance, preference, boundary)
        bounded strictly by KNOWLEDGE_FACTS_LIMIT.
        """
        norm_query = _normalize_query(query, tenant_id, provider_id, limit)
        max_limit = min(
            limit or settings.KNOWLEDGE_FACTS_LIMIT,
            settings.KNOWLEDGE_FACTS_LIMIT,
        )
        items = self._retrieve_channel(
            query=norm_query,
            target_kinds=FACT_KINDS,
            channel_limit=max_limit,
            db=db or self._db,
        )
        if as_strings:
            return [item.text for item in items]
        return items

    def retrieve_behaviour(
        self,
        query: Union[RetrievalQuery, str],
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        db: Optional[Session] = None,
        limit: Optional[int] = None,
        as_strings: bool = False,
    ) -> Union[List[KnowledgeItem], List[str]]:
        """Retrieve bounded behavioural guidance items (Spec 47, 48).

        Channel 2: Behavioural guidance (behaviour_rule)
        bounded strictly by KNOWLEDGE_BEHAVIOUR_LIMIT.
        """
        norm_query = _normalize_query(query, tenant_id, provider_id, limit)
        max_limit = min(
            limit or settings.KNOWLEDGE_BEHAVIOUR_LIMIT,
            settings.KNOWLEDGE_BEHAVIOUR_LIMIT,
        )
        items = self._retrieve_channel(
            query=norm_query,
            target_kinds=BEHAVIOUR_KINDS,
            channel_limit=max_limit,
            db=db or self._db,
        )
        if as_strings:
            return [item.text for item in items]
        return items

    def retrieve_examples(
        self,
        query: Union[RetrievalQuery, str],
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        db: Optional[Session] = None,
        limit: Optional[int] = None,
        as_strings: bool = False,
    ) -> Union[List[KnowledgeItem], List[str]]:
        """Retrieve bounded style examples and guidance (Spec 47, 48).

        Channel 3: Style examples (style_example, response_guidance)
        bounded strictly by KNOWLEDGE_EXAMPLES_LIMIT.
        """
        norm_query = _normalize_query(query, tenant_id, provider_id, limit)
        max_limit = min(
            limit or settings.KNOWLEDGE_EXAMPLES_LIMIT,
            settings.KNOWLEDGE_EXAMPLES_LIMIT,
        )
        items = self._retrieve_channel(
            query=norm_query,
            target_kinds=EXAMPLE_KINDS,
            channel_limit=max_limit,
            db=db or self._db,
        )
        if as_strings:
            return [item.text for item in items]
        return items

    def retrieve_all_channels(
        self,
        query: Union[RetrievalQuery, str],
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> RetrievalResult:
        """Execute bounded retrieval across all 3 channels and return structured RetrievalResult."""
        norm_query = _normalize_query(query, tenant_id, provider_id)
        effective_db = db or self._db

        # Safety & Scope checks
        if norm_query.tenant_id <= 0:
            logger.warning("Invalid tenant_id in RetrievalQuery: %s", norm_query.tenant_id)
            return RetrievalResult(metadata={"error": "invalid_tenant_id", "cache_hit": False})

        if is_system_safety_violation(norm_query.query):
            logger.warning("Safety violation detected in knowledge query: %s", norm_query.query)
            return RetrievalResult(metadata={"safety_violation": True, "cache_hit": False})

        # 1. Attempt Graphiti retrieval if enabled (Spec 46)
        source = "fallback"
        from app.services.knowledge.shadow_evaluator import is_canary_active, resolve_rollout_mode
        rollout_mode = resolve_rollout_mode(norm_query.tenant_id, norm_query.provider_id)
        group_ids = resolve_query_group_ids(norm_query.tenant_id, norm_query.provider_id)
        is_graph_active = (
            bool(settings.GRAPH_KNOWLEDGE_ENABLED)
            or bool(settings.GRAPH_SHADOW_READ)
            or is_canary_active(norm_query.tenant_id, norm_query.provider_id)
        )

        graph_facts: List[KnowledgeItem] = []
        graph_behaviour: List[KnowledgeItem] = []
        graph_examples: List[KnowledgeItem] = []

        if is_graph_active:
            try:
                g_facts, g_behaviour, g_examples = self._retrieve_from_graphiti(norm_query, group_ids)
                if g_facts or g_behaviour or g_examples:
                    graph_facts = g_facts[:settings.KNOWLEDGE_FACTS_LIMIT]
                    graph_behaviour = g_behaviour[:settings.KNOWLEDGE_BEHAVIOUR_LIMIT]
                    graph_examples = g_examples[:settings.KNOWLEDGE_EXAMPLES_LIMIT]
                    source = "graphiti"
            except Exception as exc:
                logger.warning("Graphiti search failed, activating safe fallback: %s", exc)

        # 2. If Graphiti did not produce results, execute safe fallback path (Spec 66)
        if not (graph_facts or graph_behaviour or graph_examples):
            source = "fallback"
            fact_items = self.retrieve_facts(norm_query, db=effective_db, limit=settings.KNOWLEDGE_FACTS_LIMIT)
            behaviour_items = self.retrieve_behaviour(norm_query, db=effective_db, limit=settings.KNOWLEDGE_BEHAVIOUR_LIMIT)
            example_items = self.retrieve_examples(norm_query, db=effective_db, limit=settings.KNOWLEDGE_EXAMPLES_LIMIT)
        else:
            fact_items = graph_facts
            behaviour_items = graph_behaviour
            example_items = graph_examples

        epoch = get_composite_epoch(norm_query.tenant_id, norm_query.provider_id)
        all_items: List[KnowledgeItem] = list(fact_items) + list(behaviour_items) + list(example_items)

        # Telemetry: structured logging distinguishing rollout mode without raw query text or PII
        logger.info(
            "Knowledge retrieval complete: tenant_id=%s provider_id=%s source=%s rollout_mode=%s "
            "facts_count=%d behaviour_count=%d examples_count=%d cache_hit=%s",
            norm_query.tenant_id,
            norm_query.provider_id,
            source,
            rollout_mode,
            len(fact_items),
            len(behaviour_items),
            len(example_items),
            False,
        )

        return RetrievalResult(
            facts=[item.text for item in fact_items],
            behavioural_rules=[item.text for item in behaviour_items],
            examples=[item.text for item in example_items],
            items=all_items,
            metadata={
                "source": source,
                "rollout_mode": rollout_mode,
                "epoch": epoch,
                "group_ids": group_ids,
                "cache_hit": False,
                "enabled": bool(settings.GRAPH_KNOWLEDGE_ENABLED),
                "shadow_read": bool(settings.GRAPH_SHADOW_READ),
                "facts_count": len(fact_items),
                "behaviour_count": len(behaviour_items),
                "examples_count": len(example_items),
            },
        )

    def _retrieve_channel(
        self,
        query: RetrievalQuery,
        target_kinds: Set[KnowledgeKind],
        channel_limit: int,
        db: Optional[Session] = None,
    ) -> List[KnowledgeItem]:
        """Internal worker fetching bounded items for a specific kind set via safe fallback."""
        if db is not None:
            return self._query_database_fallback(query, target_kinds, channel_limit, db)
        else:
            with SessionLocal() as session:
                return self._query_database_fallback(query, target_kinds, channel_limit, session)

    def _query_database_fallback(
        self,
        query: RetrievalQuery,
        target_kinds: Set[KnowledgeKind],
        channel_limit: int,
        session: Session,
    ) -> List[KnowledgeItem]:
        """Query PostgreSQL CuratedMemory and approved SmsKnowledgeEntry with strict multi-tenant isolation (Spec 66)."""
        now = datetime.now(timezone.utc)
        query_tokens = [w.lower() for w in re.findall(r"\w+", query.query) if len(w) >= 3]

        candidates: List[Tuple[int, KnowledgeItem]] = []

        # -----------------------------------------------------------------
        # 1. Query PostgreSQL CuratedMemory
        # -----------------------------------------------------------------
        cm_query = session.query(CuratedMemory).filter(
            CuratedMemory.tenant_id == query.tenant_id,
            CuratedMemory.status == "active",
            or_(
                CuratedMemory.effective_until.is_(None),
                CuratedMemory.effective_until > now,
            ),
        )

        if query.provider_id is not None:
            cm_query = cm_query.filter(
                or_(
                    CuratedMemory.provider_id == query.provider_id,
                    CuratedMemory.provider_id.is_(None),
                )
            )
        else:
            cm_query = cm_query.filter(CuratedMemory.provider_id.is_(None))

        active_memories = cm_query.order_by(desc(CuratedMemory.id)).all()

        for mem in active_memories:
            user_q = (mem.user_query or "").strip()
            ideal_ans = (mem.ideal_response or "").strip()
            full_text = f"{user_q} {ideal_ans}".strip()

            # Dynamic operational data and safety guards (Spec 19, 58)
            if is_dynamic_operational_data(full_text) or is_system_safety_violation(full_text):
                continue

            # Classify kind
            kind = self._resolve_memory_kind(mem)
            if kind not in target_kinds:
                continue

            text = ideal_ans if ideal_ans else user_q
            is_prov = (mem.provider_id is not None and mem.provider_id == query.provider_id)
            score = _compute_relevance_score(f"{user_q} {ideal_ans} {mem.category}", query_tokens, is_prov)

            item = KnowledgeItem(
                id=f"cm_{mem.id}",
                scope=KnowledgeScope(
                    tenant_id=mem.tenant_id,
                    provider_id=mem.provider_id,
                    is_tenant_shared=(mem.provider_id is None),
                ),
                kind=kind,
                text=text,
                authority=self._resolve_authority(mem.authority),
                metadata={
                    "source": "curated_memory",
                    "id": mem.id,
                    "category": mem.category,
                    "confidence_score": getattr(mem, "confidence_score", 1.0),
                },
                created_at=mem.created_at or now,
            )
            candidates.append((score, item))

        # -----------------------------------------------------------------
        # 2. Query PostgreSQL SmsKnowledgeEntry (approved status)
        # -----------------------------------------------------------------
        ske_query = session.query(SmsKnowledgeEntry).filter(
            SmsKnowledgeEntry.tenant_id == query.tenant_id,
            SmsKnowledgeEntry.status == "approved",
        )

        if query.provider_id is not None:
            ske_query = ske_query.filter(
                or_(
                    SmsKnowledgeEntry.provider_id == query.provider_id,
                    SmsKnowledgeEntry.provider_id.is_(None),
                )
            )
        else:
            ske_query = ske_query.filter(SmsKnowledgeEntry.provider_id.is_(None))

        active_entries = ske_query.order_by(desc(SmsKnowledgeEntry.id)).all()

        for entry in active_entries:
            text = (entry.text or "").strip()
            if not text:
                continue
            if is_dynamic_operational_data(text) or is_system_safety_violation(text):
                continue

            kind = self._resolve_entry_kind(entry)
            if kind not in target_kinds:
                continue

            is_prov = (entry.provider_id is not None and entry.provider_id == query.provider_id)
            score = _compute_relevance_score(f"{text} {entry.category}", query_tokens, is_prov)

            item = KnowledgeItem(
                id=f"ske_{entry.id}",
                scope=KnowledgeScope(
                    tenant_id=entry.tenant_id,
                    provider_id=entry.provider_id,
                    is_tenant_shared=(entry.provider_id is None),
                ),
                kind=kind,
                text=text,
                authority=Authority.system_import,
                metadata={
                    "source": "sms_knowledge_entry",
                    "id": entry.id,
                    "category": entry.category,
                },
                created_at=getattr(entry, "created_at", now) or now,
            )
            candidates.append((score, item))

        # -----------------------------------------------------------------
        # 3. Sort by relevance score descending, then recency
        # -----------------------------------------------------------------
        candidates.sort(key=lambda x: (x[0], x[1].created_at), reverse=True)

        bounded_items = [c[1] for c in candidates[:channel_limit]]
        return bounded_items

    def _retrieve_from_graphiti(
        self,
        query: RetrievalQuery,
        group_ids: List[str],
    ) -> Tuple[List[KnowledgeItem], List[KnowledgeItem], List[KnowledgeItem]]:
        """Query Graphiti client and categorize results into 3 channels."""
        client = get_graphiti_client()
        if client is None:
            return [], [], []

        facts: List[KnowledgeItem] = []
        behaviour: List[KnowledgeItem] = []
        examples: List[KnowledgeItem] = []

        import asyncio
        import inspect

        search_fn = getattr(client, "search", None)
        if search_fn is None:
            return [], [], []

        edges = []
        total_limit = (
            settings.KNOWLEDGE_FACTS_LIMIT
            + settings.KNOWLEDGE_BEHAVIOUR_LIMIT
            + settings.KNOWLEDGE_EXAMPLES_LIMIT
        )

        if inspect.iscoroutinefunction(search_fn):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        edges = pool.submit(
                            lambda: asyncio.run(
                                client.search(
                                    query=query.query,
                                    group_ids=group_ids,
                                    num_results=total_limit,
                                )
                            )
                        ).result(timeout=5.0)
                else:
                    edges = loop.run_until_complete(
                        client.search(
                            query=query.query,
                            group_ids=group_ids,
                            num_results=total_limit,
                        )
                    )
            except Exception as err:
                logger.warning("Graphiti search coroutine failed: %s", err)
                return [], [], []
        else:
            edges = client.search(
                query=query.query,
                group_ids=group_ids,
                num_results=total_limit,
            )

        for edge in (edges or []):
            fact_str = getattr(edge, "fact", str(edge))
            # Determine kind
            edge_type = str(getattr(edge, "type", "")).lower()
            name = str(getattr(edge, "name", "")).lower()

            if any(k in edge_type or k in name for k in ("behaviour", "behavior", "rule", "instruction")):
                kind = KnowledgeKind.behaviour_rule
                target_list = behaviour
            elif any(k in edge_type or k in name for k in ("example", "style", "guidance")):
                kind = KnowledgeKind.style_example
                target_list = examples
            else:
                kind = KnowledgeKind.durable_fact
                target_list = facts

            item = KnowledgeItem(
                scope=KnowledgeScope(
                    tenant_id=query.tenant_id,
                    provider_id=query.provider_id,
                    is_tenant_shared=(query.provider_id is None),
                ),
                kind=kind,
                text=fact_str,
                authority=Authority.explicit_provider_instruction,
                metadata={"source": "graphiti"},
            )
            target_list.append(item)

        return facts, behaviour, examples

    @staticmethod
    def _resolve_memory_kind(mem: CuratedMemory) -> KnowledgeKind:
        """Resolve memory kind with priority on explicit knowledge_kind."""
        k = (mem.knowledge_kind or "").strip().lower()
        if k in ("behaviour_rule", "behavior_rule", "behavior", "behaviour"):
            return KnowledgeKind.behaviour_rule
        if k in ("style_example", "style"):
            return KnowledgeKind.style_example
        if k in ("response_guidance", "guidance"):
            cat = (mem.category or "").strip().lower()
            if cat in ("tone", "behaviour", "behavior", "rule"):
                return KnowledgeKind.behaviour_rule
            return KnowledgeKind.response_guidance
        if k in ("policy_guidance", "policy"):
            return KnowledgeKind.policy_guidance
        if k in ("preference",):
            return KnowledgeKind.preference
        if k in ("boundary",):
            return KnowledgeKind.boundary
        if k in ("durable_fact", "fact"):
            return KnowledgeKind.durable_fact

        # Fallback to category
        cat = (mem.category or "").strip().lower()
        if cat in ("tone", "behaviour", "behavior", "guidance", "rule"):
            return KnowledgeKind.behaviour_rule
        if cat in ("style_example", "example", "dialogue", "few_shot"):
            return KnowledgeKind.style_example
        if cat in ("policy",):
            return KnowledgeKind.policy_guidance
        if cat in ("preference",):
            return KnowledgeKind.preference
        if cat in ("boundary",):
            return KnowledgeKind.boundary
        return KnowledgeKind.durable_fact

    @staticmethod
    def _resolve_entry_kind(entry: SmsKnowledgeEntry) -> KnowledgeKind:
        """Resolve entry kind based on SMS entry category."""
        cat = (entry.category or "").strip().lower()
        if cat in ("tone", "behaviour", "behavior", "rule"):
            return KnowledgeKind.behaviour_rule
        if cat in ("example", "style", "few_shot"):
            return KnowledgeKind.style_example
        if cat in ("policy",):
            return KnowledgeKind.policy_guidance
        return KnowledgeKind.durable_fact

    @staticmethod
    def _resolve_authority(auth_str: Optional[str]) -> Authority:
        """Map authority string to Authority enum."""
        if not auth_str:
            return Authority.explicit_provider_instruction
        auth_norm = auth_str.strip().lower()
        for a in Authority:
            if a.value == auth_norm:
                return a
        return Authority.explicit_provider_instruction


# Global retriever instance
default_retriever = BoundedKnowledgeRetriever()


def retrieve_facts(
    query: Union[RetrievalQuery, str],
    tenant_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    db: Optional[Session] = None,
    limit: Optional[int] = None,
    as_strings: bool = False,
) -> Union[List[KnowledgeItem], List[str]]:
    """Retrieve bounded factual knowledge items (Spec 47, 48)."""
    return default_retriever.retrieve_facts(
        query=query,
        tenant_id=tenant_id,
        provider_id=provider_id,
        db=db,
        limit=limit,
        as_strings=as_strings,
    )


def retrieve_behaviour(
    query: Union[RetrievalQuery, str],
    tenant_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    db: Optional[Session] = None,
    limit: Optional[int] = None,
    as_strings: bool = False,
) -> Union[List[KnowledgeItem], List[str]]:
    """Retrieve bounded behavioural guidance items (Spec 47, 48)."""
    return default_retriever.retrieve_behaviour(
        query=query,
        tenant_id=tenant_id,
        provider_id=provider_id,
        db=db,
        limit=limit,
        as_strings=as_strings,
    )


def retrieve_examples(
    query: Union[RetrievalQuery, str],
    tenant_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    db: Optional[Session] = None,
    limit: Optional[int] = None,
    as_strings: bool = False,
) -> Union[List[KnowledgeItem], List[str]]:
    """Retrieve bounded style examples and guidance (Spec 47, 48)."""
    return default_retriever.retrieve_examples(
        query=query,
        tenant_id=tenant_id,
        provider_id=provider_id,
        db=db,
        limit=limit,
        as_strings=as_strings,
    )


def retrieve_bounded_knowledge(
    query: Union[RetrievalQuery, str],
    tenant_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> RetrievalResult:
    """Retrieve bounded knowledge across all 3 channels (Spec 47, 48, 66)."""
    return default_retriever.retrieve_all_channels(
        query=query,
        tenant_id=tenant_id,
        provider_id=provider_id,
        db=db,
    )
