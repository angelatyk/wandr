from pydantic import BaseModel
from typing import Optional

class TripRequest(BaseModel):
    vibe: Optional[str] = None
    location: Optional[str] = None
    duration: Optional[str] = None
