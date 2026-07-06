from typing import Literal

from pydantic import BaseModel


class RouteStop(BaseModel):
    place_id: str
    order: int
    travel_time_from_prev_min: int
    lat: float
    lng: float
    place_source: Literal["api", "mock", "unknown"] = "api"
    # travel_source discriminates how travel_time_from_prev_min was obtained:
    #   "api"       — real leg duration from Google Directions
    #   "mock"      — synthetic value when Directions API is not configured
    #   "overnight" — cross-day leg; UI shows this as "N min to tomorrow's first stop"
    #   "none"      — first stop in sequence; no previous stop to measure from
    travel_source: Literal["api", "mock", "overnight", "none"] = "none"
    travel_mode: Literal["driving", "transit", "walking", "none", "unknown"] = "unknown"


class RouteModel(BaseModel):
    stops: list[RouteStop]
    total_travel_min: int
