"""Server-held realtime voice SDP exchange for authenticated conversations."""

from __future__ import annotations

from typing import Any

import httpx

from ...core.config import settings
from .runtime import SYSTEM_INSTRUCTIONS
from .tool_registry import ALL_BUSINESS_ASSISTANT_TOOLS


class RealtimeConfigurationError(RuntimeError):
    """Raised when the server lacks the non-secret settings required for voice."""


class RealtimeInvalidSdpError(RuntimeError):
    """Raised when a browser offer is empty or outside the configured boundary."""


class RealtimeProviderUnavailableError(RuntimeError):
    """Raised when the upstream provider cannot establish a valid voice session."""


def build_realtime_session_config(
    *,
    product_context_text: str | None = None,
) -> dict[str, Any]:
    """Build the OpenAI Realtime session configuration including instructions and tools."""
    instructions = SYSTEM_INSTRUCTIONS
    if product_context_text and product_context_text.strip():
        instructions = f"{SYSTEM_INSTRUCTIONS}\n\n{product_context_text.strip()}"

    realtime_tools: list[dict[str, Any]] = []
    for tool in ALL_BUSINESS_ASSISTANT_TOOLS:
        fn = tool.get("function", {})
        realtime_tools.append(
            {
                "type": "function",
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            }
        )

    return {
        "instructions": instructions,
        "tools": realtime_tools,
    }


def validate_sdp(data: bytes, max_bytes: int, *, is_offer: bool = True) -> None:
    """Validate bounded SDP payload size and structural RFC 4566 compliance."""
    if not isinstance(data, (bytes, bytearray)) or not data or len(data) > max_bytes:
        if is_offer:
            raise RealtimeInvalidSdpError("The realtime SDP offer is invalid or too large.")
        raise RealtimeProviderUnavailableError("The realtime provider returned an invalid SDP answer.")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        if is_offer:
            raise RealtimeInvalidSdpError("The realtime SDP offer contains invalid non-text characters.") from exc
        raise RealtimeProviderUnavailableError("The realtime provider returned an unreadable SDP answer.") from exc

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not any(line.startswith("v=0") for line in lines):
        if is_offer:
            raise RealtimeInvalidSdpError("The realtime SDP offer is missing required version header (v=0).")
        raise RealtimeProviderUnavailableError("The realtime provider returned an SDP answer missing version header.")


class BusinessAssistantRealtimeRuntime:
    """Exchange SDP with the configured upstream without exposing its credentials."""

    def __init__(self, *, api_key: str, model_name: str, timeout_seconds: float, max_sdp_bytes: int) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self.max_sdp_bytes = max_sdp_bytes

    @classmethod
    def is_configured(cls) -> bool:
        """Return True if the server has the necessary API key and model configured."""
        api_key = settings.OPENAI_API_KEY.strip()
        model_name = settings.BUSINESS_ASSISTANT_REALTIME_MODEL.strip()
        return bool(api_key and model_name)

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
        validate_sdp(answer, self.max_sdp_bytes, is_offer=False)
        return answer

    def _build_exchange_request(self, offer: bytes) -> httpx.Request:
        """Build the provider SDP request without issuing network I/O."""
        validate_sdp(offer, self.max_sdp_bytes, is_offer=True)
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

