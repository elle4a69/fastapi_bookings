"""Pydantic schemas for identity management, Logto token exchange, and organization mapping (WP1).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LogtoTokenExchangeRequest(BaseModel):
    """Payload for exchanging or linking a Logto identity."""
    id_token: Optional[str] = Field(None, description="Logto OIDC ID token")
    access_token: Optional[str] = Field(None, description="Logto OIDC access token / organization token")
    token: Optional[str] = Field(None, description="Generic token field (either ID or access token)")
    invitation_token: Optional[str] = Field(None, description="Optional tenant invitation token to link during onboarding")


class IdentityMeOrganization(BaseModel):
    """Details of a tenant organization accessible to the user."""
    tenant_id: int
    tenant_name: str
    tenant_subdomain: str
    external_organization_id: Optional[str] = None
    role: str
    status: str = "active"


class IdentityMeResponse(BaseModel):
    """Response schema for GET /api/identity/me."""
    ok: bool = True
    user_id: int
    login: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_platform_owner: bool = False
    tenant_id: Optional[int] = None
    tenant_subdomain: Optional[str] = None
    external_subject_id: Optional[str] = None
    provider: Optional[str] = None
    organizations: List[IdentityMeOrganization] = Field(default_factory=list)


class IdentityLinkResponse(BaseModel):
    """Response schema for POST /api/identity/exchange."""
    ok: bool = True
    user_id: int
    external_subject_id: str
    provider: str = "logto"
    tenant_id: Optional[int] = None
    tenant_subdomain: Optional[str] = None
    access_token: Optional[str] = None
    token_type: str = "bearer"


class OrganizationListResponse(BaseModel):
    """Response schema for GET /api/identity/organizations."""
    ok: bool = True
    data: List[IdentityMeOrganization] = Field(default_factory=list)


class LogtoWebhookPayload(BaseModel):
    """Webhook event payload dispatched from Logto."""
    event: str = Field(..., description="Logto webhook event type (e.g. User.Created, Organization.Created)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data dictionary")
    interaction_event_id: Optional[str] = None
    created_at: Optional[str] = None
