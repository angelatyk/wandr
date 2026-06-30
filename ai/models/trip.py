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

class PlaceOptionModel(BaseModel):
    place_id: str
    name: str
    address: str
    photo_url: str
    suggested_duration: str
    description: str
    must_see: bool
    hours_of_operation: str
    persona_note: str

class DayOptionsModel(BaseModel):
    day: int
    options: List[PlaceOptionModel]

class ItineraryOptionsModel(BaseModel):
    destination: str
    days: List[DayOptionsModel]
