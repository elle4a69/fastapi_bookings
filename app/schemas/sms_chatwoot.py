from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


__all__ = [
    "ChatwootConnectionCreate",
    "ChatwootConnectionUpdate",
    "ChatwootSigningSecretRotate",
    "ChatwootConnectionResponse",
    "ChatwootInboxBindingCreate",
    "ChatwootInboxBindingUpdate",
    "ChatwootInboxBindingResponse",
]


def _canonical_instance_origin(value: str) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("instance_origin must be an absolute HTTP(S) origin")
    if parsed.username or parsed.password:
        raise ValueError("instance_origin must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("instance_origin must not contain a path, query, or fragment")

    scheme = parsed.scheme.lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("instance_origin contains an invalid port") from exc

    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    default_port = (scheme == "https" and port == 443) or (
        scheme == "http" and port == 80
    )
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    return urlunsplit((scheme, netloc, "", "", ""))


class ChatwootConnectionCreate(BaseModel):
    instance_origin: str = Field(min_length=1, max_length=2048)
    chatwoot_account_id: int = Field(gt=0)
    enabled: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("instance_origin")
    @classmethod
    def canonicalize_instance_origin(cls, value: str) -> str:
        return _canonical_instance_origin(value)


class ChatwootConnectionUpdate(BaseModel):
    enabled: Optional[bool] = None

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


class ChatwootConnectionResponse(BaseModel):
    id: int
    public_id: UUID
    tenant_id: int
    instance_origin: str
    chatwoot_account_id: int
    enabled: bool
    webhook_path: str
    has_signing_secret: bool
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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
