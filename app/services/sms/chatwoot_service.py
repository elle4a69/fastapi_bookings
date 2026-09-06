"""Retired legacy Chatwoot sender.

Package D owns all FastAPI-originated Chatwoot delivery through the outbound
intent gateway. This module cannot inspect legacy binding credentials or make
a network request.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models.sms_conversation import SmsConversation

LEGACY_OUTBOUND_RETIRED_DETAIL = "Legacy Chatwoot outbound is retired."


async def send_chatwoot_message(
    db: Session,
    conversation: SmsConversation,
    body: str,
) -> int:
    """Fail closed without inspecting inputs or constructing an HTTP call."""
    del db, conversation, body
    raise RuntimeError(LEGACY_OUTBOUND_RETIRED_DETAIL)


def process_chatwoot_webhook(
    db: Session, payload: dict, token: str | None
) -> dict:
    """Fail closed for callers of the retired token-authenticated processor."""
    del db, payload, token
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Legacy Chatwoot webhook is retired.",
    )
