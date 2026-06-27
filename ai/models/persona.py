from typing import Literal
from pydantic import BaseModel

class PersonaModel(BaseModel):
    type: Literal["foodie", "artist", "historian", "adventurer", "local-life"]
    pace: Literal["relaxed", "moderate", "packed"]
    budget: Literal["budget", "mid", "luxury"]
    notes: str
