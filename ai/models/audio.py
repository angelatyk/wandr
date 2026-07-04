from typing import List, Literal

from pydantic import BaseModel

class AudioScript(BaseModel):
    place_id: str
    script: str
    audio_url: str
    duration_sec: int
    research_source: Literal["api", "mock", "unknown"] = "unknown"
    tts_attempted: bool = False
    audio_source: Literal["inline", "signed_url", "text_only"] = "text_only"

class AudioScriptsModel(BaseModel):
    scripts: List[AudioScript]
