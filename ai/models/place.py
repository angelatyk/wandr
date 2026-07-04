from typing import List, Optional

from pydantic import BaseModel, Field


class PlaceDetails(BaseModel):
    """Enriched place data returned by get_place_details — fed to Stop Research."""

    place_id: str
    name: str
    address: str
    opening_hours: str
    editorial_summary: str = ""
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    types: List[str] = Field(default_factory=list)
    business_status: str = "UNKNOWN"
    is_seasonal_or_closed: bool = False
    lat: Optional[float] = None
    lng: Optional[float] = None
    source: str = "api"  # "api" | "mock"


class PlaceSearchResult(BaseModel):
    """Factual place candidate returned by places_search for itinerary planning."""

    place_id: str
    name: str
    address: str
    opening_hours: str = "Unknown"
    editorial_summary: str = ""
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    types: List[str] = Field(default_factory=list)
    business_status: str = "UNKNOWN"
    photo_url: str = ""
    source: str = "api"  # "api" | "mock" | "confirmed"
