from typing import Literal

from pydantic import BaseModel


class StopResearchResult(BaseModel):
    """Enriched stop data produced by the Stop Research agent for the Narrator."""

    place_id: str
    name: str
    address: str
    persona_score: float
    context_facts: list[str]
    opening_hours: str
    is_seasonal: bool
    data_source: Literal["api", "mock"] = "api"
