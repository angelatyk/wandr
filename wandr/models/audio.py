from pydantic import BaseModel
from typing import List

class AudioScript(BaseModel):
    place_id: str
    script: str
    audio_url: str
    duration_sec: int

class AudioScriptsModel(BaseModel):
    scripts: List[AudioScript]
