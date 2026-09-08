"""Narrow client for Assistant UI's dedicated decision endpoint only."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from ...core.config import settings


REQUEST_TIMEOUT_SECONDS = 5.0
MAX_REPLY_CHARS = 2000


@dataclass(frozen=True)
class AssistantUiDecision:
    kind: str
    reply: str | None = None


def decision_service_is_configured() -> bool:
    """Require an explicit HTTPS endpoint and non-empty service credential."""
    endpoint = settings.ASSISTANT_UI_DECISION_URL.strip()
    credential = settings.ASSISTANT_UI_DECISION_CREDENTIAL.strip()
    parsed = urlsplit(endpoint)
    return bool(
        credential
        and parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


async def request_decision(*, payload: dict) -> AssistantUiDecision | None:
    """Return a validated reply/handoff decision, or None for safe handoff.

    The endpoint and credential never enter logs.  This client makes one
    request only; callers treat all failures as operator handoff.
    """
    if not decision_service_is_configured():
        return None
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            trust_env=False,
        ) as client:
            response = await client.post(
                settings.ASSISTANT_UI_DECISION_URL,
                headers={
                    "Authorization": f"Bearer {settings.ASSISTANT_UI_DECISION_CREDENTIAL}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.RequestError:
        return None
    if response.status_code < 200 or response.status_code >= 300:
        return None
    try:
        data = response.json()
        if not isinstance(data, dict) or data.get("request_id") != payload["request_id"]:
            return None
        decision = data.get("decision")
        if decision == "handoff":
            return AssistantUiDecision(kind="handoff")
        reply = data.get("reply")
        if (
            decision == "reply"
            and isinstance(reply, str)
            and reply.strip()
            and len(reply) <= MAX_REPLY_CHARS
        ):
            return AssistantUiDecision(kind="reply", reply=reply.strip())
    except (TypeError, ValueError):
        pass
    return None
