"""Redis client integration module.

Provides thread-safe and async connection pools, key prefixing with multi-tenant isolation,
health checks (ping), and resilient fallback handling.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
import redis
import redis.asyncio as aioredis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "fb:"

_sync_pool: Optional[redis.ConnectionPool] = None
_async_pool: Optional[aioredis.ConnectionPool] = None


def format_key(key: str, tenant_id: Optional[int] = None) -> str:
    """Format and namespace a Redis key with the global prefix and optional tenant ID."""
    if key.startswith(KEY_PREFIX):
        return key

    clean_key = key.lstrip(":")
    if tenant_id is not None:
        return f"{KEY_PREFIX}{tenant_id}:{clean_key}"
    return f"{KEY_PREFIX}{clean_key}"


def get_sync_pool() -> redis.ConnectionPool:
    """Get or create singleton sync ConnectionPool."""
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
            max_connections=20,
        )
    return _sync_pool


def get_async_pool() -> aioredis.ConnectionPool:
    """Get or create singleton async ConnectionPool."""
    global _async_pool
    if _async_pool is None:
        _async_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
            max_connections=20,
        )
    return _async_pool


def get_redis_client() -> redis.Redis:
    """Return a synchronous Redis client instance backed by the connection pool."""
    return redis.Redis(connection_pool=get_sync_pool())


def get_async_redis_client() -> aioredis.Redis:
    """Return an asynchronous Redis client instance backed by the connection pool."""
    return aioredis.Redis(connection_pool=get_async_pool())


def ping() -> bool:
    """Synchronous health check ping returning True if Redis is reachable, False otherwise."""
    try:
        client = get_redis_client()
        return bool(client.ping())
    except (ConnectionError, TimeoutError, RedisError) as exc:
        logger.warning("Redis sync ping failed: %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error during Redis sync ping: %s", exc)
        return False


async def async_ping() -> bool:
    """Asynchronous health check ping returning True if Redis is reachable, False otherwise."""
    try:
        client = get_async_redis_client()
        res = await client.ping()
        return bool(res)
    except (ConnectionError, TimeoutError, RedisError) as exc:
        logger.warning("Redis async ping failed: %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error during Redis async ping: %s", exc)
        return False


def close_connections() -> None:
    """Close synchronous connection pool."""
    global _sync_pool
    if _sync_pool is not None:
        _sync_pool.disconnect()
        _sync_pool = None


async def async_close_connections() -> None:
    """Close asynchronous connection pool."""
    global _async_pool
    if _async_pool is not None:
        await _async_pool.disconnect()
        _async_pool = None
