"""Pydantic schemas for the Umbrella Directory and Geo-Radius Map Marketplace."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DirectoryServiceBadge(BaseModel):
    """Summarized service badge shown on tenant directory card."""
    id: int
    name: str
    duration: int
    price: float
    category: Optional[str] = None


class DirectoryTenantCard(BaseModel):
    """Verified tenant card representation for directory & map marketplace."""
    id: int
    name: str
    subdomain: str
    description: Optional[str] = None
    rating: float = 4.9
    review_count: int = 15
    starting_price: float = 0.0
    location_name: str = ""
    address: str = ""
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    website_url: str
    booking_url: str
    featured_services: List[Dict[str, Any]] = Field(default_factory=list)


class DirectorySearchResponse(BaseModel):
    """Response payload for directory geo-radius search."""
    ok: bool = True
    count: int
    search_center: Optional[Dict[str, Any]] = None
    radius_km: float
    tenants: List[DirectoryTenantCard] = Field(default_factory=list)


class DirectoryTriageRequest(BaseModel):
    """Payload for AI bot directory triage."""
    query: str
    user_lat: Optional[float] = None
    user_lng: Optional[float] = None
    postcode_or_suburb: Optional[str] = None


class DirectoryTriageResponse(BaseModel):
    """Response payload for AI bot directory triage concierge."""
    ok: bool = True
    reply: str
    matched_tenants: List[DirectoryTenantCard] = Field(default_factory=list)


class DirectoryFeaturedResponse(BaseModel):
    """Featured tenants and top service categories for directory landing."""
    ok: bool = True
    featured_tenants: List[DirectoryTenantCard] = Field(default_factory=list)
    categories: List[Dict[str, Any]] = Field(default_factory=list)
