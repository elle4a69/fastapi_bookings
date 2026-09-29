"""Pydantic schemas for travel calculations and routing."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TravelEstimateRequest(BaseModel):
    """Request payload for estimating travel fees based on suburb/postcode."""
    model_config = ConfigDict(from_attributes=True)

    provider_id: int = Field(..., description="Provider ID to check travel for")
    suburb: str = Field(..., min_length=1, description="Suburb name for centroid estimate")
    postcode: Optional[str] = Field(None, description="Postcode / ZIP code (optional)")


class TravelQuoteRequest(BaseModel):
    """Request payload for exact travel quote to a specific address."""
    model_config = ConfigDict(from_attributes=True)

    provider_id: int = Field(..., description="Provider ID to calculate travel for")
    service_address: str = Field(..., min_length=1, description="Exact destination street address for out-call booking")
    previous_booking_address: Optional[str] = Field(
        None, description="Previous booking address if evaluating actual origin routing"
    )


class ChargeableTravelQuote(BaseModel):
    """Commercial travel quote specifying billing amounts and radius compliance."""
    model_config = ConfigDict(from_attributes=True)

    distance_km: float = Field(..., description="Calculated chargeable distance in kilometers")
    travel_fee: float = Field(..., description="Total travel surcharge fee charged to the client")
    base_surcharge: float = Field(..., description="Base out-call surcharge amount")
    distance_fee: float = Field(..., description="Variable distance-based fee component")
    origin_type: str = Field(..., description="Origin policy used: ALWAYS_FROM_BASE or ACTUAL_ORIGIN")
    is_estimate: bool = Field(False, description="True if based on suburb/postcode centroid estimate")
    within_radius: bool = Field(True, description="Whether destination is within provider's maximum out-call radius")
    max_radius_km: float = Field(..., description="Provider's maximum allowed out-call radius in km")
    origin_address: Optional[str] = Field(None, description="Resolved origin address or waypoint")
    destination_address: Optional[str] = Field(None, description="Destination address or suburb")
    disclaimer: Optional[str] = Field(None, description="Contextual disclaimer or note for quotes/estimates")
    reason: Optional[str] = Field(None, description="Failure reason if not within radius or unserviceable")


class OperationalTravelSegment(BaseModel):
    """Physical transit calculation for provider itinerary and calendar buffers."""
    model_config = ConfigDict(from_attributes=True)

    origin: str = Field(..., description="Origin location or coordinates")
    destination: str = Field(..., description="Destination location or coordinates")
    duration_minutes: float = Field(..., description="Transit duration in minutes")
    distance_km: float = Field(..., description="Physical road distance in kilometers")
    method: str = Field(..., description="Routing calculation method used (osrm, haversine, direct)")


class OperationalTransitRequest(BaseModel):
    """Request payload for calculating operational travel between two waypoints."""
    model_config = ConfigDict(from_attributes=True)

    origin: str = Field(..., min_length=1, description="Origin address or coordinates")
    destination: str = Field(..., min_length=1, description="Destination address or coordinates")


class SuburbAutocompleteItem(BaseModel):
    """Item returned by the suburb/postcode autocomplete typeahead endpoint."""
    model_config = ConfigDict(from_attributes=True)

    suburb: str = Field(..., description="Locality or suburb name")
    postcode: str = Field(..., description="Postal code")
    state: str = Field(..., description="State or territory code (e.g. NSW, VIC)")
    latitude: float = Field(..., description="Centroid latitude")
    longitude: float = Field(..., description="Centroid longitude")


class AddressAutocompleteItem(BaseModel):
    """Standardized address suggestion returned by the address autocomplete endpoint."""
    model_config = ConfigDict(from_attributes=True)

    formatted_address: str = Field(..., description="Full standardized display address")
    street_address: Optional[str] = Field(None, description="Street number and street name if available")
    suburb: Optional[str] = Field(None, description="Suburb or locality name")
    state: Optional[str] = Field(None, description="State or territory code (e.g. NSW, VIC)")
    postcode: Optional[str] = Field(None, description="Postal code")
    country: Optional[str] = Field("Australia", description="Country name")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    source: str = Field("au_postcodes", description="Data source providing verification (mapbox, osm_nominatim, au_postcodes)")
    is_verified: bool = Field(True, description="Whether this address was verified against geospatial authority")

