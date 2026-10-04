"""Server-only creation of GPT-Live WebRTC sessions."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

import httpx

from ....core.config import settings


class GPTLiveConfigurationError(RuntimeError):
    """Raised when the server lacks the project-scoped OpenAI credential."""


class GPTLiveInvalidSdpError(RuntimeError):
    """Raised when the browser's or provider's SDP is malformed or oversized."""


class GPTLiveProviderUnavailableError(RuntimeError):
    """Raised when OpenAI cannot create a valid GPT-Live session."""


@dataclass(frozen=True)
class GPTLiveSession:
    """The opaque session identifier and WebRTC answer returned to the browser."""

    session_id: str
    sdp: str


RequestSender = Callable[[httpx.Request, float], httpx.Response]
_CONFIG_PATH = Path(__file__).with_name("session_config.json")


def load_session_config() -> dict[str, Any]:
    """Load the handoff configuration without adding defaults or overrides."""
    with _CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def validate_sdp(sdp: str, max_bytes: int, *, provider_answer: bool = False) -> None:
    """Apply a small RFC 4566 boundary before accepting or forwarding SDP."""
    try:
        encoded = sdp.encode("utf-8") if isinstance(sdp, str) else b""
    except UnicodeEncodeError as exc:
        raise GPTLiveInvalidSdpError("The SDP is not valid UTF-8 text.") from exc

    if not encoded or len(encoded) > max_bytes:
        message = "The provider returned an invalid SDP answer." if provider_answer else "The browser SDP offer is invalid or too large."
        raise GPTLiveInvalidSdpError(message)

    lines = [line.strip() for line in sdp.splitlines() if line.strip()]
    if not lines or not any(line == "v=0" for line in lines):
        message = "The provider returned an SDP answer without v=0." if provider_answer else "The browser SDP offer is missing v=0."
        raise GPTLiveInvalidSdpError(message)


def _send_request(request: httpx.Request, timeout_seconds: float) -> httpx.Response:
    with httpx.Client(timeout=timeout_seconds) as client:
        return client.send(request)


class GPTLiveRuntime:
    """Create GPT-Live sessions with an API key that never leaves the server."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float,
        max_sdp_bytes: int,
        request_sender: RequestSender = _send_request,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self.max_sdp_bytes = max_sdp_bytes
        self._request_sender = request_sender

    @classmethod
    def from_settings(cls) -> "GPTLiveRuntime":
        api_key = settings.OPENAI_API_KEY.strip()
        if not api_key:
            raise GPTLiveConfigurationError("GPT-Live requires a server-side OpenAI project API key.")
        return cls(
            api_key=api_key,
            timeout_seconds=settings.BUSINESS_ASSISTANT_TURN_TIMEOUT_SECONDS,
            max_sdp_bytes=settings.BUSINESS_ASSISTANT_REALTIME_SDP_MAX_BYTES,
        )

    def create_session(self, offer_sdp: str) -> GPTLiveSession:
        """POST the unmodified handoff session configuration and one WebRTC offer."""
        validate_sdp(offer_sdp, self.max_sdp_bytes)
        request = self._build_create_request(offer_sdp)
        try:
            response = self._request_sender(request, self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GPTLiveProviderUnavailableError("GPT-Live could not create a voice session.") from exc
        return self._parse_response(payload)

    def _build_create_request(self, offer_sdp: str) -> httpx.Request:
        """Build the provider request without performing I/O or exposing credentials."""
        return httpx.Request(
            "POST",
            "https://api.openai.com/v1/live/sessions",
            json={
                "session": load_session_config(),
                "transport": {"type": "webrtc", "sdp": offer_sdp},
            },
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    def _parse_response(self, payload: Any) -> GPTLiveSession:
        if not isinstance(payload, dict):
            raise GPTLiveProviderUnavailableError("GPT-Live returned an invalid session response.")
        session = payload.get("session")
        transport = payload.get("transport")
        session_id = session.get("id") if isinstance(session, dict) else None
        sdp = transport.get("sdp") if isinstance(transport, dict) else None
        transport_type = transport.get("type") if isinstance(transport, dict) else None
        if not isinstance(session_id, str) or not session_id or transport_type != "webrtc" or not isinstance(sdp, str):
            raise GPTLiveProviderUnavailableError("GPT-Live returned an incomplete WebRTC session response.")
        try:
            validate_sdp(sdp, self.max_sdp_bytes, provider_answer=True)
        except GPTLiveInvalidSdpError as exc:
            raise GPTLiveProviderUnavailableError("GPT-Live returned an invalid WebRTC answer.") from exc
        return GPTLiveSession(session_id=session_id, sdp=sdp)
