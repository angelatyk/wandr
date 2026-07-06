import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ai.models.trip_archive import PlanStatus, SavedPlanSnapshot, TripSummary

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PLANS_ROOT = _PROJECT_ROOT / "outputs" / "plans"


def _now() -> datetime:
    return datetime.now(timezone.utc)


_SAFE_PLAN_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def is_valid_plan_id(plan_id: str) -> bool:
    """Plan IDs are server-minted UUIDs; reject anything that could traverse paths."""
    return bool(plan_id) and _SAFE_PLAN_ID.match(plan_id) is not None


def _plan_path(plan_id: str) -> Path:
    if not is_valid_plan_id(plan_id):
        raise ValueError(f"Unsafe plan_id: {plan_id!r}")
    return _PLANS_ROOT / f"{plan_id}.json"


def derive_plan_status(state: dict[str, Any]) -> PlanStatus:
    if state.get("pipeline_error"):
        return "error"
    # A plan is only fully complete once logistics (route) and narration (audio_scripts) are done
    if state.get("itinerary") and state.get("route") and state.get("audio_scripts"):
        return "complete"
    if state.get("itinerary_options"):
        return "awaiting_selection"
    if state.get("persona") or state.get("itinerary"):
        return "planning"
    return "started"


def _stop_count(state: dict[str, Any]) -> int:
    itinerary = state.get("itinerary") or {}
    return sum(len(day.get("stops", [])) for day in itinerary.get("days", []))


def _has_audio(state: dict[str, Any]) -> bool:
    scripts = (state.get("audio_scripts") or {}).get("scripts") or []
    return any(script.get("audio_url") for script in scripts)


def build_summary(
    plan_id: str,
    state: dict[str, Any],
    *,
    owner_id: str = "",
    created_at: datetime | None = None,
) -> TripSummary:
    persona = state.get("persona") or {}
    pipeline_error = state.get("pipeline_error") or {}
    now = _now()
    return TripSummary(
        plan_id=plan_id,
        status=derive_plan_status(state),
        owner_id=owner_id,
        destination=persona.get("destination") or state.get("itinerary", {}).get("destination") or "Unknown destination",
        duration=persona.get("duration") or "",
        persona_type=persona.get("type") or "",
        stop_count=_stop_count(state),
        has_audio=_has_audio(state),
        created_at=created_at or now,
        updated_at=now,
        error_message=pipeline_error.get("message"),
    )


def enrich_itinerary_dict(itinerary: dict[str, Any], place_photos: dict[str, str]) -> dict[str, Any]:
    """Copy place_photos onto stops so saved trips keep images after options are cleared."""
    if not place_photos or not itinerary.get("days"):
        return itinerary

    enriched_days = []
    for day in itinerary["days"]:
        enriched_stops = []
        for stop in day.get("stops", []):
            entry = dict(stop)
            if not entry.get("photo_url"):
                photo = place_photos.get(entry.get("place_id", ""))
                if photo:
                    entry["photo_url"] = photo
            enriched_stops.append(entry)
        enriched_days.append({**day, "stops": enriched_stops})
    return {**itinerary, "days": enriched_days}


def sanitize_state_for_storage(plan_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Strip bulky inline audio blobs — disk files + API URLs are enough."""
    sanitized = dict(state)
    place_photos = sanitized.get("place_photos") or {}
    if sanitized.get("itinerary"):
        sanitized["itinerary"] = enrich_itinerary_dict(sanitized["itinerary"], place_photos)
    scripts_payload = sanitized.get("audio_scripts")
    if scripts_payload and isinstance(scripts_payload.get("scripts"), list):
        cleaned_scripts = []
        for script in scripts_payload["scripts"]:
            entry = dict(script)
            audio_url = entry.get("audio_url") or ""
            place_id = entry.get("place_id") or ""
            if audio_url.startswith("data:audio/"):
                entry["audio_url"] = f"/api/plan/{plan_id}/audio?place_id={quote(place_id, safe='')}"
                entry["audio_source"] = "stored"
            elif audio_url.startswith("/api/plan/") and place_id:
                entry["audio_url"] = f"/api/plan/{plan_id}/audio?place_id={quote(place_id, safe='')}"
                entry["audio_source"] = entry.get("audio_source") or "stored"
            cleaned_scripts.append(entry)
        sanitized["audio_scripts"] = {"scripts": cleaned_scripts}
    return sanitized


def _write_snapshot(snapshot: SavedPlanSnapshot) -> None:
    _PLANS_ROOT.mkdir(parents=True, exist_ok=True)
    payload = snapshot.model_dump(mode="json")
    _plan_path(snapshot.plan_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_plan_snapshot(
    plan_id: str,
    state: dict[str, Any],
    *,
    owner_id: str | None = None,
) -> SavedPlanSnapshot:
    existing = load_plan_snapshot(plan_id)
    created_at = existing.summary.created_at if existing else _now()
    # Ownership is set at creation and never reassigned on later updates.
    resolved_owner = owner_id or (existing.owner_id if existing else "") or ""
    sanitized_state = sanitize_state_for_storage(plan_id, state)
    summary = build_summary(plan_id, sanitized_state, owner_id=resolved_owner, created_at=created_at)
    summary.updated_at = _now()
    snapshot = SavedPlanSnapshot(
        plan_id=plan_id,
        status=summary.status,
        owner_id=resolved_owner,
        summary=summary,
        state=sanitized_state,
    )
    _write_snapshot(snapshot)
    logger.info("Saved plan snapshot %s (status=%s, owner=%s).", plan_id, summary.status, resolved_owner or "-")
    return snapshot


async def async_save_plan_snapshot(
    plan_id: str,
    state: dict[str, Any],
    *,
    owner_id: str | None = None,
) -> SavedPlanSnapshot:
    return await asyncio.to_thread(save_plan_snapshot, plan_id, state, owner_id=owner_id)


def load_plan_snapshot(plan_id: str) -> SavedPlanSnapshot | None:
    if not is_valid_plan_id(plan_id):
        return None
    path = _plan_path(plan_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SavedPlanSnapshot.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Could not load plan snapshot %s: %s", plan_id, exc)
        return None


def user_owns_plan(snapshot: SavedPlanSnapshot | None, owner_id: str) -> bool:
    """Ownership check. Legacy plans with no owner are treated as inaccessible."""
    if snapshot is None:
        return False
    return bool(snapshot.owner_id) and snapshot.owner_id == owner_id


def list_plan_summaries(owner_id: str | None = None) -> list[TripSummary]:
    if not _PLANS_ROOT.is_dir():
        return []

    summaries: list[TripSummary] = []
    for path in _PLANS_ROOT.glob("*.json"):
        snapshot = load_plan_snapshot(path.stem)
        if snapshot is None:
            continue
        # Only surface trips owned by the requesting user.
        if owner_id is not None and snapshot.owner_id != owner_id:
            continue
        summaries.append(snapshot.summary)

    summaries.sort(key=lambda item: item.updated_at, reverse=True)
    return summaries
