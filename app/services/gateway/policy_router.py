from typing import Dict, Any, Optional
import time
from fastapi import HTTPException

# Models
MODELS = {
    "luna": "gpt-4o-mini",
    "terra": "gpt-4o",
    "website_generate": "gpt-4o"
}

# In-memory stores for rate limiting and budgets
# A real implementation would use Redis or the database
RATE_LIMITS = {}
BUDGETS = {}

def reset_limits():
    RATE_LIMITS.clear()
    BUDGETS.clear()

def check_rate_limit(tenant_id: str, limit: int = 10, window: int = 60) -> bool:
    now = time.time()
    if tenant_id not in RATE_LIMITS:
        RATE_LIMITS[tenant_id] = []
    
    # Filter out requests outside the window
    RATE_LIMITS[tenant_id] = [t for t in RATE_LIMITS[tenant_id] if now - t < window]
    
    if len(RATE_LIMITS[tenant_id]) >= limit:
        return False
    
    RATE_LIMITS[tenant_id].append(now)
    return True

def enforce_tenant_budget(tenant_id: str, cost: float, max_budget: float = 10.0) -> bool:
    if tenant_id not in BUDGETS:
        BUDGETS[tenant_id] = 0.0
        
    if BUDGETS[tenant_id] + cost > max_budget:
        return False
        
    BUDGETS[tenant_id] += cost
    return True

def route_model(policy_name: str) -> str:
    """Returns the OpenAI model name for the given policy."""
    return MODELS.get(policy_name, MODELS["luna"])

def validate_request(tenant_id: str, policy_name: str = "luna"):
    if not check_rate_limit(tenant_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # We will enforce budget after response is received or keep track of estimated budget
    if tenant_id in BUDGETS and BUDGETS[tenant_id] >= 10.0:
        raise HTTPException(status_code=402, detail="Tenant budget exceeded")
    
    return route_model(policy_name)
