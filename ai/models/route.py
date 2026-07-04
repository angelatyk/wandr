from typing import List

from pydantic import BaseModel

class RouteStop(BaseModel):
    place_id: str
    day: int
    order: int
    travel_time_from_prev_min: int
    transit_mode: str
    break_duration: int
    lat: float
    lng: float

class RouteModel(BaseModel):
    stops: List[RouteStop]
    total_travel_min: int
