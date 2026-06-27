from pydantic import BaseModel
from typing import List

class RouteStop(BaseModel):
    place_id: str
    order: int
    travel_time_from_prev_min: int
    lat: float
    lng: float

class RouteModel(BaseModel):
    stops: List[RouteStop]
    total_travel_min: int
