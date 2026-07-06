from typing import Any, Literal

from pydantic import BaseModel


class PipelineEvent(BaseModel):
    """SSE payload streamed to the frontend for each pipeline phase transition."""

    type: Literal[
        "profiler_clarification",
        "profiler_done",
        "itinerary_options",   # options mode — user must confirm/refine before finalizing
        "itinerary_done",
        "stop_done",
        "logistics_done",
        "complete",
        "error",
    ]
    data: dict[str, Any] | None = None
    progress: int
