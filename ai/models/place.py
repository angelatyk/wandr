from pydantic import BaseModel, Field


class PlaceDetails(BaseModel):
    """Enriched place data returned by get_place_details — fed to Stop Research."""

    place_id: str
    name: str
    address: str
    opening_hours: str
    editorial_summary: str = ""
    rating: float | None = None
    user_rating_count: int | None = None
    types: list[str] = Field(default_factory=list)
    business_status: str = "UNKNOWN"
    is_seasonal_or_closed: bool = False
    lat: float | None = None
    lng: float | None = None
    source: str = "api"  # "api" | "mock"


class PlaceSearchResult(BaseModel):
    """Factual place candidate returned by places_search for itinerary planning."""

    place_id: str
    name: str
    address: str
    opening_hours: str = "Unknown"
    editorial_summary: str = ""
    rating: float | None = None
    user_rating_count: int | None = None
    types: list[str] = Field(default_factory=list)
    business_status: str = "UNKNOWN"
    photo_url: str = ""
    lat: float | None = None
    lng: float | None = None
    source: str = "api"  # "api" | "mock" | "confirmed"
