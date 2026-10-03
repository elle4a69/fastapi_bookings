"""Graphiti client and Neo4j driver connection management.

Spec references: Sections 6, 7, 34, 35, 36.
Group ID isolation:
  - Tenant-shared: tenant:{tenant_id}:shared
  - Provider-specific: tenant:{tenant_id}:provider:{provider_id}
"""

from __future__ import annotations

import logging
from typing import List, Optional
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError, Neo4jError

from app.core.config import settings

logger = logging.getLogger(__name__)

_driver: Optional[Driver] = None
_graphiti_instance = None
_indices_initialized: bool = False


def format_group_id(tenant_id: int, provider_id: Optional[int] = None) -> str:
    """Format the canonical Graphiti group ID partition for tenant and optional provider.

    Spec 34:
      - Tenant-shared: tenant:{tenant_id}:shared
      - Provider-specific: tenant:{tenant_id}:provider:{provider_id}
    """
    if provider_id is None:
        return f"tenant:{tenant_id}:shared"
    return f"tenant:{tenant_id}:provider:{provider_id}"


def resolve_query_group_ids(tenant_id: int, provider_id: Optional[int] = None) -> List[str]:
    """Derive list of partition group IDs to query for a tenant/provider context.

    If provider_id is provided, both provider-specific and tenant-shared partitions
    are queried. If provider_id is None, only the tenant-shared partition is queried.
    """
    shared_group = format_group_id(tenant_id, None)
    if provider_id is not None:
        return [format_group_id(tenant_id, provider_id), shared_group]
    return [shared_group]


def get_neo4j_driver() -> Optional[Driver]:
    """Get or create singleton Neo4j driver instance with resilient error handling."""
    global _driver
    if _driver is None:
        try:
            _driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600,
            )
        except Exception as exc:
            logger.warning("Failed to initialize Neo4j driver: %s", exc)
            return None
    return _driver


def ping_neo4j() -> bool:
    """Ping Neo4j to verify active database connectivity."""
    try:
        driver = get_neo4j_driver()
        if driver is None:
            return False
        driver.verify_connectivity()
        return True
    except (ServiceUnavailable, AuthError, Neo4jError, Exception) as exc:
        logger.warning("Neo4j connectivity check failed: %s", exc)
        return False


def initialize_graphiti_schema(client=None) -> bool:
    """Initialize Graphiti schema indices and constraints idempotently.

    Safe to invoke during startup lifespans or upon client instantiation.
    """
    global _indices_initialized
    if _indices_initialized:
        return True

    target_client = client or _graphiti_instance
    if target_client is None:
        return False

    build_fn = getattr(target_client, "build_indices_and_constraints", None)
    if build_fn is None:
        _indices_initialized = True
        return True

    try:
        import asyncio
        import concurrent.futures
        import inspect

        if inspect.iscoroutinefunction(build_fn):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(asyncio.run, build_fn()).result()
            else:
                asyncio.run(build_fn())
        else:
            build_fn()

        _indices_initialized = True
        logger.info("Successfully established Graphiti indices and schema constraints.")
        return True
    except Exception as exc:
        logger.warning("Failed to initialize Graphiti schema indices and constraints: %s", exc)
        return False


def get_graphiti_client():
    """Get or instantiate singleton Graphiti client with graceful fallback."""
    global _graphiti_instance
    if _graphiti_instance is not None:
        if not _indices_initialized:
            initialize_graphiti_schema(_graphiti_instance)
        return _graphiti_instance

    if not ping_neo4j():
        logger.info("Neo4j is not reachable; Graphiti client will operate in fallback mode.")
        return None

    try:
        from graphiti_core import Graphiti
        _graphiti_instance = Graphiti(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
        )
        initialize_graphiti_schema(_graphiti_instance)
        return _graphiti_instance
    except Exception as exc:
        logger.error("Failed to initialize Graphiti core client: %s", exc)
        return None


def close_connections() -> None:
    """Close active Neo4j driver and Graphiti connections."""
    global _driver, _graphiti_instance, _indices_initialized
    if _graphiti_instance is not None:
        try:
            # Graphiti provides a close() coroutine or method
            if hasattr(_graphiti_instance, "close"):
                import asyncio
                import inspect
                if inspect.iscoroutinefunction(_graphiti_instance.close):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(_graphiti_instance.close())
                    else:
                        loop.run_until_complete(_graphiti_instance.close())
                else:
                    _graphiti_instance.close()
        except Exception as exc:
            logger.debug("Error closing Graphiti instance: %s", exc)
        _graphiti_instance = None
        _indices_initialized = False

    if _driver is not None:
        try:
            _driver.close()
        except Exception as exc:
            logger.debug("Error closing Neo4j driver: %s", exc)
        _driver = None
