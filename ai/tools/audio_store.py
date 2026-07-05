import asyncio
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_AUDIO_ROOT = _PROJECT_ROOT / "outputs" / "audio"
_SAFE_ID = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_segment(value: str) -> str:
    cleaned = _SAFE_ID.sub("_", value.strip())
    return cleaned or "unknown"


def plan_audio_path(plan_id: str, place_id: str) -> Path:
    """Return the on-disk MP3 path for a stop narration."""
    return _AUDIO_ROOT / _safe_segment(plan_id) / f"{_safe_segment(place_id)}.mp3"


def plan_audio_api_url(plan_id: str, place_id: str) -> str:
    """Browser-playable API URL for a persisted narration clip."""
    return f"/api/plan/{plan_id}/audio/{place_id}"


def _write_bytes(path: Path, audio_bytes: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio_bytes)


async def save_plan_audio(plan_id: str, place_id: str, audio_bytes: bytes) -> str:
    """Persist MP3 bytes for a plan stop and return the playback API URL."""
    path = plan_audio_path(plan_id, place_id)
    await asyncio.to_thread(_write_bytes, path, audio_bytes)
    logger.info("Saved narration audio to %s (%d bytes).", path, len(audio_bytes))
    return plan_audio_api_url(plan_id, place_id)


def load_plan_audio(plan_id: str, place_id: str) -> bytes | None:
    """Load persisted MP3 bytes, or None if the file does not exist."""
    path = plan_audio_path(plan_id, place_id)
    if not path.is_file():
        return None
    return path.read_bytes()
