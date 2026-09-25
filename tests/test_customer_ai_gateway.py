import pytest
from app.services.gateway.policy_router import route_model, check_rate_limit, enforce_tenant_budget, reset_limits, validate_request
from fastapi import HTTPException

def setup_function():
    reset_limits()

def test_policy_routing():
    assert route_model("luna") == "gpt-4o-mini"
    assert route_model("terra") == "gpt-4o"
    assert route_model("website_generate") == "gpt-4o"
    assert route_model("unknown") == "gpt-4o-mini" # default

def test_rate_limiting():
    tenant_id = "test_tenant"
    for _ in range(10):
        assert check_rate_limit(tenant_id, limit=10, window=60) == True
    
    assert check_rate_limit(tenant_id, limit=10, window=60) == False

def test_tenant_budget():
    tenant_id = "test_tenant"
    assert enforce_tenant_budget(tenant_id, cost=5.0, max_budget=10.0) == True
    assert enforce_tenant_budget(tenant_id, cost=4.0, max_budget=10.0) == True
    assert enforce_tenant_budget(tenant_id, cost=2.0, max_budget=10.0) == False # total 11.0

def test_validate_request():
    tenant_id = "test_tenant"
    model = validate_request(tenant_id, "luna")
    assert model == "gpt-4o-mini"
    
    # Exceed budget
    enforce_tenant_budget(tenant_id, cost=10.0)
    with pytest.raises(HTTPException) as excinfo:
        validate_request(tenant_id, "luna")
    assert excinfo.value.status_code == 402

    # Exceed rate limit
    tenant_id2 = "tenant2"
    for _ in range(10):
        validate_request(tenant_id2, "luna")
    
    with pytest.raises(HTTPException) as excinfo:
        validate_request(tenant_id2, "luna")
    assert excinfo.value.status_code == 429

def test_tenant_isolation():
    tenant_1 = "tenant1"
    tenant_2 = "tenant2"
    
    # Rate limit tenant 1
    for _ in range(10):
        check_rate_limit(tenant_1, limit=10, window=60)
        
    assert check_rate_limit(tenant_1, limit=10, window=60) == False
    assert check_rate_limit(tenant_2, limit=10, window=60) == True # Tenant 2 is isolated


def test_redis_keys_and_budget_keys(monkeypatch):
    from unittest.mock import MagicMock
    mock_redis = MagicMock()
    mock_redis.eval.return_value = 1
    monkeypatch.setattr("app.services.gateway.policy_router.get_redis_client", lambda: mock_redis)

    tenant_id = "tenant_keys_test"
    provider_id = "prov_42"
    period = "2026-09"

    # Enforce budget with provider and period
    ok = enforce_tenant_budget(tenant_id, cost=2.5, max_budget=10.0, provider_id=provider_id, period=period)
    assert ok is True

    # Check key passed to Redis eval
    expected_budget_key = f"fb:budget:{tenant_id}:{provider_id}:{period}"
    mock_redis.eval.assert_called()
    assert mock_redis.eval.call_args[0][2] == expected_budget_key

    # Check rate limit key format
    endpoint = "chat_completion"
    check_rate_limit(tenant_id, limit=5, window=30, endpoint_or_key=endpoint)
    expected_ratelimit_key = f"fb:ratelimit:{tenant_id}:{endpoint}"
    assert mock_redis.eval.call_args[0][2] == expected_ratelimit_key

