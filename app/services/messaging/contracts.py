"""Strict, privacy-minimising contracts for Chatwoot webhook projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID


SUPPORTED_EVENTS = frozenset({"message_created", "message_updated"})
SUPPORTED_CONTENT_TYPES = frozenset({"text"})
SUPPORTED_CHANNEL_OBSERVATIONS = frozenset(
    {"Channel::WebWidget", "WebWidget", "web_widget"}
)
MAX_ATTACHMENTS = 20
MAX_ATTACHMENT_TEXT = 128
MAX_SENDER_REFERENCE = 255
MAX_REMOTE_ID = 2**63 - 1


class InvalidChatwootPayload(ValueError):
    """Raised when an authenticated payload is not structurally usable."""


@dataclass(frozen=True)
class ParsedChatwootEvent:
    event_type: str
    account_id: int
    inbox_id: int | None
    conversation_id: int | None
    message_id: int | None
    message_type: str | None
    content_type: str | None
    body: str
    private: bool
    sender_type: str | None
    sender_reference: str | None
    attachments: list[dict[str, object]]
    occurred_at: datetime
    channel_observation: str | None
    outbound_correlation_id: UUID | None = None


@dataclass(frozen=True)
class ParsedChatwootOutboundMessage:
    """Minimal verified shape required for Package D reconciliation."""

    account_id: int
    inbox_id: int
    conversation_id: int
    message_id: int
    message_type: str
    content_type: str
    private: bool
    sender_type: str
    sender_id: int
    outbound_correlation_id: UUID | None


@dataclass(frozen=True)
class NormalizedMessage:
    direction: Literal["inbound", "outbound", "system"]
    author_type: Literal["customer", "staff", "external_bot", "system"]
    body: str
    normalized_body: str | None


def _positive_int(value: Any, field: str, *, required: bool = True) -> int | None:
    if value is None and not required:
        return None
    if isinstance(value, bool):
        raise InvalidChatwootPayload(f"{field} is invalid")
    if isinstance(value, int):
        converted = value
    elif (
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
        and len(value) <= 19
    ):
        try:
            converted = int(value)
        except (ValueError, OverflowError) as exc:
            raise InvalidChatwootPayload(f"{field} is invalid") from exc
    else:
        raise InvalidChatwootPayload(f"{field} is invalid")
    if converted <= 0 or converted > MAX_REMOTE_ID:
        raise InvalidChatwootPayload(f"{field} is invalid")
    return converted


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidChatwootPayload(f"{field} is invalid")
    return value


def _bounded_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        text = str(value)
        return text[:limit]
    return None


def _safe_attachments(value: Any) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    safe: list[dict[str, object]] = []
    for raw in value[:MAX_ATTACHMENTS]:
        if not isinstance(raw, dict):
            continue
        item: dict[str, object] = {}
        for key in ("id", "file_type", "content_type"):
            bounded = _bounded_text(raw.get(key), MAX_ATTACHMENT_TEXT)
            if bounded is not None:
                item[key] = bounded
        size = raw.get("file_size")
        if isinstance(size, int) and not isinstance(size, bool) and 0 <= size <= 2**63 - 1:
            item["file_size"] = size
        if item:
            safe.append(item)
    return safe


def _occurred_at(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return fallback
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return fallback
    return fallback


def parse_outbound_correlation_id(value: Any) -> UUID | None:
    """Read exactly the namespaced opaque UUID and nothing else.

    This intentionally ignores ``source_id``, all generic content attributes,
    and any marker with extra data. A malformed marker is never trusted.
    """
    if not isinstance(value, dict):
        return None
    namespace = value.get("fastapi_bookings")
    if not isinstance(namespace, dict) or set(namespace) != {"outbound_correlation_id"}:
        return None
    marker = namespace.get("outbound_correlation_id")
    if not isinstance(marker, str) or len(marker) != 36:
        return None
    try:
        parsed = UUID(marker)
    except (ValueError, AttributeError):
        return None
    return parsed if str(parsed) == marker.lower() else None


def parse_chatwoot_payload(
    payload: Any, *, webhook_timestamp: datetime
) -> ParsedChatwootEvent:
    root = _mapping(payload, "payload")
    event_type = root.get("event")
    if not isinstance(event_type, str) or not event_type or len(event_type) > 64:
        raise InvalidChatwootPayload("event is invalid")

    account = _mapping(root.get("account"), "account")
    account_id = _positive_int(account.get("id"), "account.id")

    inbox_raw = root.get("inbox")
    inbox = _mapping(inbox_raw, "inbox") if inbox_raw is not None else {}
    conversation_raw = root.get("conversation")
    conversation = (
        _mapping(conversation_raw, "conversation")
        if conversation_raw is not None
        else {}
    )

    root_inbox_id = _positive_int(inbox.get("id"), "inbox.id", required=False)
    conversation_inbox_id = _positive_int(
        conversation.get("inbox_id"), "conversation.inbox_id", required=False
    )
    if (
        root_inbox_id is not None
        and conversation_inbox_id is not None
        and root_inbox_id != conversation_inbox_id
    ):
        raise InvalidChatwootPayload("inbox identifiers do not match")
    inbox_id = root_inbox_id or conversation_inbox_id
    conversation_account_id = _positive_int(
        conversation.get("account_id"),
        "conversation.account_id",
        required=False,
    )
    if conversation_account_id is not None and conversation_account_id != account_id:
        raise InvalidChatwootPayload("account identifiers do not match")
    conversation_id = _positive_int(
        conversation.get("id"), "conversation.id", required=False
    )
    message_id = _positive_int(root.get("id"), "id", required=False)

    if event_type in SUPPORTED_EVENTS and (
        inbox_id is None or conversation_id is None or message_id is None
    ):
        raise InvalidChatwootPayload("message identifiers are required")

    message_type = _bounded_text(root.get("message_type"), 32)
    content_type = _bounded_text(root.get("content_type"), 64)
    content = root.get("content")
    if content is None:
        body = ""
    elif isinstance(content, str):
        body = content
    else:
        raise InvalidChatwootPayload("content is invalid")

    private = root.get("private", False)
    if not isinstance(private, bool):
        raise InvalidChatwootPayload("private is invalid")

    sender_raw = root.get("sender")
    sender = _mapping(sender_raw, "sender") if sender_raw is not None else {}
    sender_type = _bounded_text(sender.get("type"), 64)
    sender_reference = _bounded_text(sender.get("id"), MAX_SENDER_REFERENCE)

    channel_observation = _bounded_text(inbox.get("channel_type"), 64)
    if channel_observation is None:
        meta = conversation.get("meta")
        if isinstance(meta, dict):
            channel_observation = _bounded_text(meta.get("channel"), 64)

    return ParsedChatwootEvent(
        event_type=event_type,
        account_id=account_id,
        inbox_id=inbox_id,
        conversation_id=conversation_id,
        message_id=message_id,
        message_type=message_type,
        content_type=content_type,
        body=body,
        private=private,
        sender_type=sender_type,
        sender_reference=sender_reference,
        attachments=_safe_attachments(root.get("attachments")),
        occurred_at=_occurred_at(root.get("created_at"), webhook_timestamp),
        channel_observation=channel_observation,
        outbound_correlation_id=parse_outbound_correlation_id(
            root.get("content_attributes")
        ),
    )


def parse_chatwoot_outbound_message(value: Any) -> ParsedChatwootOutboundMessage:
    """Validate the exact structural response/GET message shape for Package D.

    No content is retained by this contract. The content field is checked only
    for the required text-message shape.
    """
    root = _mapping(value, "message")
    account = _mapping(root.get("account"), "account")
    inbox = _mapping(root.get("inbox"), "inbox")
    conversation = _mapping(root.get("conversation"), "conversation")
    sender = _mapping(root.get("sender"), "sender")
    content = root.get("content")
    if not isinstance(content, str):
        raise InvalidChatwootPayload("content is invalid")
    message_type = _bounded_text(root.get("message_type"), 32)
    content_type = _bounded_text(root.get("content_type"), 64)
    sender_type = _bounded_text(sender.get("type"), 64)
    private = root.get("private")
    if not isinstance(private, bool):
        raise InvalidChatwootPayload("private is invalid")
    if message_type is None or content_type is None or sender_type is None:
        raise InvalidChatwootPayload("message fields are invalid")
    return ParsedChatwootOutboundMessage(
        account_id=_positive_int(account.get("id"), "account.id"),
        inbox_id=_positive_int(inbox.get("id"), "inbox.id"),
        conversation_id=_positive_int(conversation.get("id"), "conversation.id"),
        message_id=_positive_int(root.get("id"), "id"),
        message_type=message_type,
        content_type=content_type,
        private=private,
        sender_type=sender_type,
        sender_id=_positive_int(sender.get("id"), "sender.id"),
        outbound_correlation_id=parse_outbound_correlation_id(
            root.get("content_attributes")
        ),
    )


def extract_chatwoot_outbound_messages(value: Any) -> list[dict[str, Any]]:
    """Select only documented list containers for bounded GET reconciliation."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []
    for key in ("payload", "messages"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def normalize_message(event: ParsedChatwootEvent) -> NormalizedMessage:
    sender_type = (event.sender_type or "").casefold().replace("_", "")
    if event.message_type == "incoming" and sender_type == "contact":
        direction: Literal["inbound", "outbound", "system"] = "inbound"
        author_type: Literal["customer", "staff", "external_bot", "system"] = (
            "customer"
        )
    elif event.message_type == "outgoing" and sender_type == "user":
        direction = "outbound"
        author_type = "staff"
    elif event.message_type == "outgoing" and sender_type == "agentbot":
        direction = "outbound"
        author_type = "external_bot"
    else:
        direction = "system"
        author_type = "system"

    may_store_body = (
        not event.private
        and event.message_type in {"incoming", "outgoing"}
        and event.content_type in SUPPORTED_CONTENT_TYPES
        and author_type != "system"
    )
    body = event.body if may_store_body else ""
    normalized = body.strip().lower() if body else None
    return NormalizedMessage(
        direction=direction,
        author_type=author_type,
        body=body,
        normalized_body=normalized,
    )
