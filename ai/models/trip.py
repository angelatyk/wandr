from pydantic import BaseModel


class StopModel(BaseModel):
    place_id: str
    name: str
    address: str
    day: int
    order: int
    photo_url: str = ""


class ItineraryDay(BaseModel):
    day: int
    stops: list[StopModel]


class ItineraryModel(BaseModel):
    destination: str
    days: list[ItineraryDay]


class PlaceOptionModel(BaseModel):
    """A single candidate place shown to the user during the options/verify step."""

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
    options: list[PlaceOptionModel]


class ItineraryOptionsModel(BaseModel):
    """Itinerary in "options" mode — user must confirm/refine before finalizing."""

    destination: str
    days: list[DayOptionsModel]
