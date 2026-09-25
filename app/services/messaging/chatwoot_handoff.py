"""Chatwoot AgentBot handoff and messaging service.

Handles transitioning conversations from bot automation to human agents
and sending outbound bot messages via the Chatwoot REST API.
"""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


async def handoff_to_human(
    chatwoot_base_url: str,
    api_access_token: str,
    account_id: int,
    conversation_id: int,
    note: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Transition a Chatwoot conversation from bot to human agent.

    Changes conversation status to 'open' and optionally adds a private note
    to provide the human agent with context or reason for handoff.

    Args:
        chatwoot_base_url: Chatwoot instance base URL (e.g. 'https://app.chatwoot.com').
        api_access_token: Chatwoot API access token (bot or account token).
        account_id: The Chatwoot account ID.
        conversation_id: The Chatwoot conversation ID to open.
        note: Optional internal note text to append to the agent inbox.
        client: Optional httpx.AsyncClient instance for testing or reuse.
        timeout: HTTP request timeout in seconds.

    Returns:
        Summary dict containing handoff status and conversation update details.
    """
    base_url = chatwoot_base_url.rstrip("/")
    status_url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}"
    messages_url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"

    headers = {
        "api_access_token": api_access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async def _execute(http_client: httpx.AsyncClient) -> dict[str, Any]:
        logger.info(
            "Initiating Chatwoot human handoff for account=%s, conversation=%s",
            account_id,
            conversation_id,
        )

        # 1. Update conversation status to 'open'
        patch_payload = {"status": "open"}
        patch_resp = await http_client.patch(
            status_url,
            json=patch_payload,
            headers=headers,
            timeout=timeout,
        )
        patch_resp.raise_for_status()
        conversation_data = patch_resp.json()

        # 2. Post internal/private note if provided
        note_result: Optional[dict[str, Any]] = None
        if note:
            note_payload = {
                "content": note,
                "private": True,
                "message_type": "outgoing",
            }
            logger.info(
                "Posting handoff private note to conversation=%s",
                conversation_id,
            )
            note_resp = await http_client.post(
                messages_url,
                json=note_payload,
                headers=headers,
                timeout=timeout,
            )
            note_resp.raise_for_status()
            note_result = note_resp.json()

        return {
            "status": "success",
            "conversation_id": conversation_id,
            "account_id": account_id,
            "conversation_status": "open",
            "note_sent": note is not None,
            "conversation": conversation_data,
            "note_details": note_result,
        }

    try:
        if client is not None:
            return await _execute(client)
        async with httpx.AsyncClient(timeout=timeout) as temp_client:
            return await _execute(temp_client)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "HTTP %d error during Chatwoot human handoff (conversation=%s): %s",
            exc.response.status_code,
            conversation_id,
            exc.response.text,
        )
        raise
    except Exception as exc:
        logger.error(
            "Failed Chatwoot human handoff (conversation=%s): %s",
            conversation_id,
            exc,
            exc_info=True,
        )
        raise


async def send_bot_message(
    chatwoot_base_url: str,
    api_access_token: str,
    account_id: int,
    conversation_id: int,
    content: str,
    client: Optional[httpx.AsyncClient] = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Send an outgoing bot message to a Chatwoot conversation.

    Args:
        chatwoot_base_url: Chatwoot instance base URL.
        api_access_token: Chatwoot API access token.
        account_id: The Chatwoot account ID.
        conversation_id: The Chatwoot conversation ID.
        content: Text content of the message to send.
        client: Optional httpx.AsyncClient instance for testing or reuse.
        timeout: HTTP request timeout in seconds.

    Returns:
        JSON response dict from Chatwoot API containing the created message.
    """
    base_url = chatwoot_base_url.rstrip("/")
    url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"

    headers = {
        "api_access_token": api_access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "content": content,
        "message_type": "outgoing",
    }

    async def _execute(http_client: httpx.AsyncClient) -> dict[str, Any]:
        logger.info(
            "Sending Chatwoot bot message to account=%s, conversation=%s",
            account_id,
            conversation_id,
        )
        response = await http_client.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(
            "Chatwoot bot message sent successfully (message_id=%s)",
            data.get("id"),
        )
        return data

    try:
        if client is not None:
            return await _execute(client)
        async with httpx.AsyncClient(timeout=timeout) as temp_client:
            return await _execute(temp_client)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "HTTP %d error sending Chatwoot bot message (conversation=%s): %s",
            exc.response.status_code,
            conversation_id,
            exc.response.text,
        )
        raise
    except Exception as exc:
        logger.error(
            "Failed sending Chatwoot bot message (conversation=%s): %s",
            conversation_id,
            exc,
            exc_info=True,
        )
        raise
