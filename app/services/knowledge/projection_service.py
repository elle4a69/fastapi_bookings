"""Canonical Graphiti graph projection service.

Spec references: Sections 28–36, 67–69.
Builds Graphiti episodes from KnowledgeGraphProjection records with provenance,
ontological concepts, deterministic idempotency, and multi-tenant isolation.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from enum import Enum
import inspect
import json
import logging
from typing import Any, Dict, List, Optional, Type
import uuid

from pydantic import BaseModel, Field

from app.models.curated_memory import CuratedMemory
from app.models.knowledge_projection import KnowledgeGraphProjection, utc_now
from app.models.learning_event import LearningEvent
from app.services.curation.pii_scrubber import scrub_pii
from app.services.knowledge.graphiti_client import format_group_id, get_graphiti_client

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Ontological Concepts (Spec 36)
# -----------------------------------------------------------------------------

class EntityConcept(str, Enum):
    """Entity concept nodes defined in Spec 36."""
    PROVIDER = "Provider"
    TENANT = "Tenant"
    PREFERENCE = "Preference"
    BEHAVIOUR = "Behaviour"
    POLICY = "Policy"
    BOUNDARY = "Boundary"
    EXAMPLE = "Example"


class EdgeType(str, Enum):
    """Edge types connecting ontological entities defined in Spec 36."""
    PREFERS = "PREFERS"
    AVOIDS = "AVOIDS"
    APPLIES_WHEN = "APPLIES_WHEN"
    HAS_BOUNDARY = "HAS_BOUNDARY"
    SUPERSEDES = "SUPERSEDES"
    SUPPORTED_BY = "SUPPORTED_BY"


class ProviderNode(BaseModel):
    name: str
    tenant_id: int
    provider_id: Optional[int] = None


class TenantNode(BaseModel):
    name: str
    tenant_id: int


class PreferenceNode(BaseModel):
    description: str


class BehaviourNode(BaseModel):
    rule: str


class PolicyNode(BaseModel):
    statement: str


class BoundaryNode(BaseModel):
    rule: str


class ExampleNode(BaseModel):
    dialogue: str


ONTOLOGY_ENTITY_CONCEPTS: List[str] = [c.value for c in EntityConcept]
ONTOLOGY_EDGE_TYPES: List[str] = [e.value for e in EdgeType]

ONTOLOGY_ENTITY_TYPES: Dict[str, Type[BaseModel]] = {
    EntityConcept.PROVIDER.value: ProviderNode,
    EntityConcept.TENANT.value: TenantNode,
    EntityConcept.PREFERENCE.value: PreferenceNode,
    EntityConcept.BEHAVIOUR.value: BehaviourNode,
    EntityConcept.POLICY.value: PolicyNode,
    EntityConcept.BOUNDARY.value: BoundaryNode,
    EntityConcept.EXAMPLE.value: ExampleNode,
}


# -----------------------------------------------------------------------------
# Projection Service (Specs 28–36)
# -----------------------------------------------------------------------------

class ProjectionService:
    """Canonical graph projection service bridging PostgreSQL records to Graphiti/Neo4j."""

    @staticmethod
    def compute_episode_uuid(projection: KnowledgeGraphProjection) -> str:
        """Compute deterministic UUIDv5 for projection episode.

        Spec 32: Ensures idempotent synchronization with Graphiti so re-processing
        the exact same projection updates the existing episode rather than creating
        duplicate graph entities.
        """
        canonical_key = (
            f"tenant:{projection.tenant_id}:"
            f"prov:{projection.provider_id}:"
            f"type:{projection.projection_type}:"
            f"cm:{projection.curated_memory_id}:"
            f"le:{projection.learning_event_id}"
        )
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, canonical_key))

    def build_episode_name(
        self,
        projection: KnowledgeGraphProjection,
        memory: Optional[CuratedMemory] = None,
        event: Optional[LearningEvent] = None,
    ) -> str:
        """Build human-readable summary name for the Graphiti episode.

        Format: "[Fact] provider:Tori - parking situation" or "[Behaviour] provider:1 - tone"
        """
        # 1. Kind prefix
        if projection.projection_type in ("behavioural_rule", "behavioural_guidance", "behaviour_rule"):
            kind_prefix = "Behaviour"
        elif projection.projection_type in ("fact", "explicit_fact", "upsert_fact", "supersede_fact"):
            kind_prefix = "Fact"
        elif memory and getattr(memory, "canonical_rule", None):
            kind_prefix = "Behaviour"
        elif memory and getattr(memory, "knowledge_kind", None) in ("fact", "durable_fact"):
            kind_prefix = "Fact"
        else:
            kind_prefix = (projection.projection_type or "Fact").capitalize()

        # 2. Subject actor
        if projection.provider_id is not None:
            prov_name = None
            if projection.provider and getattr(projection.provider, "name", None):
                prov_name = projection.provider.name
            elif memory and getattr(memory, "provider", None) and getattr(memory.provider, "name", None):
                prov_name = memory.provider.name
            actor = f"provider:{prov_name or projection.provider_id}"
        else:
            actor = f"tenant:{projection.tenant_id}"

        # 3. Topic summary
        topic = "general"
        if memory:
            if memory.category:
                topic = memory.category
            elif memory.user_query:
                topic = memory.user_query.strip()[:40]
        elif event:
            if (
                event.metadata_payload
                and isinstance(event.metadata_payload, dict)
                and event.metadata_payload.get("category")
            ):
                topic = event.metadata_payload["category"]
            elif event.customer_message:
                topic = event.customer_message.strip()[:40]

        return f"[{kind_prefix}] {actor} - {topic}"

    def build_episode_body(
        self,
        projection: KnowledgeGraphProjection,
        memory: Optional[CuratedMemory] = None,
        event: Optional[LearningEvent] = None,
    ) -> str:
        """Format textual episode content with customer PII strictly omitted.

        Spec 33 & 35: Privacy boundary enforcement.
        """
        content_parts: List[str] = []
        if memory:
            canonical_rule = getattr(memory, "canonical_rule", None)
            if canonical_rule:
                content_parts.append(f"Behavioural Rule: {canonical_rule}")
            if getattr(memory, "ideal_response", None):
                prefix = "Guidance" if canonical_rule else "Fact"
                content_parts.append(f"{prefix}: {memory.ideal_response}")
            if getattr(memory, "user_query", None):
                content_parts.append(f"Context Query: {memory.user_query}")
            if getattr(memory, "category", None):
                content_parts.append(f"Category: {memory.category}")
        elif event:
            if event.human_content:
                content_parts.append(f"Content: {event.human_content}")
            if event.customer_message:
                content_parts.append(f"Context Query: {event.customer_message}")
        else:
            content_parts.append(f"Projection: {projection.projection_type}")

        raw_body = "\n".join(content_parts)
        return scrub_pii(raw_body)

    def build_source_description(
        self,
        projection: KnowledgeGraphProjection,
        memory: Optional[CuratedMemory] = None,
        event: Optional[LearningEvent] = None,
    ) -> str:
        """Build provenance metadata string for the episode.

        Spec 33: Contains tenant_id, provider_id, learning_event_id,
        curated_memory_id, authority, source, created_at.
        """
        prov_dict = {
            "tenant_id": projection.tenant_id,
            "provider_id": projection.provider_id,
            "learning_event_id": (
                str(projection.learning_event_id)
                if projection.learning_event_id
                else (str(event.id) if event and event.id else None)
            ),
            "curated_memory_id": projection.curated_memory_id or (memory.id if memory else None),
            "authority": getattr(memory, "authority", None) or "curator:2.0",
            "source": getattr(event, "source", None) or "production_messages",
            "created_at": (
                projection.created_at.isoformat()
                if projection.created_at
                else utc_now().isoformat()
            ),
        }
        return json.dumps(prov_dict, sort_keys=True)

    @staticmethod
    def parse_source_description(source_desc: str) -> Dict[str, Any]:
        """Parse provenance metadata from source_description."""
        try:
            return json.loads(source_desc)
        except Exception:
            return {}

    def project_to_graphiti(
        self,
        projection: KnowledgeGraphProjection,
        memory: Optional[CuratedMemory] = None,
        event: Optional[LearningEvent] = None,
        client: Any = None,
    ) -> str:
        """Project a KnowledgeGraphProjection into Graphiti/Neo4j.

        Validates tenant boundaries, constructs the episode payload,
        invokes Graphiti add_episode (or mocked fallback), and returns the episode ID.
        """
        # 1. Tenant boundary validation
        if memory is not None and projection.tenant_id != memory.tenant_id:
            raise ValueError(
                f"Tenant boundary violation: projection tenant {projection.tenant_id} != memory tenant {memory.tenant_id}"
            )
        if event is not None and projection.tenant_id != event.tenant_id:
            raise ValueError(
                f"Tenant boundary violation: projection tenant {projection.tenant_id} != event tenant {event.tenant_id}"
            )

        # 2. Build episode components
        name = self.build_episode_name(projection, memory, event)
        episode_body = self.build_episode_body(projection, memory, event)
        source_description = self.build_source_description(projection, memory, event)
        group_id = format_group_id(projection.tenant_id, projection.provider_id)
        episode_uuid = self.compute_episode_uuid(projection)
        reference_time = projection.created_at or utc_now()

        # 3. Graphiti dispatch
        active_client = client if client is not None else get_graphiti_client()
        if active_client is None:
            logger.info(
                "Graphiti client offline; mock-projecting episode %s for group %s",
                episode_uuid,
                group_id,
            )
            return episode_uuid

        res = active_client.add_episode(
            name=name,
            episode_body=episode_body,
            source_description=source_description,
            reference_time=reference_time,
            group_id=group_id,
            uuid=episode_uuid,
        )

        if inspect.isawaitable(res):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    add_res = executor.submit(asyncio.run, res).result()
            else:
                add_res = asyncio.run(res)
        else:
            add_res = res

        if hasattr(add_res, "episode") and hasattr(add_res.episode, "uuid"):
            return str(add_res.episode.uuid)
        if hasattr(add_res, "uuid"):
            return str(add_res.uuid)
        if isinstance(add_res, str):
            return add_res

        return episode_uuid


projection_service = ProjectionService()
