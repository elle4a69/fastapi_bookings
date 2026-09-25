"""Pydantic models for internal users."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    company: str = Field(..., description="Company name")
    login: str = Field(..., description="Login username")
    role: str = Field("owner", description="Role of the user")
    provider_id: Optional[int] = Field(None, description="Linked provider ID for provider role")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="User password")


class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    provider_id: Optional[int] = None


class UserInDBBase(UserBase):
    id: int
    provider_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class User(UserInDBBase):
    pass


class UserListResponse(BaseModel):
    ok: bool
    data: list[User]
    meta: dict


class UserResponse(BaseModel):
    ok: bool
    data: User