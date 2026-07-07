"""Pydantic schemas for notifications, reminders and local dispatch logs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationBase(BaseModel):
    booking_id: Optional[int] = Field(None, description="Associated booking identifier")
    recipient_email: Optional[str] = Field(None, description="Recipient email")
    type: str = Field("email", description="Notification type (email, sms, push)")
    status: str = Field("pending", description="Delivery status")
    content: Optional[str] = Field(None, description="Notification content")


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    booking_id: Optional[int] = None
    recipient_email: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    content: Optional[str] = None


class NotificationInDBBase(NotificationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Notification(NotificationInDBBase):
    pass


class NotificationListResponse(BaseModel):
    ok: bool
    data: list[Notification]
    meta: dict


class NotificationResponse(BaseModel):
    ok: bool
    data: Notification


# --- Notification Templates ---

class NotificationTemplateBase(BaseModel):
    code: str
    name: str
    channel: str = "email"
    subject: Optional[str] = None
    body: str
    locale: str = "en"
    active: bool = True


class NotificationTemplateCreate(NotificationTemplateBase):
    pass


class NotificationTemplateUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    channel: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    locale: Optional[str] = None
    active: Optional[bool] = None


class NotificationTemplate(NotificationTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificationTemplateResponse(BaseModel):
    ok: bool
    data: NotificationTemplate


class NotificationTemplateListResponse(BaseModel):
    ok: bool
    data: list[NotificationTemplate]
    meta: dict


# --- Reminder Rules ---

class ReminderRuleBase(BaseModel):
    name: str
    event_type: str = "booking.start"
    channel: str = "email"
    audience: str = "client"
    timing: str = "before"
    offset_minutes: int = 1440
    template_id: Optional[int] = None
    active: bool = True
    conditions_json: Optional[str] = None


class ReminderRuleCreate(ReminderRuleBase):
    pass


class ReminderRuleUpdate(BaseModel):
    name: Optional[str] = None
    event_type: Optional[str] = None
    channel: Optional[str] = None
    audience: Optional[str] = None
    timing: Optional[str] = None
    offset_minutes: Optional[int] = None
    template_id: Optional[int] = None
    active: Optional[bool] = None
    conditions_json: Optional[str] = None


class ReminderRule(ReminderRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReminderRuleResponse(BaseModel):
    ok: bool
    data: ReminderRule


class ReminderRuleListResponse(BaseModel):
    ok: bool
    data: list[ReminderRule]
    meta: dict


class ReminderPreviewRequest(BaseModel):
    template_id: Optional[int] = None
    template_code: Optional[str] = None
    rule_id: Optional[int] = None
    booking_id: Optional[int] = None
    client_id: Optional[int] = None
    channel: Optional[str] = None
    context: dict = Field(default_factory=dict)
    recipient: Optional[str] = None


class ReminderPreview(BaseModel):
    channel: str
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body: str
    context: dict
    template_id: Optional[int] = None
    rule_id: Optional[int] = None
    placeholder_only: bool = True


class ReminderPreviewResponse(BaseModel):
    ok: bool
    data: ReminderPreview


# --- Notification Logs ---

class NotificationLogBase(BaseModel):
    notification_id: Optional[int] = None
    outbox_event_id: Optional[int] = None
    template_id: Optional[int] = None
    rule_id: Optional[int] = None
    booking_id: Optional[int] = None
    client_id: Optional[int] = None
    channel: str = "email"
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    status: str = "queued"
    provider: str = "local-placeholder"
    gateway_response: Optional[str] = None
    dispatched_at: Optional[datetime] = None


class NotificationLog(NotificationLogBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificationLogListResponse(BaseModel):
    ok: bool
    data: list[NotificationLog]
    meta: dict


class NotificationLogResponse(BaseModel):
    ok: bool
    data: NotificationLog


class NotificationQueueItem(BaseModel):
    id: int
    type: str
    payload: dict | None = None
    processed: bool
    created_at: datetime
    processed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class NotificationQueueResponse(BaseModel):
    ok: bool
    data: list[NotificationQueueItem]
    meta: dict


# --- Device Tokens ---

class DeviceTokenBase(BaseModel):
    client_id: Optional[int] = None
    user_id: Optional[int] = None
    token: str
    platform: Optional[str] = None
    device_id: Optional[str] = None
    enabled: bool = True


class DeviceTokenCreate(DeviceTokenBase):
    pass


class DeviceTokenUpdate(BaseModel):
    platform: Optional[str] = None
    device_id: Optional[str] = None
    enabled: Optional[bool] = None


class DeviceToken(DeviceTokenBase):
    id: int
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DeviceTokenResponse(BaseModel):
    ok: bool
    data: DeviceToken


class DeviceTokenListResponse(BaseModel):
    ok: bool
    data: list[DeviceToken]
    meta: dict


# --- Notification Preferences ---

class NotificationPreferenceBase(BaseModel):
    email_enabled: bool = True
    sms_enabled: bool = True
    push_enabled: bool = True
    reminders_enabled: bool = True
    marketing_enabled: bool = False


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    reminders_enabled: Optional[bool] = None
    marketing_enabled: Optional[bool] = None


class NotificationPreference(NotificationPreferenceBase):
    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceResponse(BaseModel):
    ok: bool
    data: NotificationPreference