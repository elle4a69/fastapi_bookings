"""Server-held realtime voice SDP exchange for authenticated conversations."""

from __future__ import annotations

import httpx

from ...core.config import settings


class RealtimeConfigurationError(RuntimeError):
    """Raised when the server lacks the non-secret settings required for voice."""


class RealtimeInvalidSdpError(RuntimeError):
    """Raised when a browser offer is empty or outside the configured boundary."""


class RealtimeProviderUnavailableError(RuntimeError):
    """Raised when the upstream provider cannot establish a valid voice session."""


class BusinessAssistantRealtimeRuntime:
    """Exchange SDP with the configured upstream without exposing its credentials."""

    def __init__(self, *, api_key: str, model_name: str, timeout_seconds: float, max_sdp_bytes: int) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self.max_sdp_bytes = max_sdp_bytes

    @classmethod
    def from_settings(cls) -> "BusinessAssistantRealtimeRuntime":
        api_key = settings.OPENAI_API_KEY.strip()
        model_name = settings.BUSINESS_ASSISTANT_REALTIME_MODEL.strip()
        if not api_key or not model_name:
            raise RealtimeConfigurationError("Realtime voice configuration is incomplete.")
        return cls(
            api_key=api_key,
            model_name=model_name,
            timeout_seconds=settings.BUSINESS_ASSISTANT_TURN_TIMEOUT_SECONDS,
            max_sdp_bytes=settings.BUSINESS_ASSISTANT_REALTIME_SDP_MAX_BYTES,
        )

    def exchange_sdp(self, offer: bytes) -> bytes:
        """Perform one live, bounded SDP exchange using server-held credentials."""
        request = self._build_exchange_request(offer)
        try:
            response = httpx.request(
                request.method,
                request.url,
                content=request.content,
                headers=request.headers,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            answer = response.content
        except httpx.HTTPError as exc:
            raise RealtimeProviderUnavailableError("The realtime voice exchange failed.") from exc
        if not answer or len(answer) > self.max_sdp_bytes:
            raise RealtimeProviderUnavailableError("The realtime provider returned an invalid SDP answer.")
        return answer

    def _build_exchange_request(self, offer: bytes) -> httpx.Request:
        """Build the provider SDP request without issuing network I/O."""
        if not offer or len(offer) > self.max_sdp_bytes:
            raise RealtimeInvalidSdpError("The realtime SDP offer is invalid or too large.")
        return httpx.Request(
            "POST",
            "https://api.openai.com/v1/realtime/calls",
            params={"model": self._model_name},
            content=offer,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/sdp",
                "Accept": "application/sdp",
            },
        )
