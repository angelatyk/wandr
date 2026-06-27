from pydantic import BaseModel
from typing import List

class StopResearchResult(BaseModel):
    place_id: str
    name: str
    address: str
    persona_score: float
    context_facts: List[str]
    opening_hours: str
    is_seasonal: bool
