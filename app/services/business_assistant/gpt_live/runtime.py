"""Server-only creation of GPT-Live WebRTC sessions."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Callable

import httpx

from ....core.config import settings

logger = logging.getLogger(__name__)


GPT_LIVE_APP_INSTRUCTIONS = (
    "\n\nYou are the authoritative Business Assistant for FastAPI Bookings, directly connected to the user's live web application "
    "with real, active control over the dashboard and available tools to navigate, inspect, update, and diagnose business settings, "
    "services, and onboarding steps.\n"
    "You have the following operational tools available:\n"
    "- `stage_fields(step_id, fields)`: Stage candidate field values in the user's active form on screen "
    "(e.g. business_name, email, phone, address in business settings, or name, duration, price in services). "
    "Staging is visible in the UI immediately without prematurely committing to the database.\n"
    "- `validate_form(form_id)`: Validate staged fields before saving.\n"
    "- `save_form(form_id, nonce)` or `commit_save(step_id, nonce)`: Authoritatively commit and persist validated fields to the database.\n"
    "- `highlight_field(field_name, reason)`: Point visually to an input field in the user's UI.\n"
    "- `point_to_control(control_id, message)`: Direct visual user focus to a specific dashboard button or control.\n"
    "- `navigate_route(route, subtab)`: Switch the user's UI to a specific route and subtab (e.g. '/admin/settings/business' or '/admin/catalog/services').\n"
    "- `diagnostic_report()` or `run_diagnostic_check()`: Execute active system health checks and report operational status.\n"
    "- `get_onboarding_status()`: Retrieve current progress across all onboarding domains.\n"
    "- `list_services()`: List existing services configured in the system.\n"
    "- `read_system_settings()`: Read current tenant settings.\n\n"
    "When the user asks to change, update, or set their business name, contact info, hours, or services, or run diagnostics, "
    "NEVER claim you do not have access or control over the dashboard. Never tell the user to look in an 'app drawer' or external drawer. "
    "Use `navigate_route` to open the relevant page, `stage_fields` to populate their inputs, `save_form` or `commit_save` when they confirm, "
    "and execute diagnostic checks directly while providing the verdict and summary in the conversation.\n\n"
    "Batching: the voice interface gathers related details before delegating. Stage all assembled fields in a "
    "single `stage_fields` call with `fields={...}` (never one call per field), then call `validate_form`, "
    "then `save_form`/`commit_save` only after the user confirms."
)


GPT_LIVE_DIAGNOSTIC_INSTRUCTIONS = (
    "You are operating in DIAGNOSTIC MODE as the voice relay (GPT-Live) for the authoritative Business Assistant.\n"
    "Zero conversational filler, pleasantries, or small talk. "
    "You have active dashboard control via your reasoning engine (`gpt-5.6-terra`). "
    "Immediately delegate any diagnostic question, system inspection, troubleshooting request, or user request to the reasoning model (`gpt-5.6-terra`). "
    "When delegated work returns, read back the one-line Verdict and the top status points concisely. "
    "Provide the diagnostic report and summary directly in the conversation; never refer to an 'app drawer' or external imaginary drawers."
)

TERRA_DIAGNOSTIC_INSTRUCTIONS = (
    "DIAGNOSTIC MODE IS ACTIVE. You are the internal system investigator (GPT-5.6-Terra) for FastAPI Bookings with full dashboard and tool authority.\n"
    "When asked for a system diagnostic report, troubleshooting assistance, or when diagnosing errors, execute the 8-step runbook using `diagnostic_report`:\n"
    "1. Session/transport/models/delegation config & session liveness\n"
    "2. Attached tool inventory vs expected set (navigate_route, stage_fields, validate_form, save_form, commit_save, highlight_field, get_onboarding_status, list_services, read_system_settings)\n"
    "3. Tool-call log (last 10 calls: name, sanitized args, status, error)\n"
    "4. UI & executor state: current route, form adapter registered, executor lease, manual takeover, staged fields\n"
    "5. Navigation allowlist check & last navigation result\n"
    "6. Onboarding plan status, pending nonces, last save result/error\n"
    "7. Recent backend OpenAI/tool errors & voice concurrency state\n"
    "8. Current user's role and write permissions\n\n"
    "Never refer the user to an 'app drawer' or external drawers; present the structured report directly in the conversation.\n"
    "Output format MUST follow this exact structure:\n"
    "- **Verdict**: One line (Working / Degraded / Broken)\n"
    "- **Working**: Summary of functioning subsystems\n"
    "- **Not working**: Exact failed checks, evidence, and likely causes (or 'None' if all healthy)\n"
    "- **Cannot do**: Explicit boundary (no shell, no source code, no direct DB/git/infra access)\n"
    "- **Next step**: Recommended action or offer to draft a maintenance ticket (create_maintenance_handoff).\n\n"
    "When any tool fails or is unavailable, you must explain what you tried and what failed in plain language. Never hang or go silent."
)


def build_gpt_live_session_config(
    *,
    diagnostic_mode: bool = False,
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the production or diagnostic GPT-Live session configuration with live UI and onboarding tools."""
    config = copy.deepcopy(base_config if base_config is not None else load_session_config())

    from ..tool_registry import VOICE_BUSINESS_ASSISTANT_TOOLS

    realtime_tools: list[dict[str, Any]] = []

    for tool in VOICE_BUSINESS_ASSISTANT_TOOLS:
        fn = tool.get("function", {})
        tool_name = fn.get("name")
        if not diagnostic_mode and tool_name == "diagnostic_report":
            continue
        realtime_tools.append({
            "type": "function",
            "name": tool_name,
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {}),
        })

    # Zero tools at root. All operational function tools belong in delegation.responses.tools.
    config.pop("tools", None)

    if diagnostic_mode:
        config["instructions"] = GPT_LIVE_DIAGNOSTIC_INSTRUCTIONS
    else:
        config["instructions"] = config.get("instructions", "")

    if "delegation" in config and isinstance(config["delegation"], dict):
        delegation_resp = config["delegation"].get("responses")
        if isinstance(delegation_resp, dict):
            if diagnostic_mode:
                delegation_resp["instructions"] = TERRA_DIAGNOSTIC_INSTRUCTIONS + "\n\n" + GPT_LIVE_APP_INSTRUCTIONS
            else:
                delegation_resp["instructions"] = (
                    delegation_resp.get("instructions", "")
                    + GPT_LIVE_APP_INSTRUCTIONS
                    + "\n\nWhen any tool fails or is unavailable, explain what you tried and what failed in plain language. Never hang or go silent."
                )
            delegation_resp["tool_choice"] = "auto"
            existing_tools = delegation_resp.get("tools", [])
            web_search_tools = [t for t in existing_tools if isinstance(t, dict) and t.get("type") == "web_search"]
            delegation_resp["tools"] = [*web_search_tools, *realtime_tools]

    return config


class GPTLiveConfigurationError(RuntimeError):
    """Raised when the server lacks the project-scoped OpenAI credential."""


class GPTLiveInvalidSdpError(RuntimeError):
    """Raised when the browser's or provider's SDP is malformed or oversized."""


class GPTLiveProviderUnavailableError(RuntimeError):
    """Raised when OpenAI cannot create a valid GPT-Live session."""

    def __init__(
        self,
        message: str,
        *,
        provider_status: int | None = None,
        provider_code: str | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_status = provider_status
        self.provider_code = provider_code
        self.provider_request_id = provider_request_id


@dataclass(frozen=True)
class GPTLiveSession:
    """The opaque session identifier and WebRTC answer returned to the browser."""

    session_id: str
    sdp: str


_ALLOWED_GPT_LIVE_SESSION_KEYS = frozenset({"model", "instructions", "delegation", "audio"})
_ALLOWED_DELEGATION_RESPONSES_KEYS = frozenset({"model", "instructions", "parallel_tool_calls", "reasoning", "tools", "tool_choice"})


def sanitize_gpt_live_session_payload(session_config: dict[str, Any]) -> dict[str, Any]:
    """Sanitize outbound session payload to adhere strictly to OpenAI Live API schema.

    OpenAI's POST /v1/live/sessions strictly rejects top-level 'tools', 'modalities',
    'native_tools', 'voice', etc. with HTTP 400 (code: 'unknown_parameter').
    Voice configuration in OpenAI Live API is configured under 'audio.output.voice'.
    All operational function tools reside strictly inside 'delegation.responses.tools'.
    """
    config = copy.deepcopy(session_config)

    # 1. Ensure root has NO tools
    config.pop("tools", None)

    # 2. Extract and map top-level voice to audio.output.voice
    voice = config.pop("voice", None)
    if voice:
        if "audio" not in config or not isinstance(config.get("audio"), dict):
            config["audio"] = {"output": {"voice": voice}}
        else:
            output = config["audio"].setdefault("output", {})
            if isinstance(output, dict):
                output.setdefault("voice", voice)

    # 3. Sanitize delegation structure and tools
    delegation = config.get("delegation")
    if isinstance(delegation, dict):
        responses = delegation.get("responses")
        if isinstance(responses, dict):
            # Format and sanitize all tools strictly as valid OpenAI definitions
            sanitized_tools: list[dict[str, Any]] = []
            for t in responses.get("tools", []):
                if not isinstance(t, dict):
                    continue
                tool_type = t.get("type")
                if tool_type == "web_search":
                    sanitized_tools.append({"type": "web_search"})
                elif tool_type == "function":
                    fn_name = t.get("name")
                    if not fn_name:
                        continue
                    params = t.get("parameters")
                    if not isinstance(params, dict):
                        params = {"type": "object", "properties": {}}
                    sanitized_tools.append({
                        "type": "function",
                        "name": str(fn_name),
                        "description": str(t.get("description", "")),
                        "parameters": params,
                    })
            responses["tools"] = sanitized_tools

            # Filter delegation response keys strictly
            delegation["responses"] = {
                k: v for k, v in responses.items() if k in _ALLOWED_DELEGATION_RESPONSES_KEYS and v is not None
            }

    # 4. Allowlist top-level session keys strictly
    return {k: v for k, v in config.items() if k in _ALLOWED_GPT_LIVE_SESSION_KEYS and v is not None}


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

    def create_session(
        self,
        offer_sdp: str,
        *,
        session_config: dict[str, Any] | None = None,
    ) -> GPTLiveSession:
        """POST the session configuration and one WebRTC offer."""
        validate_sdp(offer_sdp, self.max_sdp_bytes)
        request = self._build_create_request(offer_sdp, session_config=session_config)
        try:
            response = self._request_sender(request, self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "GPT-Live provider HTTP %s error: request_id=%s, body=%s",
                exc.response.status_code,
                exc.response.headers.get("x-request-id"),
                exc.response.text,
            )
            raise self._provider_error_from_response(exc.response) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("GPT-Live connection or parse error: %s", exc)
            raise GPTLiveProviderUnavailableError("GPT-Live could not create a voice session.") from exc
        return self._parse_response(payload)

    @staticmethod
    def _provider_error_from_response(response: httpx.Response) -> GPTLiveProviderUnavailableError:
        """Retain only safe provider diagnostics; never return the provider body verbatim."""
        provider_code: str | None = None
        try:
            payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            code = error.get("code") if isinstance(error, dict) else None
            if isinstance(code, str) and code:
                provider_code = code
        except ValueError:
            pass

        request_id = response.headers.get("x-request-id")
        return GPTLiveProviderUnavailableError(
            "GPT-Live could not create a voice session.",
            provider_status=response.status_code,
            provider_code=provider_code,
            provider_request_id=request_id,
        )

    def _build_create_request(
        self,
        offer_sdp: str,
        *,
        session_config: dict[str, Any] | None = None,
    ) -> httpx.Request:
        """Build the provider request without performing I/O or exposing credentials."""
        raw_config = session_config if session_config is not None else load_session_config()
        config = sanitize_gpt_live_session_payload(raw_config)
        return httpx.Request(
            "POST",
            "https://api.openai.com/v1/live/sessions",
            json={
                "session": config,
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
