"""Pydantic schemas for the Website Builder Module."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class WebsiteConfigSchema(BaseModel):
    """Schema representing the tenant website configuration."""

    id: Optional[int] = None
    tenant_id: Optional[int] = None
    template_id: str = Field("minimalist", description="Active website template ID")
    theme_id: str = Field("ocean_slate", description="Active color theme ID")
    custom_colors: Optional[Dict[str, str]] = Field(
        None, description="Optional hex color overrides"
    )
    sections_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured sections content (hero, about, services, booking, testimonials, contact, footer)",
    )
    is_published: bool = Field(False, description="Whether the website is live")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    seo_title: Optional[str] = Field(None, description="SEO meta title")
    seo_description: Optional[str] = Field(None, description="SEO meta description")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WebsiteUpdateRequest(BaseModel):
    """Payload for updating draft website configuration."""

    template_id: Optional[str] = None
    theme_id: Optional[str] = None
    custom_colors: Optional[Dict[str, str]] = None
    sections_data: Optional[Dict[str, Any]] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None


class WebsitePublishRequest(BaseModel):
    """Payload for publishing / unpublishing website."""

    is_published: Optional[bool] = True


class WebsitePublishData(BaseModel):
    is_published: bool
    published_at: Optional[datetime] = None
    message: str


class WebsitePublishResponse(BaseModel):
    ok: bool = True
    data: WebsitePublishData


class WebsiteResponse(BaseModel):
    ok: bool = True
    data: WebsiteConfigSchema


class PublicWebsiteData(BaseModel):
    config: WebsiteConfigSchema
    tenant_name: str
    tenant_subdomain: str
    tenant_email: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_address: Optional[str] = None
    tenant_logo_url: Optional[str] = None
    services: Optional[list[Dict[str, Any]]] = None


class PublicWebsiteResponse(BaseModel):
    ok: bool = True
    data: PublicWebsiteData


class WebsiteAiGenerateRequest(BaseModel):
    """Payload for AI copy / template generation."""

    prompt: str = Field(..., description="Prompt describing the business or desired changes")
    action: Optional[str] = Field("generate_full", description="generate_full | rewrite_section | suggest_theme")
    section_key: Optional[str] = Field(None, description="Specific section key to rewrite if action is rewrite_section")
    business_type: Optional[str] = Field(None, description="Business category or industry")


class WebsiteAiGenerateResponse(BaseModel):
    ok: bool = True
    suggested_template: Optional[str] = None
    suggested_theme: Optional[str] = None
    generated_sections: Optional[Dict[str, Any]] = None
    rewritten_text: Optional[str] = None
    message: str


class WebsiteChatWidgetConfig(BaseModel):
    """Configuration for proactive chat widget & invitation callout bubble."""

    enabled: bool = Field(True, description="Whether the floating chat widget is enabled")
    invitation_title: str = Field("Need help booking?", description="Greeting header in invitation card")
    invitation_message: str = Field(
        "Hi there! 👋 Have questions about our services or need to book? Chat with us!",
        description="Friendly proactive greeting text",
    )
    invitation_delay_seconds: int = Field(3, ge=0, le=60, description="Delay in seconds before showing invitation bubble")
    show_sms_fallback: bool = Field(True, description="Whether to display direct SMS fallback button")


class WebsiteChatRequest(BaseModel):
    """Payload for visitor chat message sent via public website widget."""

    tenant_id: Optional[int] = Field(None, description="Optional tenant ID if not in header")
    visitor_name: Optional[str] = Field("Visitor", description="Visitor's name")
    visitor_contact: Optional[str] = Field(None, description="Visitor's phone number or email")
    message: str = Field(..., min_length=1, description="Message text")
    conversation_id: Optional[int] = Field(None, description="Optional existing conversation ID to continue")


class WebsiteChatMessageItem(BaseModel):
    id: Optional[int] = None
    direction: str
    author_type: str
    body: str
    occurred_at: Optional[datetime] = None


class WebsiteChatResponse(BaseModel):
    ok: bool = True
    conversation_id: int
    reply: str
    messages: list[WebsiteChatMessageItem] = []

