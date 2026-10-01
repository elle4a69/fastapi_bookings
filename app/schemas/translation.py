"""Pydantic schemas for tenant translations and dynamic terminology."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


TerminologyMap = Dict[str, str]


class IndustryPresetInfo(BaseModel):
    """Details and terminology map for an industry preset."""

    id: str = Field(..., description="Unique machine key for the preset")
    name: str = Field(..., description="Human-readable preset name")
    description: str = Field(..., description="Description of the target industry")
    terminology: Dict[str, str] = Field(..., description="Default terminology map for this preset")


class IndustryPresetList(BaseModel):
    """List of all available industry presets."""

    presets: List[IndustryPresetInfo] = Field(default_factory=list, description="Available presets")


class TenantTranslationOut(BaseModel):
    """Tenant translation record."""

    id: int
    tenant_id: int
    locale: str = "en"
    terminology: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantTranslationUpdate(BaseModel):
    """Payload to update custom terms or apply an industry preset."""

    locale: Optional[str] = Field(None, description="Language / locale code (e.g. 'en')")
    preset: Optional[str] = Field(
        None,
        description="Industry preset key to apply (e.g. 'allied_health', 'automotive', 'wellness_salon', 'professional_services')",
    )
    terminology: Optional[Dict[str, str]] = Field(
        None,
        description="Custom terminology overrides dictionary",
    )


class AdminTranslationsResponse(BaseModel):
    """Response returned to tenant administrators for translation management."""

    translation: TenantTranslationOut
    presets: List[IndustryPresetInfo]
    resolved_terminology: Dict[str, str]


class PublicTranslationsResponse(BaseModel):
    """Publicly accessible terminology and locale configuration for booking portals."""

    locale: str = "en"
    terminology: Dict[str, str] = Field(default_factory=dict)
