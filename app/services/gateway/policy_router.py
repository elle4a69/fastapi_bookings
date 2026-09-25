from typing import Dict, Any, Optional, List
import time
import uuid
from fastapi import HTTPException

from app.core.redis import get_redis_client

# Models
MODELS = {
    "luna": "gpt-4o-mini",
    "terra": "gpt-4o",
    "website_generate": "gpt-4o",
}

# Local in-memory fallbacks if Redis is unavailable
_LOCAL_RATE_LIMITS: Dict[str, List[float]] = {}
_LOCAL_BUDGETS: Dict[str, float] = {}

SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

local clear_before = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)
local current_requests = redis.call('ZCARD', key)
if current_requests < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, math.ceil(window))
    return 1
else
    return 0
end
"""

ENFORCE_BUDGET_LUA = """
local key = KEYS[1]
local cost = tonumber(ARGV[1])
local max_budget = tonumber(ARGV[2])

local current = tonumber(redis.call('GET', key) or '0')
if current + cost > max_budget then
    return 0
else
    redis.call('INCRBYFLOAT', key, cost)
    return 1
end
"""


def reset_limits():
    """Reset all rate limits and budgets across Redis and local fallback stores."""
    _LOCAL_RATE_LIMITS.clear()
    _LOCAL_BUDGETS.clear()
    try:
        r = get_redis_client()
        keys = r.keys("fb:ratelimit:*") + r.keys("fb:budget:*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass


def check_rate_limit(
    tenant_id: str,
    limit: int = 10,
    window: int = 60,
    endpoint_or_key: str = "default",
) -> bool:
    """Check and record request rate using a Redis sliding-window log with graceful local fallback."""
    key = f"fb:ratelimit:{tenant_id}:{endpoint_or_key}"
    now = time.time()

    try:
        r = get_redis_client()
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        res = r.eval(SLIDING_WINDOW_LUA, 1, key, str(now), str(window), str(limit), member)
        return res == 1
    except Exception:
        if key not in _LOCAL_RATE_LIMITS:
            _LOCAL_RATE_LIMITS[key] = []
        _LOCAL_RATE_LIMITS[key] = [t for t in _LOCAL_RATE_LIMITS[key] if now - t < window]
        if len(_LOCAL_RATE_LIMITS[key]) >= limit:
            return False
        _LOCAL_RATE_LIMITS[key].append(now)
        return True


def enforce_tenant_budget(
    tenant_id: str,
    cost: float,
    max_budget: float = 10.0,
    provider_id: str = "all",
    period: str = "current",
) -> bool:
    """Enforce tenant/provider budget using Redis counters with graceful local fallback."""
    key = f"fb:budget:{tenant_id}:{provider_id}:{period}"
    try:
        r = get_redis_client()
        res = r.eval(ENFORCE_BUDGET_LUA, 1, key, str(cost), str(max_budget))
        return res == 1
    except Exception:
        if key not in _LOCAL_BUDGETS:
            _LOCAL_BUDGETS[key] = 0.0
        if _LOCAL_BUDGETS[key] + cost > max_budget:
            return False
        _LOCAL_BUDGETS[key] += cost
        return True


def get_tenant_budget(
    tenant_id: str,
    provider_id: str = "all",
    period: str = "current",
) -> float:
    """Get the current accumulated budget usage for a tenant/provider/period."""
    key = f"fb:budget:{tenant_id}:{provider_id}:{period}"
    try:
        r = get_redis_client()
        val = r.get(key)
        return float(val) if val is not None else 0.0
    except Exception:
        return _LOCAL_BUDGETS.get(key, 0.0)


def route_model(policy_name: str) -> str:
    """Returns the OpenAI model name for the given policy."""
    return MODELS.get(policy_name, MODELS["luna"])


def validate_request(
    tenant_id: str,
    policy_name: str = "luna",
    provider_id: str = "all",
    period: str = "current",
    max_budget: float = 10.0,
) -> str:
    """Validate request rate limit and budget status before routing to model."""
    if not check_rate_limit(tenant_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if get_tenant_budget(tenant_id, provider_id, period) >= max_budget:
        raise HTTPException(status_code=402, detail="Tenant budget exceeded")

    return route_model(policy_name)
