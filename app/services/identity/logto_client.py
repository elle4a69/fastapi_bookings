"""Logto Management API Client (WP1).

Provides an administrative client for interacting with the Logto Management API,
provisioning organizations, syncing memberships, and managing roles.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)


class LogtoClientError(Exception):
    """Raised when Logto Management API calls fail."""

    def __init__(self, code: str, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class LogtoClient:
    """Client for Logto Management API with token caching and retry safety."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        m2m_app_id: Optional[str] = None,
        m2m_app_secret: Optional[str] = None,
        api_resource: Optional[str] = None,
    ) -> None:
        self.endpoint = (endpoint or settings.LOGTO_ENDPOINT or "").rstrip("/")
        self.m2m_app_id = m2m_app_id or settings.LOGTO_M2M_APP_ID
        self.m2m_app_secret = m2m_app_secret or settings.LOGTO_M2M_APP_SECRET
        self.api_resource = api_resource or settings.LOGTO_API_RESOURCE
        self._m2m_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    @property
    def is_configured(self) -> bool:
        """Return True if Logto endpoint and credentials are configured."""
        return bool(self.endpoint and self.m2m_app_id and self.m2m_app_secret)

    async def _get_management_token(self) -> str:
        """Fetch or return cached M2M access token for the Management API."""
        now = datetime.now(timezone.utc)
        if self._m2m_token and self._token_expires_at and now < self._token_expires_at:
            return self._m2m_token

        if not self.is_configured:
            raise LogtoClientError(
                code="NOT_CONFIGURED",
                message="Logto client is not configured with endpoint or M2M credentials.",
            )

        token_url = f"{self.endpoint}/oidc/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.m2m_app_id,
            "client_secret": self.m2m_app_secret,
            "resource": f"{self.endpoint}/api",
            "scope": "all",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(token_url, data=payload, headers=headers)
                if resp.status_code != 200:
                    logger.error("Logto M2M token request failed with status %d", resp.status_code)
                    raise LogtoClientError(
                        code="AUTH_FAILED",
                        message="Failed to authenticate M2M client with identity provider.",
                        status_code=resp.status_code,
                    )
                data = resp.json()
                access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 3600))
                self._m2m_token = access_token
                self._token_expires_at = datetime.fromtimestamp(
                    now.timestamp() + max(expires_in - 60, 60),
                    tz=timezone.utc,
                )
                return access_token
        except httpx.RequestError as exc:
            logger.error("Logto M2M token network request failed: %s", exc)
            raise LogtoClientError(
                code="NETWORK_ERROR",
                message="Network error communicating with identity provider.",
            )

    async def get_or_create_organization(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Idempotently fetch or create an organization in Logto.

        Args:
            name: Organization display name.
            description: Optional organization description.

        Returns:
            Dict containing organization details ('id', 'name', 'description').
        """
        if not self.is_configured:
            # Synthetic fallback for unconfigured environments
            synthetic_id = f"synth_org_{abs(hash(name)) % 10000000}"
            return {"id": synthetic_id, "name": name, "description": description or ""}

        token = await self._get_management_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Search existing organizations
            try:
                list_url = f"{self.endpoint}/api/organizations"
                resp = await client.get(list_url, headers=headers)
                if resp.status_code == 200:
                    orgs = resp.json()
                    for org in orgs:
                        if org.get("name") == name:
                            return org
            except Exception as exc:
                logger.warning("Failed listing organizations from Logto: %s", exc)

            # 2. Create organization if not found
            create_url = f"{self.endpoint}/api/organizations"
            payload = {"name": name, "description": description or ""}
            resp = await client.post(create_url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return resp.json()

            # Handle 409 Conflict if created concurrently
            if resp.status_code == 409:
                resp_list = await client.get(create_url, headers=headers)
                if resp_list.status_code == 200:
                    for org in resp_list.json():
                        if org.get("name") == name:
                            return org

            raise LogtoClientError(
                code="ORG_CREATION_FAILED",
                message=f"Failed to create organization in Logto (status {resp.status_code}).",
                status_code=resp.status_code,
            )

    async def add_user_to_organization(
        self,
        external_organization_id: str,
        external_user_id: str,
        role_names: Optional[List[str]] = None,
    ) -> bool:
        """Add an external user to a Logto organization."""
        if not self.is_configured:
            return True

        token = await self._get_management_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{self.endpoint}/api/organizations/{external_organization_id}/users"
        payload = {"userIds": [external_user_id]}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201, 204, 409):
                return True
            logger.warning("Failed adding user to Logto organization: status %d", resp.status_code)
            return False


logto_client = LogtoClient()
