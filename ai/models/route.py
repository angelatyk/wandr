from typing import List, Literal

from pydantic import BaseModel

class RouteStop(BaseModel):
    place_id: str
    order: int
    travel_time_from_prev_min: int
    lat: float
    lng: float
    place_source: Literal["api", "mock", "unknown"] = "api"
    # "api"      — travel time from Google Directions API
    # "mock"     — travel time from mock data
    # "overnight"— cross-day leg (first stop of Day N+1 relative to last of Day N)
    # "none"     — first stop in sequence, no prior stop to measure from
    travel_source: Literal["api", "mock", "overnight", "none"] = "none"

class RouteModel(BaseModel):
    stops: List[RouteStop]
    total_travel_min: int
