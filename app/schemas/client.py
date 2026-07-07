"""Pydantic schemas for clients."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ClientBase(BaseModel):
    name: Optional[str] = Field(None, description="Client's full name")
    email: Optional[str] = Field(None, description="Client's email address")
    phone: Optional[str] = Field(None, description="Client's phone number")
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    accepts_marketing: bool = False
    notes: Optional[str] = None
    active: bool = True


class ClientCreate(ClientBase):
    pass


class PublicClientRegister(BaseModel):
    name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    password: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    accepts_marketing: bool = False
    accept_terms: bool = False
    accept_privacy: bool = False


class PublicClientLogin(BaseModel):
    email: str
    password: Optional[str] = None


class PublicClientProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    accepts_marketing: Optional[bool] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    accepts_marketing: Optional[bool] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class ClientInDBBase(ClientBase):
    id: int
    created_at: datetime
    terms_accepted_at: Optional[datetime] = None
    privacy_accepted_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class Client(ClientInDBBase):
    pass


class ClientAuthResponse(BaseModel):
    ok: bool
    data: dict


class ClientListResponse(BaseModel):
    ok: bool
    data: list[Client]
    meta: dict


class ClientResponse(BaseModel):
    ok: bool
    data: Client


class ClientResponse(BaseModel):
    ok: bool
    data: Client