"""Pydantic models for audit logs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditLogBase(BaseModel):
    user_id: Optional[int] = Field(None, description="User who performed the action")
    action: str = Field(..., description="Name of the action performed")
    target_type: Optional[str] = Field(None, description="Type of the entity affected")
    target_id: Optional[int] = Field(None, description="Identifier of the entity affected")
    details: Optional[str] = Field(None, description="Additional details in JSON format")


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogInDBBase(AuditLogBase):
    id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


class AuditLog(AuditLogInDBBase):
    pass


class AuditLogListResponse(BaseModel):
    ok: bool
    data: list[AuditLog]
    meta: dict


class AuditLogResponse(BaseModel):
    ok: bool
    data: AuditLog