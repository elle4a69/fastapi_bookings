"""Schemas for webhook registrations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from ..core.network_safety import assert_safe_url


class WebhookBase(BaseModel):
    event: str
    target_url: str
    is_active: bool = True

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, v: str) -> str:
        assert_safe_url(v)
        return v


class WebhookCreate(WebhookBase):
    secret: Optional[str] = None


class WebhookUpdate(BaseModel):
    event: Optional[str] = None
    target_url: Optional[str] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            assert_safe_url(v)
        return v


class WebhookOut(BaseModel):
    """Webhook registration representation for list, get, and update responses.

    Plaintext signing secret is strictly excluded to prevent credential disclosure.
    """
    id: int
    tenant_id: int
    event: str
    target_url: str
    is_active: bool = True
    has_secret: bool = False
    secret_last4: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WebhookCreateOut(WebhookOut):
    """Returned only upon initial webhook registration.

    Contains the generated/provided secret once so the administrator can copy it.
    """
    secret: Optional[str] = None


class WebhookListResponse(BaseModel):
    ok: bool
    data: list[WebhookOut]


class WebhookResponse(BaseModel):
    ok: bool
    data: WebhookOut


class WebhookCreateResponse(BaseModel):
    ok: bool
    data: WebhookCreateOut

