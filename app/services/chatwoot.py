import logging
import httpx
import os

logger = logging.getLogger(__name__)

class ChatwootClient:
    def __init__(self):
        # Allow configuration via environment variables or parameters
        self.api_url = os.environ.get("CHATWOOT_API_URL", "https://app.chatwoot.com/api/v1")
        self.access_token = os.environ.get("CHATWOOT_ACCESS_TOKEN", "")

    async def send_message(self, account_id: int, conversation_id: int, message: str, is_private: bool = False) -> dict:
        """Send a message or a private note to a Chatwoot conversation."""
        if not self.access_token:
            logger.warning("CHATWOOT_ACCESS_TOKEN is not set. Skipping message send.")
            return {"status": "skipped", "reason": "no_token"}

        url = f"{self.api_url}/accounts/{account_id}/conversations/{conversation_id}/messages"
        headers = {
            "api_access_token": self.access_token,
            "Content-Type": "application/json"
        }
        payload = {
            "content": message,
            "message_type": "outgoing",
            "private": is_private
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                res_data = response.json()
                logger.info(f"Chatwoot message sent successfully: {res_data}")
                return res_data
            except Exception as e:
                logger.error(f"Failed to send Chatwoot message: {str(e)}")
                raise

chatwoot_client = ChatwootClient()
