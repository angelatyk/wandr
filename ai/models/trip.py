from pydantic import BaseModel
from typing import List

class StopModel(BaseModel):
    place_id: str
    name: str
    address: str
    day: int
    order: int

class ItineraryDay(BaseModel):
    day: int
    stops: List[StopModel]

class ItineraryModel(BaseModel):
    destination: str
    days: List[ItineraryDay]
