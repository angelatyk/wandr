from typing import Annotated

from pydantic import BaseModel, Field

from ai.models.input_limits import (
    FREE_TEXT_MAX,
    LOCATION_TEXT_MAX,
    MAX_CONFIRMED_PLACES,
    PLACE_ID_MAX,
    SHORT_TEXT_MAX,
)

# Named aliases keep field definitions DRY while enforcing length caps at the API boundary.
FreeText = Annotated[str, Field(max_length=FREE_TEXT_MAX)]
LocationText = Annotated[str, Field(max_length=LOCATION_TEXT_MAX)]
ShortText = Annotated[str, Field(max_length=SHORT_TEXT_MAX)]
PlaceId = Annotated[str, Field(max_length=PLACE_ID_MAX)]


class TripRequest(BaseModel):
    vibe: FreeText | None = None
    destination: LocationText | None = None
    current_location: LocationText | None = None
    duration: ShortText | None = None
    persona_type: ShortText | None = None
    transit_preference: ShortText | None = None


class SelectRequest(TripRequest):
    """
    Payload from VerifyPage when the user refines or finalises the itinerary.

    confirmed_place_ids — place_ids the user has toggled ON
    refinement_text     — optional free-text refinement request
    action              — "refine" re-generates options; "finalize" locks in the itinerary
    """

    confirmed_place_ids: list[PlaceId] = Field(default_factory=list, max_length=MAX_CONFIRMED_PLACES)
    refinement_text: FreeText | None = None
    action: str = "refine"  # "refine" | "finalize"
