from typing import Annotated, Optional

from pydantic import BaseModel, Field

# Free-text fields are capped so a single request can't push an unbounded prompt
# into Gemini (token-cost abuse) or carry an oversized prompt-injection payload.
ShortText = Annotated[str, Field(max_length=200)]
FreeText = Annotated[str, Field(max_length=2000)]
PlaceId = Annotated[str, Field(max_length=300)]


class TripRequest(BaseModel):
    vibe: Optional[FreeText] = None
    destination: Optional[ShortText] = None
    current_location: Optional[ShortText] = None
    duration: Optional[ShortText] = None
    persona_type: Optional[ShortText] = None
    transit_preference: Optional[ShortText] = None


class SelectRequest(TripRequest):
    """
    Payload from VerifyPage when the user refines or finalises the itinerary.

    confirmed_place_ids — place_ids the user has toggled ON
    refinement_text     — optional free-text refinement request
    action              — "refine" re-generates options; "finalize" locks in the itinerary
    """

    confirmed_place_ids: list[PlaceId] = Field(default_factory=list, max_length=200)
    refinement_text: Optional[FreeText] = None
    action: str = "refine"  # "refine" | "finalize"
