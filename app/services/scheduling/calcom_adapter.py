"""Cal.com API integration adapter for external booking and scheduling.

Provides an asynchronous client to interact with Cal.com API endpoints,
handling slot retrieval, booking holds, and booking confirmations with
timeout control, structured logging, and graceful error fallbacks.
"""

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)


class CalComAdapter:
    """Async adapter for communicating with Cal.com API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Initialize the Cal.com adapter.

        Args:
            api_key: Cal.com API key. Defaults to settings.CALCOM_API_KEY.
            base_url: Base URL for Cal.com API. Defaults to settings.CALCOM_BASE_URL.
            timeout: Default timeout in seconds for HTTP requests. Defaults to 10.0.
            client: Optional externally managed httpx.AsyncClient instance.
        """
        self.api_key: str = (
            api_key if api_key is not None else getattr(settings, "CALCOM_API_KEY", "")
        )
        raw_base_url = (
            base_url if base_url is not None else getattr(settings, "CALCOM_BASE_URL", "https://api.cal.com/v1")
        )
        self.base_url: str = raw_base_url.rstrip("/")
        self.timeout: float = timeout
        self._external_client: Optional[httpx.AsyncClient] = client
        self._owned_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create an active httpx.AsyncClient instance."""
        if self._external_client is not None:
            return self._external_client
        if self._owned_client is None or self._owned_client.is_closed:
            self._owned_client = httpx.AsyncClient(timeout=self.timeout)
        return self._owned_client

    async def close(self) -> None:
        """Close the internal HTTP client if owned by this adapter."""
        if self._owned_client is not None and not self._owned_client.is_closed:
            await self._owned_client.aclose()
            self._owned_client = None

    async def __aenter__(self) -> "CalComAdapter":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit, ensuring internal resources are closed."""
        await self.close()

    def _build_headers(self) -> dict[str, str]:
        """Construct standard authorization and content headers."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["apiKey"] = self.api_key
        return headers

    async def get_available_slots(
        self,
        event_type_id: int,
        start_time: datetime,
        end_time: datetime,
        time_zone: str = "UTC",
    ) -> list[dict[str, Any]]:
        """Fetch available booking slots from Cal.com.

        Args:
            event_type_id: The Cal.com event type identifier.
            start_time: Window start datetime.
            end_time: Window end datetime.
            time_zone: Desired timezone string (e.g. "UTC", "Australia/Sydney").

        Returns:
            A list of slot dictionaries containing at least the slot time.
            Returns an empty list as graceful fallback if an error or timeout occurs.
        """
        endpoint = f"{self.base_url}/slots"
        params: dict[str, str] = {
            "eventTypeId": str(event_type_id),
            "startTime": start_time.isoformat(),
            "endTime": end_time.isoformat(),
            "timeZone": time_zone,
        }
        if self.api_key:
            params["apiKey"] = self.api_key

        client = await self._get_client()
        try:
            logger.info(
                "Fetching Cal.com slots for event_type_id=%s between %s and %s (%s)",
                event_type_id,
                start_time.isoformat(),
                end_time.isoformat(),
                time_zone,
            )
            response = await client.get(
                endpoint,
                params=params,
                headers=self._build_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            # Cal.com slot responses can be:
            # 1. {"slots": {"2026-09-10": [{"time": "2026-09-10T10:00:00.000Z"}], ...}}
            # 2. {"slots": [{"time": "2026-09-10T10:00:00.000Z"}]}
            # 3. [{"time": "2026-09-10T10:00:00.000Z"}]
            slots_data = data.get("slots", data) if isinstance(data, dict) else data

            normalized_slots: list[dict[str, Any]] = []
            if isinstance(slots_data, dict):
                for date_key, slot_items in slots_data.items():
                    if isinstance(slot_items, list):
                        for slot in slot_items:
                            if isinstance(slot, dict):
                                slot_copy = dict(slot)
                                slot_copy.setdefault("date", date_key)
                                normalized_slots.append(slot_copy)
                            elif isinstance(slot, str):
                                normalized_slots.append({"time": slot, "date": date_key})
            elif isinstance(slots_data, list):
                for slot in slots_data:
                    if isinstance(slot, dict):
                        normalized_slots.append(slot)
                    elif isinstance(slot, str):
                        normalized_slots.append({"time": slot})

            logger.info(
                "Successfully retrieved %d available slots for event_type_id=%s",
                len(normalized_slots),
                event_type_id,
            )
            return normalized_slots

        except httpx.TimeoutException as exc:
            logger.error(
                "Timeout connecting to Cal.com slots endpoint (%s): %s",
                endpoint,
                exc,
            )
            return []
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP %d error returned from Cal.com slots endpoint (%s): %s",
                exc.response.status_code,
                endpoint,
                exc.response.text,
            )
            return []
        except Exception as exc:
            logger.error(
                "Unexpected error fetching available slots from Cal.com: %s",
                exc,
                exc_info=True,
            )
            return []

    async def create_booking_hold(
        self,
        event_type_id: int,
        start_time: datetime,
        client_name: str,
        client_email: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a temporary booking hold in Cal.com.

        Args:
            event_type_id: The Cal.com event type identifier.
            start_time: Slot start datetime.
            client_name: Full name of the client.
            client_email: Email address of the client.
            notes: Optional booking notes or special instructions.

        Returns:
            Dictionary containing booking hold data or fallback error dictionary.
        """
        endpoint = f"{self.base_url}/bookings"
        payload: dict[str, Any] = {
            "eventTypeId": event_type_id,
            "start": start_time.isoformat(),
            "name": client_name,
            "email": client_email,
            "status": "PENDING",
            "metadata": {
                "is_hold": True,
                "hold_created_at": datetime.utcnow().isoformat(),
            },
        }
        if notes:
            payload["notes"] = notes

        params: dict[str, str] = {}
        if self.api_key:
            params["apiKey"] = self.api_key

        client = await self._get_client()
        try:
            logger.info(
                "Creating Cal.com booking hold for event_type_id=%s at %s (client: %s)",
                event_type_id,
                start_time.isoformat(),
                client_email,
            )
            response = await client.post(
                endpoint,
                json=payload,
                params=params,
                headers=self._build_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Successfully created Cal.com booking hold for %s (id: %s)",
                client_email,
                data.get("id") or data.get("booking", {}).get("id"),
            )
            return data

        except httpx.TimeoutException as exc:
            logger.error(
                "Timeout connecting to Cal.com booking endpoint during hold creation: %s",
                exc,
            )
            return {
                "status": "error",
                "error_type": "timeout",
                "message": "Cal.com request timed out while creating booking hold",
                "event_type_id": event_type_id,
                "start_time": start_time.isoformat(),
            }
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP %d error creating booking hold on Cal.com: %s",
                exc.response.status_code,
                exc.response.text,
            )
            return {
                "status": "error",
                "error_type": "http_error",
                "status_code": exc.response.status_code,
                "message": exc.response.text,
                "event_type_id": event_type_id,
                "start_time": start_time.isoformat(),
            }
        except Exception as exc:
            logger.error(
                "Unexpected error creating booking hold on Cal.com: %s",
                exc,
                exc_info=True,
            )
            return {
                "status": "error",
                "error_type": "unexpected_error",
                "message": str(exc),
                "event_type_id": event_type_id,
                "start_time": start_time.isoformat(),
            }

    async def confirm_booking(self, booking_id: str | int) -> dict[str, Any]:
        """Confirm a previously placed booking hold in Cal.com.

        Args:
            booking_id: The Cal.com booking ID to confirm.

        Returns:
            Dictionary containing confirmed booking data or fallback error dictionary.
        """
        endpoint = f"{self.base_url}/bookings/{booking_id}"
        payload: dict[str, Any] = {"status": "ACCEPTED"}

        params: dict[str, str] = {}
        if self.api_key:
            params["apiKey"] = self.api_key

        client = await self._get_client()
        try:
            logger.info("Confirming Cal.com booking id=%s", booking_id)
            response = await client.patch(
                endpoint,
                json=payload,
                params=params,
                headers=self._build_headers(),
                timeout=self.timeout,
            )
            # If PATCH is unsupported (some API versions use POST /confirm), fallback to POST
            if response.status_code in (404, 405):
                logger.info(
                    "PATCH returned %d, falling back to POST /bookings/%s/confirm",
                    response.status_code,
                    booking_id,
                )
                confirm_endpoint = f"{self.base_url}/bookings/{booking_id}/confirm"
                response = await client.post(
                    confirm_endpoint,
                    json=payload,
                    params=params,
                    headers=self._build_headers(),
                    timeout=self.timeout,
                )

            response.raise_for_status()
            data = response.json()
            logger.info("Successfully confirmed Cal.com booking id=%s", booking_id)
            return data

        except httpx.TimeoutException as exc:
            logger.error("Timeout confirming Cal.com booking id=%s: %s", booking_id, exc)
            return {
                "status": "error",
                "error_type": "timeout",
                "message": f"Cal.com request timed out while confirming booking {booking_id}",
                "booking_id": booking_id,
            }
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP %d error confirming booking %s on Cal.com: %s",
                exc.response.status_code,
                booking_id,
                exc.response.text,
            )
            return {
                "status": "error",
                "error_type": "http_error",
                "status_code": exc.response.status_code,
                "message": exc.response.text,
                "booking_id": booking_id,
            }
        except Exception as exc:
            logger.error(
                "Unexpected error confirming booking %s on Cal.com: %s",
                booking_id,
                exc,
                exc_info=True,
            )
            return {
                "status": "error",
                "error_type": "unexpected_error",
                "message": str(exc),
                "booking_id": booking_id,
            }

    async def check_connection(self) -> dict[str, Any]:
        """Test Cal.com connection and API key validity."""
        if not self.api_key:
            return {
                "connected": False,
                "configured": False,
                "base_url": self.base_url,
                "message": "Cal.com API key is not configured.",
                "event_types_count": 0,
            }

        endpoint = f"{self.base_url}/event-types"
        params: dict[str, str] = {"apiKey": self.api_key}
        client = await self._get_client()
        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._build_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                event_types = (
                    data.get("event_types")
                    or data.get("eventTypes")
                    or (data if isinstance(data, list) else [])
                )
                return {
                    "connected": True,
                    "configured": True,
                    "base_url": self.base_url,
                    "event_types_count": len(event_types),
                    "message": "Successfully connected to Cal.com API.",
                }
            return {
                "connected": False,
                "configured": True,
                "base_url": self.base_url,
                "status_code": response.status_code,
                "message": f"Cal.com returned status {response.status_code}: {response.text}",
                "event_types_count": 0,
            }
        except httpx.TimeoutException:
            return {
                "connected": False,
                "configured": True,
                "base_url": self.base_url,
                "message": "Cal.com request timed out.",
                "event_types_count": 0,
            }
        except Exception as exc:
            return {
                "connected": False,
                "configured": True,
                "base_url": self.base_url,
                "message": str(exc),
                "event_types_count": 0,
            }

    async def get_event_types(self) -> list[dict[str, Any]]:
        """Fetch configured event types and booking links from Cal.com.

        Returns:
            A list of event type dictionaries or empty list on error.
        """
        endpoint = f"{self.base_url}/event-types"
        params: dict[str, str] = {}
        if self.api_key:
            params["apiKey"] = self.api_key

        client = await self._get_client()
        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._build_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                raw = data.get("event_types") or data.get("eventTypes") or []
            elif isinstance(data, list):
                raw = data
            else:
                raw = []

            results: list[dict[str, Any]] = []
            for item in raw:
                if isinstance(item, dict):
                    results.append({
                        "id": item.get("id"),
                        "title": item.get("title") or item.get("name", "Event"),
                        "slug": item.get("slug", ""),
                        "length": item.get("length", 30),
                        "description": item.get("description", ""),
                        "scheduling_url": item.get("url") or f"https://cal.com/{item.get('slug', '')}",
                    })
            return results
        except Exception as exc:
            logger.error("Failed to fetch event types from Cal.com: %s", exc)
            return []

    def get_embed_config(
        self,
        cal_link: str,
        theme: str = "auto",
        layout: str = "month_view",
    ) -> dict[str, Any]:
        """Generate embed configuration and snippets for Cal.com headless / embed integration.

        Args:
            cal_link: Cal.com username/slug e.g. "acme/30min" or full URL.
            theme: Embed theme ("light", "dark", or "auto").
            layout: Preferred layout ("month_view", "week_view", "column_view").

        Returns:
            Dictionary containing iframe_url, js_snippet, and embed metadata.
        """
        clean_link = cal_link.replace("https://cal.com/", "").strip("/")
        base_embed_url = f"https://cal.com/{clean_link}"
        iframe_src = f"{base_embed_url}?embed=true&layout={layout}&theme={theme}"
        js_embed = (
            f'<div style="width:100%;height:100%;min-height:650px;overflow:scroll" id="cal-embed-{clean_link.replace("/", "-")}">'
            f'</div>\n'
            f'<script type="text/javascript">\n'
            f'(function (C, A, L) {{ let p = function (a, ar) {{ a.q.push(ar); }}; let d = C.document; C.Cal = C.Cal || function () {{ let cal = C.Cal; let ar = arguments; if (!cal.loaded) {{ cal.ns = {{}}; cal.q = cal.q || []; d.head.appendChild(d.createElement("script")).src = A; cal.loaded = true; }} if (ar[0] === L) {{ const api = function () {{ p(api, arguments); }}; const namespace = ar[1]; api.q = api.q || []; if(typeof namespace === "string"){{cal.ns[namespace] = cal.ns[namespace] || api;p(cal.ns[namespace], ar);p(cal, ["initNamespace", namespace]);}} else p(cal, ar); return; }} p(cal, ar); }}; }})(window, "https://app.cal.com/embed/embed.js", "init");\n'
            f'Cal("init", "{clean_link}", {{origin: "https://cal.com"}});\n'
            f'Cal.ns["{clean_link}"]("inline", {{elementOrSelector: "#cal-embed-{clean_link.replace("/", "-")}", calLink: "{clean_link}", layout: "{layout}"}});\n'
            f'Cal.ns["{clean_link}"]("ui", {{"styles":{{"branding":{{"brandColor":"#000000"}}}},"hideEventTypeDetails":false,"layout":"{layout}"}});\n'
            f'</script>'
        )

        return {
            "cal_link": clean_link,
            "embed_url": base_embed_url,
            "iframe_url": iframe_src,
            "js_snippet": js_embed,
            "layout": layout,
            "theme": theme,
        }

