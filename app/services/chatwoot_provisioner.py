import logging
from typing import Optional
from dataclasses import dataclass
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class TenantProvisionResult:
    chatwoot_account_id: int
    webhook_id: int

class ChatwootProvisionError(Exception):
    """Exception raised for errors during Chatwoot provisioning."""
    pass

def provision_chatwoot_tenant(business_name: str) -> TenantProvisionResult:
    """
    Provisions a new Chatwoot tenant (account) via the Platform API.
    Also creates a webhook for the new account.
    """
    platform_token = settings.CHATWOOT_PLATFORM_ACCESS_TOKEN or settings.CHATWOOT_PLATFORM_API_TOKEN
    base_url = settings.CHATWOOT_BASE_URL.rstrip('/')
    webhook_url = settings.AGENT_WEBHOOK_URL
    
    if not platform_token:
        raise ChatwootProvisionError("Chatwoot platform access token is not configured")
        
    headers = {
        "api_access_token": platform_token,
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(base_url=base_url, headers=headers, timeout=10.0) as client:
            # 1. Create Account
            response = client.post("/platform/api/v1/accounts", json={"name": business_name})
            response.raise_for_status()
            account_data = response.json()
            account_id = account_data.get("id")
            
            if not account_id:
                raise ChatwootProvisionError("Failed to get account ID from creation response")
                
            logger.info(f"Created Chatwoot account '{business_name}' with ID {account_id}")
            
            # 2. Create Webhook for the account
            webhook_payload = {
                "webhook": {
                    "url": webhook_url,
                    "subscriptions": ["message_created", "conversation_status_changed"]
                }
            }
            webhook_resp = client.post(f"/api/v1/accounts/{account_id}/webhooks", json=webhook_payload)
            webhook_resp.raise_for_status()
            
            webhook_data = webhook_resp.json()
            
            webhook_id = None
            if "payload" in webhook_data and isinstance(webhook_data["payload"], dict) and "webhook" in webhook_data["payload"]:
                webhook_id = webhook_data["payload"]["webhook"].get("id")
            else:
                webhook_id = webhook_data.get("id")
                
            if not webhook_id:
                raise ChatwootProvisionError("Failed to get webhook ID from creation response")
                
            logger.info(f"Created webhook ID {webhook_id} for Chatwoot account ID {account_id}")
            
            return TenantProvisionResult(
                chatwoot_account_id=account_id,
                webhook_id=webhook_id
            )
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred during Chatwoot provisioning: {e.response.text}")
        raise ChatwootProvisionError(f"HTTP error during provisioning: {e}")
    except httpx.RequestError as e:
        logger.error(f"Request error occurred during Chatwoot provisioning: {e}")
        raise ChatwootProvisionError(f"Request error during provisioning: {e}")
