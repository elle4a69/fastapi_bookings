"""Flexprice API client for managing customers, portal sessions, and subscriptions."""

import logging
from typing import Any, Callable, Dict, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class FlexpriceClientError(Exception):
    """Base error for Flexprice API client failures."""
    pass


class FlexpriceOutageError(FlexpriceClientError):
    """Raised when Flexprice API is unreachable, times out, or returns a 5xx server error."""
    pass


class FlexpriceClient:
    """Client for interacting with the Flexprice Billing API.

    Enforces fail-closed semantics: network failures, 5xx server errors, or invalid
    responses raise explicit exceptions and NEVER fail open or grant elevated privileges.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = (base_url or settings.FLEXPRICE_API_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.FLEXPRICE_API_KEY
        self.timeout = timeout
        self.transport = transport
        # Mock hook for local tests without network calls
        self._mock_handler: Optional[Callable[[str, str, Optional[Dict[str, Any]]], Dict[str, Any]]] = None

    def set_mock_handler(
        self,
        handler: Optional[Callable[[str, str, Optional[Dict[str, Any]]], Dict[str, Any]]],
    ) -> None:
        """Set a test handler to mock responses without hitting the network."""
        self._mock_handler = handler

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute HTTP request to Flexprice API with fail-closed error handling."""
        if self._mock_handler is not None:
            return self._mock_handler(method, path, json_data)

        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
                headers=self._headers(),
            ) as client:
                response = client.request(method, url, json=json_data, params=params)

                if response.status_code >= 500:
                    logger.error(
                        "Flexprice server outage: %d %s",
                        response.status_code,
                        response.text[:200],
                    )
                    raise FlexpriceOutageError(
                        f"Flexprice service unavailable ({response.status_code})"
                    )

                if response.status_code >= 400:
                    logger.warning(
                        "Flexprice client error: %d %s",
                        response.status_code,
                        response.text[:200],
                    )
                    raise FlexpriceClientError(
                        f"Flexprice API error ({response.status_code}): {response.text[:200]}"
                    )

                return response.json()

        except httpx.TimeoutException as exc:
            logger.error("Flexprice request timed out: %s", exc)
            raise FlexpriceOutageError(f"Flexprice connection timed out: {exc}") from exc
        except httpx.NetworkError as exc:
            logger.error("Flexprice network error: %s", exc)
            raise FlexpriceOutageError(f"Flexprice network error: {exc}") from exc
        except (FlexpriceClientError, FlexpriceOutageError):
            raise
        except Exception as exc:
            logger.error("Unexpected error contacting Flexprice: %s", exc)
            raise FlexpriceClientError(f"Unexpected error: {exc}") from exc

    def create_customer(
        self,
        tenant_id: int,
        name: str,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new billing customer in Flexprice."""
        payload = {
            "external_id": f"tenant_{tenant_id}",
            "name": name,
            "metadata": {"tenant_id": str(tenant_id)},
        }
        if email:
            payload["email"] = email
        return self._request("POST", "/customers", json_data=payload)

    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Retrieve a customer by Flexprice customer ID."""
        return self._request("GET", f"/customers/{customer_id}")

    def create_portal_session(
        self,
        customer_id: str,
        return_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a customer billing portal session URL.

        Returns:
            Dict containing 'url' and optionally 'expires_at'.
        """
        payload = {
            "customer_id": customer_id,
            "return_url": return_url or settings.FLEXPRICE_PORTAL_RETURN_URL,
        }
        return self._request("POST", "/portal/sessions", json_data=payload)

    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Retrieve subscription state from Flexprice."""
        return self._request("GET", f"/subscriptions/{subscription_id}")

    def send_usage_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Dispatch a batch of metered usage events."""
        payload = {"events": events}
        return self._request("POST", "/events/batch", json_data=payload)


flexprice_client = FlexpriceClient()
