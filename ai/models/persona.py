from typing import Literal
from pydantic import BaseModel


class PersonaModel(BaseModel):
    # Minimum required trip parameters — profiler must extract these before downstream agents run
    destination: str
    duration: str
    current_location: str | None = None

    # Traveller persona classification
    type: Literal["foodie", "artist", "historian", "adventurer", "local-life"]
    pace: Literal["relaxed", "moderate", "packed"]
    budget: Literal["budget", "mid", "luxury"]

    # Freeform context — anything extra the user mentioned
    notes: str
