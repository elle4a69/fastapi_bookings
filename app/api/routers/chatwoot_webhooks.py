"""Public, authenticated Chatwoot account-webhook endpoint."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import get_db
from ...models.sms_chatwoot import ChatwootConnection
from ...services.messaging.chatwoot_ingress import process_authenticated_event
from ...services.messaging.chatwoot_security import (
    SigningSecretUnavailable,
    decrypt_signing_secret,
    parse_timestamp,
    signature_is_well_formed,
    timestamp_is_fresh,
    verify_signature,
)
from ...services.messaging.contracts import (
    InvalidChatwootPayload,
    parse_chatwoot_payload,
)


router = APIRouter(
    prefix="/messaging/chatwoot/webhooks", tags=["messaging-chatwoot-webhooks"]
)

MAX_WEBHOOK_BODY_BYTES = 1024 * 1024
_AUTHENTICATION_FAILED = "Webhook authentication failed."
_INVALID_PAYLOAD = "Invalid webhook payload."
_DUMMY_SIGNING_SECRET = "chatwoot-invalid-connection-timing-placeholder"
logger = logging.getLogger(__name__)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_AUTHENTICATION_FAILED,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _reject_nonstandard_json(_value: str):
    raise ValueError("non-standard JSON constant")


async def _read_bounded_raw_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_INVALID_PAYLOAD,
            ) from exc
        if declared_length < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_INVALID_PAYLOAD,
            )
        if declared_length > MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Webhook payload is too large.",
            )

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Webhook payload is too large.",
            )
        body.extend(chunk)
    return bytes(body)


@router.post("/{connection_public_id}", status_code=status.HTTP_202_ACCEPTED)
async def receive_chatwoot_webhook(
    connection_public_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    signature_header = request.headers.get("X-Chatwoot-Signature")
    timestamp_header = request.headers.get("X-Chatwoot-Timestamp")
    delivery_header = request.headers.get("X-Chatwoot-Delivery")
    if (
        not signature_is_well_formed(signature_header)
        or timestamp_header is None
        or delivery_header is None
    ):
        raise _unauthorized()

    try:
        timestamp_seconds, webhook_timestamp = parse_timestamp(timestamp_header)
    except ValueError as exc:
        raise _unauthorized() from exc
    if not timestamp_is_fresh(timestamp_seconds, _utc_now()):
        raise _unauthorized()

    raw_body = await _read_bounded_raw_body(request)

    try:
        public_id = UUID(connection_public_id)
    except (ValueError, TypeError, AttributeError):
        public_id = UUID(int=0)
    connection = (
        db.query(ChatwootConnection)
        .filter(ChatwootConnection.public_id == public_id)
        .first()
    )

    signing_secret = _DUMMY_SIGNING_SECRET
    secret_available = False
    if connection is not None and connection.enabled:
        try:
            signing_secret = decrypt_signing_secret(
                connection._signing_secret_ciphertext
            )
            secret_available = True
        except SigningSecretUnavailable:
            pass

    signature_valid = verify_signature(
        secret=signing_secret,
        timestamp_header=timestamp_header,
        raw_body=raw_body,
        signature_header=signature_header,
    )
    if not secret_available or not signature_valid:
        raise _unauthorized()

    # From this point onward the request is authenticated to a known, enabled
    # connection. Delivery and JSON validation deliberately happen afterwards.
    try:
        delivery_id = UUID(delivery_header)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_INVALID_PAYLOAD,
        ) from exc

    try:
        decoded = json.loads(
            raw_body,
            parse_constant=_reject_nonstandard_json,
        )
        event = parse_chatwoot_payload(
            decoded,
            webhook_timestamp=webhook_timestamp,
        )
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        InvalidChatwootPayload,
        ValueError,
        OverflowError,
        RecursionError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_INVALID_PAYLOAD,
        ) from exc

    if event.account_id != connection.chatwoot_account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook account does not match.",
        )

    try:
        process_authenticated_event(
            db,
            connection=connection,
            delivery_id=delivery_id,
            event=event,
            webhook_timestamp=webhook_timestamp,
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error("chatwoot_webhook_projection_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed.",
        ) from None
    return {"status": "accepted"}
