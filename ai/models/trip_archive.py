from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

PlanStatus = Literal[
    "started",
    "planning",
    "awaiting_selection",
    "complete",
    "error",
]


class TripSummary(BaseModel):
    plan_id: str
    status: PlanStatus
    destination: str = "Unknown destination"
    duration: str = ""
    persona_type: str = ""
    stop_count: int = 0
    has_audio: bool = False
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None


class SavedPlanSnapshot(BaseModel):
    plan_id: str
    status: PlanStatus
    summary: TripSummary
    state: dict[str, Any] = Field(default_factory=dict)
