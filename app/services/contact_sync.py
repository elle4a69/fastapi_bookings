import logging
import httpx
from typing import Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.sms_chatwoot import SmsChatwootBinding
from app.core.config import settings
from app.db.async_session import async_session_scope

logger = logging.getLogger(__name__)

async def sync_client_projection_to_chatwoot(
    db: AsyncSession,
    client_id: Union[UUID, int, str],
    tenant_id: Union[UUID, int, str],
    chatwoot_account_id: int
) -> None:
    """
    Synchronize a client's core fields to Chatwoot via projection payload.
    """
    try:
        client_id_val = int(client_id)
        tenant_id_val = int(tenant_id)
        
        # 1. Load the Client
        client = await db.scalar(
            select(Client).where(Client.id == client_id_val, Client.tenant_id == tenant_id_val)
        )
        if not client:
            logger.warning(f"Client {client_id_val} not found.")
            return
            
        # 2. Get API Token and Base URL
        binding = await db.scalar(
            select(SmsChatwootBinding).where(
                SmsChatwootBinding.tenant_id == tenant_id_val,
                SmsChatwootBinding.chatwoot_account_id == chatwoot_account_id,
                SmsChatwootBinding.is_enabled == True
            )
        )
        
        token = binding.chatwoot_api_token if binding and binding.chatwoot_api_token else settings.CHATWOOT_API_ACCESS_TOKEN
        base_url = binding.chatwoot_base_url if binding and binding.chatwoot_base_url else settings.CHATWOOT_BASE_URL
        base_url = base_url.rstrip("/")
        
        if not token:
            logger.warning("No Chatwoot API token available for sync")
            return
            
        # 3. Build Payload
        custom_attributes = {
            "client_id": str(client.id),
            "street_address": client.street_address or "",
            "suburb": client.suburb or "",
            "postcode": client.postcode or ""
        }
        
        payload = {
            "name": client.name or "",
            "phone_number": client.phone or "",
            "email": client.email or "",
            "custom_attributes": custom_attributes
        }
        
        # We need to search by phone to match Chatwoot Contact
        search_q = client.phone
        if not search_q:
            logger.warning(f"Client {client_id_val} has no phone to search in Chatwoot.")
            return
            
        headers = {
            "api_access_token": token,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as http_client:
            search_url = f"{base_url}/api/v1/accounts/{chatwoot_account_id}/contacts/search"
            search_resp = await http_client.get(search_url, params={"q": search_q}, headers=headers)
            search_resp.raise_for_status()
            search_data = search_resp.json()
            
            payload_data = search_data.get("payload", [])
            contact_to_update = None
            if isinstance(payload_data, list) and len(payload_data) > 0:
                contact_to_update = payload_data[0]
                
            if contact_to_update:
                contact_id = contact_to_update["id"]
                update_url = f"{base_url}/api/v1/accounts/{chatwoot_account_id}/contacts/{contact_id}"
                update_resp = await http_client.put(update_url, json=payload, headers=headers)
                update_resp.raise_for_status()
                
                if client.chatwoot_contact_id != contact_id:
                    client.chatwoot_contact_id = contact_id
                    await db.commit()
            else:
                create_url = f"{base_url}/api/v1/accounts/{chatwoot_account_id}/contacts"
                create_resp = await http_client.post(create_url, json=payload, headers=headers)
                create_resp.raise_for_status()
                
                create_data = create_resp.json()
                new_contact_id = create_data.get("payload", {}).get("contact", {}).get("id")
                
                if new_contact_id:
                    client.chatwoot_contact_id = new_contact_id
                    await db.commit()
                    
    except Exception as e:
        logger.error(f"Error syncing client {client_id} to Chatwoot: {e}")

async def dispatch_contact_sync_task(client_id: Union[UUID, int, str], tenant_id: Union[UUID, int, str], chatwoot_account_id: int) -> None:
    """Helper to dispatch sync task using a standalone session."""
    async with async_session_scope() as db:
        await sync_client_projection_to_chatwoot(db, client_id, tenant_id, chatwoot_account_id)

