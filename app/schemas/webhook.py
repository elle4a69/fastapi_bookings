"""Schemas for webhook registrations."""

from datetime import datetime
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global


def validate_webhook_target_url(value: str) -> str:
    """Accept only direct HTTPS destinations resolving exclusively to public IPs."""
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Webhook target_url must be a direct HTTPS URL without credentials, query, or fragment")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Webhook target_url must not target a local address")
    try:
        addresses = {result[4][0] for result in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("Webhook target_url host could not be resolved") from exc
    if not addresses or not all(_is_public_address(address) for address in addresses):
        raise ValueError("Webhook target_url must resolve only to public addresses")
    return value


class WebhookBase(BaseModel):
    event: str
    target_url: str
    secret: Optional[str] = None
    is_active: bool = True

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, value: str) -> str:
        return validate_webhook_target_url(value)


class WebhookCreate(WebhookBase):
    secret: str

    @field_validator("secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value.strip()) < 32:
            raise ValueError("Webhook secret must be at least 32 non-whitespace characters")
        return value


class WebhookUpdate(BaseModel):
    event: Optional[str] = None
    target_url: Optional[str] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, value: Optional[str]) -> Optional[str]:
        return validate_webhook_target_url(value) if value is not None else value

    @model_validator(mode="after")
    def validate_secret_update(self):
        if "secret" in self.model_fields_set and (
            not self.secret or len(self.secret.strip()) < 32
        ):
            raise ValueError("Webhook secret must be at least 32 non-whitespace characters")
        return self


class WebhookSecretRotate(BaseModel):
    secret: str

    @field_validator("secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value.strip()) < 32:
            raise ValueError("Webhook secret must be at least 32 non-whitespace characters")
        return value


class WebhookOut(BaseModel):
    id: int
    event: str
    target_url: str
    is_active: bool
    has_secret: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WebhookListResponse(BaseModel):
    ok: bool
    data: list[WebhookOut]


class WebhookResponse(BaseModel):
    ok: bool
    data: WebhookOut
