from pydantic import BaseModel
from typing import Literal, Any, Optional

class PipelineEvent(BaseModel):
    type: Literal[
        "profiler_clarification",
        "profiler_done",
        "itinerary_options",   # options mode — user must confirm/refine before finalizing
        "itinerary_done",
        "stop_done",
        "logistics_done",
        "complete",
        "error"
    ]
    data: Optional[dict[str, Any]] = None
    progress: int
