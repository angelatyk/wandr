from typing import List, Literal

from pydantic import BaseModel

class RouteStop(BaseModel):
    place_id: str
    order: int
    travel_time_from_prev_min: int
    lat: float
    lng: float
    place_source: Literal["api", "mock"] = "api"
    travel_source: Literal["api", "mock", "none"] = "none"

class RouteModel(BaseModel):
    stops: List[RouteStop]
    total_travel_min: int
