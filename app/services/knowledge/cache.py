"""Redis cache and epoch management for the knowledge subsystem.

Spec references: Sections 49, 50, 51, 52, 97, 98.
Key schema: fb:tenant:{tenant_id}:provider:{provider_id}:knowledge:{epoch}:{query_hash}
Profile schema: fb:tenant:{tenant_id}:provider:{provider_id}:profile:{epoch}
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

# Default TTL for cached knowledge query results (Spec 49: default 300s)
KNOWLEDGE_CACHE_TTL_SECONDS = getattr(settings, "KNOWLEDGE_CACHE_TTL_SECONDS", 300)

# In-memory fallback dictionaries if Redis is offline (Spec 51, 98)
_in_memory_epochs: Dict[str, int] = {}
_in_memory_cache: Dict[str, str] = {}
_in_memory_profiles: Dict[str, str] = {}


def clear_in_memory_cache() -> None:
    """Reset all in-memory fallback caches (used primarily during unit testing)."""
    _in_memory_epochs.clear()
    _in_memory_cache.clear()
    _in_memory_profiles.clear()


def _tenant_epoch_key(tenant_id: int) -> str:
    return f"fb:tenant:{tenant_id}:knowledge:epoch"


def _provider_epoch_key(tenant_id: int, provider_id: int) -> str:
    return f"fb:tenant:{tenant_id}:provider:{provider_id}:knowledge:epoch"


def get_tenant_epoch(tenant_id: int) -> int:
    """Retrieve current knowledge epoch for a tenant."""
    key = _tenant_epoch_key(tenant_id)
    try:
        client = get_redis_client()
        val = client.get(key)
        if val is not None:
            return int(val)
        # Initialize epoch to 1 if unset
        client.set(key, 1)
        return 1
    except (RedisError, Exception) as exc:
        logger.debug("Redis error in get_tenant_epoch, using fallback: %s", exc)
        return _in_memory_epochs.get(key, 1)


def get_provider_epoch(tenant_id: int, provider_id: int) -> int:
    """Retrieve current knowledge epoch for a provider."""
    key = _provider_epoch_key(tenant_id, provider_id)
    try:
        client = get_redis_client()
        val = client.get(key)
        if val is not None:
            return int(val)
        # Initialize epoch to 1 if unset
        client.set(key, 1)
        return 1
    except (RedisError, Exception) as exc:
        logger.debug("Redis error in get_provider_epoch, using fallback: %s", exc)
        return _in_memory_epochs.get(key, 1)


def increment_tenant_epoch(tenant_id: int) -> int:
    """Increment knowledge epoch for a tenant, invalidating cached tenant knowledge."""
    key = _tenant_epoch_key(tenant_id)
    try:
        client = get_redis_client()
        new_epoch = client.incr(key)
        return int(new_epoch)
    except (RedisError, Exception) as exc:
        logger.debug("Redis error in increment_tenant_epoch, using fallback: %s", exc)
        current = _in_memory_epochs.get(key, 1)
        _in_memory_epochs[key] = current + 1
        return _in_memory_epochs[key]


def increment_provider_epoch(tenant_id: int, provider_id: int) -> int:
    """Increment knowledge epoch for a provider, invalidating cached provider knowledge."""
    key = _provider_epoch_key(tenant_id, provider_id)
    try:
        client = get_redis_client()
        new_epoch = client.incr(key)
        return int(new_epoch)
    except (RedisError, Exception) as exc:
        logger.debug("Redis error in increment_provider_epoch, using fallback: %s", exc)
        current = _in_memory_epochs.get(key, 1)
        _in_memory_epochs[key] = current + 1
        return _in_memory_epochs[key]


def hash_query(query: str, kinds: Optional[List[str]] = None) -> str:
    """Generate deterministic SHA256 digest of a query string and filters."""
    normalized_kinds = sorted(kinds) if kinds else []
    payload = f"{query.strip().lower()}::{'|'.join(normalized_kinds)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def get_composite_epoch(tenant_id: int, provider_id: Optional[int] = None) -> str:
    """Retrieve composite epoch for cache partitioning.

    For provider queries: f"{tenant_epoch}:{provider_epoch}", ensuring tenant-level
    invalidation cascades to all provider caches (Spec 50, 97).
    For shared tenant queries: f"{tenant_epoch}".
    """
    tenant_epoch = get_tenant_epoch(tenant_id)
    if provider_id is not None:
        provider_epoch = get_provider_epoch(tenant_id, provider_id)
        return f"{tenant_epoch}:{provider_epoch}"
    return str(tenant_epoch)


def build_cache_key(
    tenant_id: int,
    provider_id: Optional[int],
    epoch: Any,
    query_hash: str,
) -> str:
    """Construct cache key following the specification schema:
    fb:tenant:{tenant_id}:provider:{provider_id}:knowledge:{epoch}:{query_hash}
    """
    prov_segment = str(provider_id) if provider_id is not None else "shared"
    return f"fb:tenant:{tenant_id}:provider:{prov_segment}:knowledge:{epoch}:{query_hash}"


def build_provider_profile_cache_key(
    tenant_id: int,
    provider_id: int,
    epoch: Any,
) -> str:
    """Construct configuration cache key for provider profiles (Spec 52):
    fb:tenant:{tenant_id}:provider:{provider_id}:profile:{epoch}
    """
    return f"fb:tenant:{tenant_id}:provider:{provider_id}:profile:{epoch}"


def get_cached_knowledge(cache_key: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached retrieval result payload if present."""
    try:
        client = get_redis_client()
        raw = client.get(cache_key)
        if raw:
            return json.loads(raw)
    except (RedisError, Exception) as exc:
        logger.debug("Redis error getting cached knowledge: %s", exc)
        raw = _in_memory_cache.get(cache_key)
        if raw:
            return json.loads(raw)
    return None


def set_cached_knowledge(
    cache_key: str,
    data: Dict[str, Any],
    ttl_seconds: Optional[int] = None,
) -> None:
    """Store retrieval result payload into cache."""
    ttl = ttl_seconds if ttl_seconds is not None else getattr(settings, "KNOWLEDGE_CACHE_TTL_SECONDS", 300)
    encoded = json.dumps(data, default=str)
    try:
        client = get_redis_client()
        client.set(cache_key, encoded, ex=ttl)
    except (RedisError, Exception) as exc:
        logger.debug("Redis error setting cached knowledge: %s", exc)
        _in_memory_cache[cache_key] = encoded


def get_cached_provider_profile(tenant_id: int, provider_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve cached provider profile configuration using composite epoch (Spec 52)."""
    epoch = get_composite_epoch(tenant_id, provider_id)
    cache_key = build_provider_profile_cache_key(tenant_id, provider_id, epoch)
    try:
        client = get_redis_client()
        raw = client.get(cache_key)
        if raw:
            return json.loads(raw)
    except (RedisError, Exception) as exc:
        logger.debug("Redis error getting cached provider profile: %s", exc)
        raw = _in_memory_profiles.get(cache_key)
        if raw:
            return json.loads(raw)
    return None


def set_cached_provider_profile(
    tenant_id: int,
    provider_id: int,
    profile_data: Dict[str, Any],
    ttl_seconds: Optional[int] = None,
) -> None:
    """Store provider profile configuration in cache with epoch-based invalidation (Spec 52)."""
    epoch = get_composite_epoch(tenant_id, provider_id)
    cache_key = build_provider_profile_cache_key(tenant_id, provider_id, epoch)
    ttl = ttl_seconds if ttl_seconds is not None else getattr(settings, "KNOWLEDGE_CACHE_TTL_SECONDS", 300)
    encoded = json.dumps(profile_data, default=str)
    try:
        client = get_redis_client()
        client.set(cache_key, encoded, ex=ttl)
    except (RedisError, Exception) as exc:
        logger.debug("Redis error setting cached provider profile: %s", exc)
        _in_memory_profiles[cache_key] = encoded
