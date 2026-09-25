"""Knowledge Gateway interface.

The KnowledgeGateway provides a unified, isolated boundary for knowledge retrieval,
publication, invalidation, and caching.

Spec references: Sections 6, 7, 34, 35, 36, 46, 47, 48, 49, 50, 66, 96, 97, 98.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.knowledge.types import (
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
    build_cache_key,
    get_cached_knowledge,
    get_composite_epoch,
    get_provider_epoch,
    get_tenant_epoch,
    hash_query,
    increment_provider_epoch,
    increment_tenant_epoch,
    set_cached_knowledge,
)
from app.services.knowledge.graphiti_client import (
    get_graphiti_client,
    resolve_query_group_ids,
)
from app.services.knowledge.retrieval import (
    retrieve_bounded_knowledge,
    retrieve_facts,
    retrieve_behaviour,
    retrieve_examples,
)

logger = logging.getLogger(__name__)


class KnowledgeGateway:
    """Gateway service orchestrating knowledge caching, scope resolution, and bounded retrieval."""

    def retrieve(
        self,
        query: RetrievalQuery,
        db: Optional[Session] = None,
    ) -> RetrievalResult:
        """Retrieve relevant knowledge for a given tenant/provider scope.

        1. Validates scope parameters and safety.
        2. Resolves current composite epoch for multi-tenant and provider boundaries.
        3. Checks Redis cache using current epoch and query hash (Specs 49, 50, 97).
        4. If cache miss, queries bounded channels with safe PostgreSQL fallback (Specs 47, 48, 66, 96).
        5. Caches retrieved results before returning.
        """
        # Validate query safety and scope
        if query.tenant_id <= 0:
            logger.warning("Invalid tenant_id in RetrievalQuery: %s", query.tenant_id)
            return RetrievalResult(metadata={"error": "invalid_tenant_id", "cache_hit": False})

        if is_system_safety_violation(query.query):
            logger.warning("Safety violation detected in knowledge query: %s", query.query)
            return RetrievalResult(metadata={"safety_violation": True, "cache_hit": False})

        # Resolve current cache epoch (composite epoch cascades tenant invalidation to provider queries)
        epoch = get_composite_epoch(query.tenant_id, query.provider_id)

        # Generate query hash and cache key
        kind_strings = [k.value for k in query.kinds] if query.kinds else None
        q_hash = hash_query(query.query, kind_strings)
        cache_key = build_cache_key(query.tenant_id, query.provider_id, epoch, q_hash)

        # 1. Check Redis Cache
        cached_data = None
        try:
            cached_data = get_cached_knowledge(cache_key)
        except Exception as exc:
            logger.warning("Cache access error: %s", exc)

        if cached_data is not None:
            try:
                cached_data.setdefault("metadata", {})["cache_hit"] = True
                return RetrievalResult.model_validate(cached_data)
            except Exception as exc:
                logger.warning("Failed to parse cached knowledge, regenerating: %s", exc)

        # 2. Execute bounded retrieval channels with safe fallback
        result = retrieve_bounded_knowledge(query, db=db)
        result.metadata["epoch"] = epoch
        result.metadata["cache_hit"] = False

        # 3. Store into cache
        try:
            set_cached_knowledge(cache_key, result.model_dump(mode="json"))
        except Exception as exc:
            logger.warning("Cache set error: %s", exc)
        return result

    def retrieve_facts(
        self,
        query: Union[RetrievalQuery, str],
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        db: Optional[Session] = None,
        limit: Optional[int] = None,
        as_strings: bool = False,
    ) -> Union[List[KnowledgeItem], List[str]]:
        """Retrieve bounded factual knowledge items (Spec 47, 48)."""
        return retrieve_facts(
            query=query,
            tenant_id=tenant_id,
            provider_id=provider_id,
            db=db,
            limit=limit,
            as_strings=as_strings,
        )

    def retrieve_behaviour(
        self,
        query: Union[RetrievalQuery, str],
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        db: Optional[Session] = None,
        limit: Optional[int] = None,
        as_strings: bool = False,
    ) -> Union[List[KnowledgeItem], List[str]]:
        """Retrieve bounded behavioural guidance items (Spec 47, 48)."""
        return retrieve_behaviour(
            query=query,
            tenant_id=tenant_id,
            provider_id=provider_id,
            db=db,
            limit=limit,
            as_strings=as_strings,
        )

    def retrieve_examples(
        self,
        query: Union[RetrievalQuery, str],
        tenant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        db: Optional[Session] = None,
        limit: Optional[int] = None,
        as_strings: bool = False,
    ) -> Union[List[KnowledgeItem], List[str]]:
        """Retrieve bounded style examples and guidance (Spec 47, 48)."""
        return retrieve_examples(
            query=query,
            tenant_id=tenant_id,
            provider_id=provider_id,
            db=db,
            limit=limit,
            as_strings=as_strings,
        )

    def publish(self, item: KnowledgeItem) -> bool:
        """Stage or ingest a knowledge item into Graphiti.

        Rejects dynamic operational data (Spec 19) or safety violations.
        """
        # 1. Policy checks
        if is_dynamic_operational_data(item.text):
            logger.info("Rejected dynamic operational data from knowledge ingestion: %s", item.text[:50])
            return False

        if is_system_safety_violation(item.text):
            logger.warning("Rejected safety violation from knowledge ingestion: %s", item.text[:50])
            return False

        # 2. Check feature flags
        is_write_active = settings.GRAPH_KNOWLEDGE_ENABLED or settings.GRAPH_SHADOW_WRITE
        if not is_write_active:
            logger.debug("Graph write skipped (GRAPH_KNOWLEDGE_ENABLED and GRAPH_SHADOW_WRITE are false)")
            # Invalidate cache so any updated local representations are purged
            self.invalidate(item.scope.tenant_id, item.scope.provider_id)
            return True

        # 3. Graphiti ingestion
        client = get_graphiti_client()
        if client is not None:
            try:
                # Add episode if available
                add_ep = getattr(client, "add_episode", None)
                if add_ep is not None:
                    import asyncio
                    import inspect
                    if inspect.iscoroutinefunction(add_ep):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                                    pool.submit(
                                        lambda: asyncio.run(
                                            client.add_episode(
                                                name=f"item_{item.kind.value}",
                                                episode_body=item.text,
                                                group_id=item.scope.group_id,
                                            )
                                        )
                                    ).result(timeout=5.0)
                            else:
                                loop.run_until_complete(
                                    client.add_episode(
                                        name=f"item_{item.kind.value}",
                                        episode_body=item.text,
                                        group_id=item.scope.group_id,
                                    )
                                )
                        except Exception as exc:
                            logger.warning("Graphiti add_episode failed: %s", exc)
            except Exception as exc:
                logger.error("Failed to publish item to Graphiti: %s", exc)

        # 4. Invalidate cache epoch
        self.invalidate(item.scope.tenant_id, item.scope.provider_id)
        return True

    def invalidate(self, tenant_id: int, provider_id: Optional[int] = None) -> int:
        """Invalidate cache for a tenant and optional provider by bumping the epoch."""
        if provider_id is not None:
            new_epoch = increment_provider_epoch(tenant_id, provider_id)
        else:
            new_epoch = increment_tenant_epoch(tenant_id)
        logger.debug("Invalidated knowledge cache: tenant_id=%s, provider_id=%s -> new_epoch=%s", tenant_id, provider_id, new_epoch)
        return new_epoch

    def rebuild(self, tenant_id: int, provider_id: Optional[int] = None) -> Dict[str, Any]:
        """Administrative rebuild trigger for graph indices and cached views (Spec 50)."""
        logger.info("Initiating knowledge rebuild for tenant_id=%s, provider_id=%s", tenant_id, provider_id)
        new_epoch = self.invalidate(tenant_id, provider_id)
        return {
            "status": "rebuilt",
            "tenant_id": tenant_id,
            "provider_id": provider_id,
            "epoch": new_epoch,
        }


knowledge_gateway = KnowledgeGateway()
