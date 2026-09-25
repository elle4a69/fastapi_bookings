"""Knowledge subsystem package.

Exports core gateway, domain models, and scope definitions for Graphiti
and knowledge retrieval.
"""

from app.services.knowledge.types import (
    Authority,
    CuratorAction,
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
    get_cached_provider_profile,
    get_composite_epoch,
    get_provider_epoch,
    get_tenant_epoch,
    hash_query,
    increment_provider_epoch,
    increment_tenant_epoch,
    set_cached_knowledge,
    set_cached_provider_profile,
)
from app.services.knowledge.graphiti_client import (
    format_group_id,
    get_graphiti_client,
    get_neo4j_driver,
    ping_neo4j,
    resolve_query_group_ids,
)
from app.services.knowledge.retrieval import (
    BoundedKnowledgeRetriever,
    retrieve_behaviour,
    retrieve_bounded_knowledge,
    retrieve_examples,
    retrieve_facts,
)
from app.services.knowledge.gateway import (
    KnowledgeGateway,
    knowledge_gateway,
)
from app.services.knowledge.curator import (
    CuratorDecision,
    UnifiedCurator,
    unified_curator,
)
from app.services.knowledge.curator_worker import (
    CuratorWorker,
    process_pending_learning_events_worker,
    start_curator_worker_loop,
)
from app.services.knowledge.projection_service import (
    EdgeType,
    EntityConcept,
    ONTOLOGY_EDGE_TYPES,
    ONTOLOGY_ENTITY_CONCEPTS,
    ONTOLOGY_ENTITY_TYPES,
    ProjectionService,
    projection_service,
)
from app.services.knowledge.projection_worker import (
    ProjectionWorker,
    process_pending_projections_worker,
    start_projection_worker_loop,
)
from app.services.knowledge.rebuild import (
    KnowledgeRebuildService,
    knowledge_rebuild_service,
)
from app.services.knowledge.shadow_evaluator import (
    ShadowEvaluator,
    is_canary_active,
    resolve_rollout_mode,
    shadow_evaluator,
)

__all__ = [
    "Authority",
    "CuratorAction",
    "KnowledgeItem",
    "KnowledgeKind",
    "KnowledgeScope",
    "RetrievalQuery",
    "RetrievalResult",
    "is_dynamic_operational_data",
    "is_system_safety_violation",
    "validate_scope",
    "build_cache_key",
    "get_tenant_epoch",
    "get_provider_epoch",
    "get_composite_epoch",
    "increment_tenant_epoch",
    "increment_provider_epoch",
    "get_cached_knowledge",
    "set_cached_knowledge",
    "get_cached_provider_profile",
    "set_cached_provider_profile",
    "hash_query",
    "format_group_id",
    "resolve_query_group_ids",
    "BoundedKnowledgeRetriever",
    "retrieve_facts",
    "retrieve_behaviour",
    "retrieve_examples",
    "retrieve_bounded_knowledge",
    "get_neo4j_driver",
    "ping_neo4j",
    "get_graphiti_client",
    "KnowledgeGateway",
    "knowledge_gateway",
    "CuratorDecision",
    "UnifiedCurator",
    "unified_curator",
    "CuratorWorker",
    "process_pending_learning_events_worker",
    "start_curator_worker_loop",
    "EntityConcept",
    "EdgeType",
    "ONTOLOGY_ENTITY_CONCEPTS",
    "ONTOLOGY_EDGE_TYPES",
    "ONTOLOGY_ENTITY_TYPES",
    "ProjectionService",
    "projection_service",
    "ProjectionWorker",
    "process_pending_projections_worker",
    "start_projection_worker_loop",
    "KnowledgeRebuildService",
    "knowledge_rebuild_service",
    "ShadowEvaluator",
    "shadow_evaluator",
    "is_canary_active",
    "resolve_rollout_mode",
]

