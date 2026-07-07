"""Schemas for webhook registrations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, HttpUrl


class WebhookBase(BaseModel):
    event: str
    target_url: str
    secret: Optional[str] = None
    is_active: bool = True


class WebhookCreate(WebhookBase):
    pass


class WebhookUpdate(BaseModel):
    event: Optional[str] = None
    target_url: Optional[str] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookOut(WebhookBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WebhookListResponse(BaseModel):
    ok: bool
    data: list[WebhookOut]


class WebhookResponse(BaseModel):
    ok: bool
    data: WebhookOut
