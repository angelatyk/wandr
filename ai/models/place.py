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
    source: str = "api"  # "api" | "mock"
