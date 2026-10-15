"""Pydantic schemas for Tenant Invitation contracts."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class InvitationCreate(BaseModel):
    """Payload to create a new invitation for a tenant."""
    model_config = ConfigDict(extra="ignore")

    email: str = Field(..., description="Target email of the invitee")
    role: str = Field("owner", description="Role to assign upon acceptance (e.g. 'owner', 'admin', 'staff')")
    expires_in_days: int = Field(7, ge=1, le=90, description="Validity period in days")


class InvitationAccept(BaseModel):
    """Payload to accept an invitation token."""
    model_config = ConfigDict(extra="ignore")

    token: str = Field(..., description="Single-use invitation token")
    password: Optional[str] = Field(None, min_length=6, description="Password to set for new or updated account")
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class InvitationOut(BaseModel):
    """Invitation details representation."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    email: str
    role: str
    status: str
    token: Optional[str] = None
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    created_at: datetime


class InvitationResponse(BaseModel):
    ok: bool = True
    data: InvitationOut
