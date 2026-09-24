import httpx
import logging
from typing import Dict, Any, Optional

from .policy_router import validate_request, enforce_tenant_budget

logger = logging.getLogger(__name__)


class AiGatewayError(RuntimeError):
    """Privacy-safe external model gateway failure."""

async def generate_response(
    tenant_id: str,
    messages: list,
    policy_name: str = "luna",
    response_format: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calls the OpenAI API based on the policy, applying structured outputs and rate limits.
    """
    # 1. Validate request (Rate limit, initial budget check)
    model = validate_request(tenant_id, policy_name)

    if not api_key:
        from ...core.config import settings

        api_key = settings.OPENAI_API_KEY.get_secret_value()

    if not api_key:
        raise ValueError("OpenAI API Key is missing.")

    payload = {
        "model": model,
        "messages": messages
    }
    
    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Simple cost simulation for budget
            cost = 0.01  # Mock cost
            enforce_tenant_budget(tenant_id, cost)
            
            return result
    except Exception:
        # Provider exceptions can contain response bodies, request details, or
        # credentials. Keep the log structural and let the caller fail closed.
        logger.error("OpenAI gateway request failed.")
        raise AiGatewayError("AI gateway request failed.") from None
