from __future__ import annotations

from datetime import datetime
import ipaddress
from typing import Literal, Optional
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from ..core.config import settings


_UNICODE_DOT_TRANSLATION = str.maketrans(
    {
        "\u3002": ".",
        "\uff0e": ".",
        "\uff61": ".",
    }
)
_INTERNAL_HOSTNAME_SUFFIXES = (
    ".localhost",
    ".local",
    ".localdomain",
    ".internal",
)


__all__ = [
    "ChatwootConnectionCreate",
    "ChatwootConnectionUpdate",
    "ChatwootSigningSecretRotate",
    "ChatwootApiTokenRotate",
    "ChatwootIntegrationSenderConfigure",
    "ChatwootConnectionResponse",
    "ChatwootInboxBindingCreate",
    "ChatwootInboxBindingUpdate",
    "ChatwootInboxBindingResponse",
]


def _canonical_https_instance_origin(value: str) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("instance_origin must be an absolute HTTPS origin")
    if parsed.username or parsed.password:
        raise ValueError("instance_origin must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("instance_origin must not contain a path, query, or fragment")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("instance_origin contains an invalid port") from exc

    hostname = parsed.hostname.translate(_UNICODE_DOT_TRANSLATION)
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("instance_origin contains an invalid hostname") from exc
    hostname = hostname.rstrip(".").lower()
    if (
        not hostname
        or hostname == "localhost"
        or hostname.endswith(_INTERNAL_HOSTNAME_SUFFIXES)
    ):
        raise ValueError("instance_origin must use a public DNS hostname")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("instance_origin must use a public DNS hostname")
    if "." not in hostname or _looks_like_numeric_ipv4(hostname):
        raise ValueError("instance_origin must use a public DNS hostname")

    default_port = port == 443
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    return urlunsplit(("https", netloc, "", "", ""))


def _looks_like_numeric_ipv4(hostname: str) -> bool:
    """Reject alternate numeric IPv4 spellings before HTTP parses them."""
    labels = hostname.split(".")
    return bool(labels) and all(_is_numeric_ipv4_label(label) for label in labels)


def _is_numeric_ipv4_label(label: str) -> bool:
    if not label:
        return False
    if label.startswith("0x"):
        return len(label) > 2 and all(
            character in "0123456789abcdef" for character in label[2:]
        )
    return label.isdecimal()


def _configured_trusted_chatwoot_origins() -> frozenset[str]:
    configured = [
        origin.strip()
        for origin in settings.CHATWOOT_TRUSTED_ORIGINS.split(",")
        if origin.strip()
    ]
    if not configured:
        return frozenset()
    try:
        return frozenset(
            _canonical_https_instance_origin(origin) for origin in configured
        )
    except ValueError:
        # A malformed deployment setting must not leave any other configured
        # origin usable by mistake.
        return frozenset()


def trusted_chatwoot_instance_origin(value: str) -> str | None:
    """Return a configured safe origin, or fail closed without logging it."""
    try:
        origin = _canonical_https_instance_origin(value)
    except (AttributeError, ValueError):
        return None
    if origin not in _configured_trusted_chatwoot_origins():
        return None
    return origin


class ChatwootConnectionCreate(BaseModel):
    instance_origin: str = Field(min_length=1, max_length=2048)
    chatwoot_account_id: int = Field(gt=0)
    enabled: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("instance_origin")
    @classmethod
    def canonicalize_instance_origin(cls, value: str) -> str:
        origin = trusted_chatwoot_instance_origin(value)
        if origin is None:
            raise ValueError(
                "instance_origin must be a configured trusted HTTPS origin"
            )
        return origin


class ChatwootConnectionUpdate(BaseModel):
    enabled: Optional[bool] = None
    outbound_enabled: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class ChatwootSigningSecretRotate(BaseModel):
    signing_secret: SecretStr = Field(min_length=32, max_length=512)

    model_config = ConfigDict(extra="forbid")

    @field_validator("signing_secret")
    @classmethod
    def reject_whitespace_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw != raw.strip() or len(raw.strip()) < 32:
            raise ValueError(
                "signing_secret must contain at least 32 non-whitespace characters"
            )
        return value


class ChatwootApiTokenRotate(BaseModel):
    api_token: SecretStr = Field(min_length=1, max_length=2048)

    model_config = ConfigDict(extra="forbid")

    @field_validator("api_token")
    @classmethod
    def reject_whitespace_token(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw != raw.strip() or not raw:
            raise ValueError("api_token must not be blank or padded")
        return value


class ChatwootIntegrationSenderConfigure(BaseModel):
    # The verified 4.15.1 API handoff returns the configured Chatwoot API
    # user. AgentBot must never be selectable as a FastAPI echo sender.
    sender_type: Literal["User"]
    sender_id: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

class ChatwootConnectionResponse(BaseModel):
    id: int
    public_id: UUID
    tenant_id: int
    instance_origin: str
    chatwoot_account_id: int
    enabled: bool
    outbound_enabled: bool
    webhook_path: str
    has_signing_secret: bool
    has_api_token: bool
    has_expected_integration_sender: bool
    outbound_ready: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatwootInboxBindingCreate(BaseModel):
    connection_id: int = Field(gt=0)
    provider_id: int = Field(gt=0)
    chatwoot_inbox_id: int = Field(gt=0)
    channel: Literal["web_widget"] = "web_widget"
    ingress_enabled: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class ChatwootInboxBindingUpdate(BaseModel):
    ingress_enabled: Optional[bool] = None
    outbound_enabled: Optional[bool] = None
    automation_enabled: Optional[bool] = None
    assistant_ui_policy_scope: Optional[str] = Field(default=None, min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")


class ChatwootInboxBindingResponse(BaseModel):
    id: int
    tenant_id: int
    connection_id: int
    provider_id: int
    chatwoot_inbox_id: int
    channel: Literal["web_widget"]
    ingress_enabled: bool
    effective_ingress_enabled: bool
    outbound_enabled: bool
    effective_outbound_enabled: bool
    automation_enabled: bool
    effective_automation_enabled: bool
    assistant_ui_policy_scope: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
