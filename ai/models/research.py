from typing import List, Literal

from pydantic import BaseModel

class StopResearchResult(BaseModel):
    place_id: str
    name: str
    address: str
    persona_score: float
    context_facts: List[str]
    opening_hours: str
    is_seasonal: bool
    data_source: Literal["api", "mock"] = "api"
