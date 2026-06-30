from pydantic import BaseModel
from typing import Optional


class TripRequest(BaseModel):
    vibe: Optional[str] = None
    location: Optional[str] = None
    duration: Optional[str] = None


class SelectRequest(TripRequest):
    """
    Payload from VerifyPage when the user refines or finalises the itinerary.

    confirmed_place_ids — place_ids the user has toggled ON
    refinement_text     — optional free-text refinement request
    action              — "refine" re-generates options; "finalize" locks in the itinerary
    """
    confirmed_place_ids: list[str] = []
    refinement_text: Optional[str] = None
    action: str = "refine"  # "refine" | "finalize"
