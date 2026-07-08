import base64
import logging
import httpx
from ..core.config import settings

logger = logging.getLogger(__name__)

class ClickSendClient:
    def __init__(self):
        self.username = settings.CLICKSEND_API_USERNAME
        self.api_key = settings.CLICKSEND_API_KEY
        
        # Build authorization header
        auth_str = f"{self.username}:{self.api_key}"
        encoded_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json"
        }

    async def send_sms(self, to: str, body: str, sender: str = None) -> dict:
        """Send an SMS via ClickSend API."""
        url = "https://rest.clicksend.com/v3/sms/send"
        payload = {
            "messages": [
                {
                    "source": "fastapi",
                    "body": body,
                    "to": to,
                    "from": sender or "+61488847847" # Default fallback
                }
            ]
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers, timeout=10.0)
                response.raise_for_status()
                res_data = response.json()
                logger.info(f"ClickSend SMS successfully sent to {to}: {res_data}")
                return res_data
            except Exception as e:
                logger.error(f"Failed to send ClickSend SMS to {to}: {str(e)}")
                raise

    async def send_mms(self, to: str, body: str, media_url: str, subject: str = "Notification", sender: str = None) -> dict:
        """Send an MMS via ClickSend API."""
        url = "https://rest.clicksend.com/v3/mms/send"
        payload = {
            "messages": [
                {
                    "direction": "out",
                    "media_file": media_url,
                    "to": to,
                    "body": body,
                    "subject": subject,
                    "from": sender or "+61488847847"
                }
            ]
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers, timeout=10.0)
                response.raise_for_status()
                res_data = response.json()
                logger.info(f"ClickSend MMS successfully sent to {to}: {res_data}")
                return res_data
            except Exception as e:
                logger.error(f"Failed to send ClickSend MMS to {to}: {str(e)}")
                raise

clicksend_client = ClickSendClient()
