"""Pydantic schemas for Media API."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MediaItemResponse(BaseModel):
    """Admin-facing media item representation."""

    id: int
    tenant_id: int
    provider_id: Optional[int] = None
    filename: str
    file_path: str
    url: str
    content_type: str
    file_size: int
    title: Optional[str] = None
    description: Optional[str] = None
    alt_text: Optional[str] = None
    media_type: str
    is_public_website_eligible: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MediaItemSummary(BaseModel):
    """Public / Assistant-facing safe media item representation.

    Excludes internal file paths and private/clinical notes.
    """

    id: int
    filename: str
    url: str
    content_type: str
    file_size: int
    title: Optional[str] = None
    description: Optional[str] = None
    alt_text: Optional[str] = None
    media_type: str
    is_public_website_eligible: bool

    model_config = ConfigDict(from_attributes=True)


class MediaEligibilityUpdate(BaseModel):
    """Payload to update public website eligibility."""

    is_public_website_eligible: bool = Field(
        ..., description="Whether this media asset is approved for public website use"
    )


class MediaUpdatePayload(BaseModel):
    """Payload to update media metadata."""

    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    alt_text: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, description="Confidential internal/clinical notes")
    provider_id: Optional[int] = None
    is_public_website_eligible: Optional[bool] = None


class MediaListResponse(BaseModel):
    """List response envelope."""

    ok: bool = True
    data: List[MediaItemResponse]
    total: int


class MediaDetailResponse(BaseModel):
    """Single item response envelope."""

    ok: bool = True
    data: MediaItemResponse


class MediaDeleteResponse(BaseModel):
    """Deletion response envelope."""

    ok: bool = True
    message: str = "Media item deleted successfully."
    id: int
