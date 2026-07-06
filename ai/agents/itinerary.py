import json
import logging
import math
from collections import defaultdict
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import Client, types
from pydantic import ValidationError

from ai.agents.model_fallback import generate_with_fallback
from ai.models.duration import (
    ParsedDuration,
    max_options_per_day,
    max_stops_for_duration,
    parse_trip_duration,
)
from ai.models.place import PlaceSearchResult
from ai.models.tool_usage import load_tool_usage, merge_tool_usage, usage_from_places_search
from ai.models.trip import (
    DayOptionsModel,
    ItineraryDay,
    ItineraryModel,
    ItineraryOptionsModel,
    PlaceOptionModel,
    StopModel,
)
from ai.tools.maps import places_search
from ai.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — double-brace all literal JSON braces so .format() works.
# ---------------------------------------------------------------------------
ITINERARY_SYSTEM_PROMPT = """\
You are the Itinerary Planner for Wandr, an AI travel guide.
Your job is to build a personalised itinerary based on the user's travel persona.

## User Persona
Destination: {destination}
Current Location: {current_location}
Transit Preference: {transit_preference}
Duration: {duration}
Type: {type}
Pace: {pace}
Budget: {budget}
Notes: {notes}

## Already Confirmed Places
{confirmed_section}

## Refinement Request
{refinement_section}

## Candidate Places
{candidate_section}

## Your Task
You are given factual candidate places already fetched from Google Places.
Use ONLY these candidates. Do not use outside knowledge, do not invent new places,
and do not change a place_id.

IMPORTANT: For multi-day trips, group places geographically by day (cluster them into regions) to minimize driving distances and prevent zig-zagging between distant areas. Day 1 should start in the region closest to the user's Current Location.

CORRIDOR RULE (only applies when Current Location is provided and is different from Destination): Every stop you include must be geographically plausible along the travel route from the Current Location to the Destination. Do NOT include stops that are in an unrelated region or require significant backtracking in the wrong direction. If a candidate from the list is clearly off-route, skip it and use another candidate instead. When no Current Location is given, this rule does not apply — simply select the best candidates within or near the Destination.

Output ONLY a raw JSON object (no markdown fences, no commentary) that matches
this schema exactly:
{{
  "mode": "options",
  "data": {{
    "destination": "<destination>",
    "days": [
      {{
        "day": 1,
        "options": [
          {{
            "place_id": "<unique string id>",
            "name": "<place name>",
            "address": "<full address>",
            "photo_url": "<real photo url or empty string>",
            "suggested_duration": "<e.g. 2 hours>",
            "description": "<one-sentence description>",
            "must_see": true,
            "hours_of_operation": "<e.g. 9am–6pm daily>",
            "persona_note": "<one sentence: why this fits the persona>"
          }}
        ]
      }}
    ]
  }}
}}

IMPORTANT: If you cannot find real data for a field, use a sensible placeholder —
never output prose, never wrap the JSON in markdown fences, never add any text
before or after the JSON object.
Also:
- Every option MUST come from the candidate list above.
- Copy `place_id`, `name`, `address`, `photo_url`, and `hours_of_operation`
  exactly from the matching candidate.
- Keep already confirmed places in the output.
- Do not repeat the same `place_id` across multiple days.

## Duration rules (STRICT — enforced by the system)
{duration_rules}
}}
"""

_client = Client()
_MODEL_FALLBACKS = [m.strip() for m in settings.model_fallbacks.split(",") if m.strip()]


def _build_confirmed_section(confirmed: list[dict]) -> str:
    """Format confirmed places into a human-readable prompt section."""
    if not confirmed:
        return "None yet — generate fresh options."
    lines = ["The user has already confirmed these places. You MUST include them in your output:"]
    for p in confirmed:
        lines.append(
            "  - "
            f"{p.get('name', 'Unknown')} "
            f"(ID: {p.get('place_id', '?')}, Day {p.get('day', '?')}, "
            f"Address: {p.get('address', 'Unknown')})"
        )
    return "\n".join(lines)


def _build_refinement_section(text: str | None) -> str:
    """Format the user's refinement request."""
    if not text:
        return "No refinement requested — generate options normally."
    return f'The user wants to refine the itinerary: "{text}". Incorporate this into your options.'


def _build_candidate_section(candidates: list[PlaceSearchResult]) -> str:
    if not candidates:
        return "No candidate places were found."

    lines = ["Use only these Google Places candidates:"]
    for candidate in candidates:
        lines.extend(
            [
                f"- place_id: {candidate.place_id}",
                f"  name: {candidate.name}",
                f"  address: {candidate.address}",
                f"  hours_of_operation: {candidate.opening_hours}",
                f"  photo_url: {candidate.photo_url or '(none)'}",
                f"  rating: {candidate.rating}",
                f"  user_rating_count: {candidate.user_rating_count}",
                f"  types: {', '.join(candidate.types) or '(none)'}",
                f"  editorial_summary: {candidate.editorial_summary or '(none)'}",
            ]
        )
    return "\n".join(lines)


def _build_duration_rules(parsed: ParsedDuration, confirmed_count: int = 0) -> str:
    max_stops = max_stops_for_duration(parsed)
    max_options = max_options_per_day(parsed, parsed.day_count, confirmed_count)
    lines = [
        f'- User duration: "{parsed.raw}" → {parsed.summary}.',
        f"- Output EXACTLY {parsed.day_count} day block(s) in the `days` array (day numbers 1..{parsed.day_count}).",
        "- Never invent extra calendar days beyond this count.",
        "- Include a mix of primary attractions and **short stops** (e.g. 15-30 mins: statues, viewpoints, quick snacks, small parks) so the user can build a rich, multi-stop itinerary.",
    ]
    if parsed.is_single_outing:
        lines.extend(
            [
                "- This is a single-outing / hour-scale trip: put ALL options on day 1 only.",
                f"- Suggest up to {max_options} place options total. Provide plenty of options for the user to choose from; the total time of all options combined CAN exceed the specified duration because the user will curate a subset.",
                f"- When finalising, include at most {max_stops} stops on day 1.",
                "- Do NOT spread a 7-hour walk into multiple days.",
            ]
        )
    else:
        lines.append(
            f"- Distribute options across the {parsed.day_count} day(s); ~{max_options} options per day max. Provide plenty of options; the total time can exceed the duration because the user curates it."
        )
    return "\n".join(lines)


def _day_count_from_duration(duration: str | None) -> int:
    return parse_trip_duration(duration).day_count


def _search_limit_for_days(day_count: int, parsed: ParsedDuration) -> int:
    if parsed.is_single_outing:
        return max(4, min(10, max_options_per_day(parsed, day_count) + 2))
    return max(6, min(40, day_count * 5))


def _candidate_from_confirmed_place(confirmed_place: dict) -> PlaceSearchResult:
    return PlaceSearchResult(
        place_id=confirmed_place["place_id"],
        name=confirmed_place.get("name", "Unknown"),
        address=confirmed_place.get("address", "Unknown"),
        opening_hours=confirmed_place.get("hours_of_operation", "Unknown"),
        editorial_summary=confirmed_place.get("description", ""),
        photo_url=confirmed_place.get("photo_url", ""),
        source="confirmed",
    )


def _suggested_duration(candidate: PlaceSearchResult) -> str:
    types = set(candidate.types)
    if "museum" in types:
        return "2 hours"
    if "park" in types:
        return "2-3 hours"
    if "market" in types or "shopping_mall" in types:
        return "1-2 hours"
    if "neighborhood" in types:
        return "2 hours"
    return "1-2 hours"


def _default_description(candidate: PlaceSearchResult) -> str:
    """Synthesize a short description when the Places API returns no editorial summary.

    Prefer actual editorial text. Fall back to a sentence built from place types and
    rating so we never echo the raw address as a description.
    """
    if candidate.editorial_summary:
        return candidate.editorial_summary

    # Build a readable type label (e.g. "market and café" from raw type strings)
    readable_types = [t.replace("_", " ") for t in (candidate.types or [])[:2]]
    type_label = " and ".join(readable_types) if readable_types else "point of interest"

    rating_clause = ""
    if candidate.rating and candidate.rating >= 4.0:
        rating_clause = f", rated {candidate.rating:.1f}★"

    return f"A {type_label}{rating_clause} worth visiting in {candidate.name}."


def _default_persona_note(candidate: PlaceSearchResult, persona_type: str) -> str:
    types = ", ".join(candidate.types[:2]) or "local highlights"
    return f"Fits a {persona_type} itinerary with its focus on {types}."


def _is_must_see(candidate: PlaceSearchResult) -> bool:
    if candidate.rating is None:
        return False
    return candidate.rating >= 4.5 or (candidate.user_rating_count or 0) >= 15000


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two lat/lng points."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _is_off_corridor(
    candidate: PlaceSearchResult,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> bool:
    """Return True if a candidate stop is implausibly off the origin→destination corridor.

    Uses a simple ellipse test: the sum of distances from the stop to each focus
    (origin and destination) must not exceed the direct origin→destination distance
    by more than a generous slack factor (2.5×). This allows realistic detours and
    scenic routes while catching stops in the completely wrong direction (e.g. Toronto
    on a PEI→Nova Scotia trip).
    """
    if candidate.lat is None or candidate.lng is None:
        # No coords to check — let the LLM's corridor instruction handle it
        return False

    direct_km = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    if direct_km < 50:  # short local trip — corridor constraint doesn't add value
        return False

    stop_to_origin = _haversine_km(candidate.lat, candidate.lng, origin_lat, origin_lng)
    stop_to_dest = _haversine_km(candidate.lat, candidate.lng, dest_lat, dest_lng)
    slack_factor = 2.5
    return (stop_to_origin + stop_to_dest) > direct_km * slack_factor


def _place_option_from_candidate(
    candidate: PlaceSearchResult,
    persona_type: str,
    *,
    description: str | None = None,
    persona_note: str | None = None,
    suggested_duration: str | None = None,
    must_see: bool | None = None,
) -> PlaceOptionModel:
    return PlaceOptionModel(
        place_id=candidate.place_id,
        name=candidate.name,
        address=candidate.address,
        photo_url=candidate.photo_url,
        suggested_duration=suggested_duration or _suggested_duration(candidate),
        description=description or _default_description(candidate),
        must_see=_is_must_see(candidate) if must_see is None else must_see,
        hours_of_operation=candidate.opening_hours,
        persona_note=persona_note or _default_persona_note(candidate, persona_type),
    )


def _build_options_from_candidates(
    destination: str,
    persona_type: str,
    day_count: int,
    candidates: list[PlaceSearchResult],
    confirmed: list[dict],
    *,
    parsed: ParsedDuration,
) -> ItineraryOptionsModel:
    day_numbers = list(range(1, day_count + 1))
    options_by_day: dict[int, list[PlaceOptionModel]] = {day: [] for day in day_numbers}
    seen_place_ids: set[str] = set()

    for place in sorted(confirmed, key=lambda item: (item.get("day", 1), item.get("order", 999))):
        target_day = 1 if parsed.is_single_outing else min(max(1, place.get("day", 1)), day_count)
        candidate = _candidate_from_confirmed_place(place)
        if candidate.place_id in seen_place_ids:
            continue
        options_by_day.setdefault(target_day, []).append(
            _place_option_from_candidate(
                candidate,
                persona_type,
                description=place.get("description"),
                persona_note=place.get("persona_note"),
                suggested_duration=place.get("suggested_duration"),
                must_see=place.get("must_see"),
            )
        )
        seen_place_ids.add(candidate.place_id)

    per_day_target = max_options_per_day(parsed, day_count, len(confirmed))
    unused_candidates = [candidate for candidate in candidates if candidate.place_id not in seen_place_ids]
    candidate_index = 0
    for day in day_numbers:
        while len(options_by_day[day]) < per_day_target and candidate_index < len(unused_candidates):
            candidate = unused_candidates[candidate_index]
            candidate_index += 1
            options_by_day[day].append(_place_option_from_candidate(candidate, persona_type))
            seen_place_ids.add(candidate.place_id)

    days = [
        DayOptionsModel(day=day, options=options_by_day.get(day, []))
        for day in day_numbers
        if options_by_day.get(day)
    ]
    return ItineraryOptionsModel(destination=destination, days=days)


def _enforce_day_structure(
    options: ItineraryOptionsModel,
    day_count: int,
    parsed: ParsedDuration,
    confirmed_count: int = 0,
) -> ItineraryOptionsModel:
    """Clamp LLM output to the parsed calendar day count (fixes spurious multi-day plans)."""
    if day_count <= 1 or parsed.is_single_outing:
        merged: list[PlaceOptionModel] = []
        seen: set[str] = set()
        for day in sorted(options.days, key=lambda item: item.day):
            for option in day.options:
                if option.place_id in seen:
                    continue
                merged.append(option)
                seen.add(option.place_id)
        cap = max_options_per_day(parsed, 1, confirmed_count)
        return ItineraryOptionsModel(
            destination=options.destination,
            days=[DayOptionsModel(day=1, options=merged[:cap])],
        )

    by_day: dict[int, list[PlaceOptionModel]] = {day: [] for day in range(1, day_count + 1)}
    seen: set[str] = set()
    for day in options.days:
        target = min(max(1, day.day), day_count)
        for option in day.options:
            if option.place_id in seen:
                continue
            by_day[target].append(option)
            seen.add(option.place_id)

    cap = max_options_per_day(parsed, day_count, confirmed_count)
    days = [
        DayOptionsModel(day=day, options=by_day[day][:cap])
        for day in range(1, day_count + 1)
        if by_day[day]
    ]
    return ItineraryOptionsModel(destination=options.destination, days=days)


def _normalize_options(
    raw_options: ItineraryOptionsModel,
    destination: str,
    persona_type: str,
    day_count: int,
    candidates: list[PlaceSearchResult],
    confirmed: list[dict],
    *,
    parsed: ParsedDuration,
    corridor_origin: tuple[float, float] | None = None,
    corridor_dest: tuple[float, float] | None = None,
) -> ItineraryOptionsModel:
    raw_options = _enforce_day_structure(raw_options, day_count, parsed, confirmed_count=len(confirmed))
    candidate_map = {candidate.place_id: candidate for candidate in candidates}

    # Build corridor filter — only active when both origin and destination coords are known.
    def _is_corridor_violation(candidate: PlaceSearchResult) -> bool:
        if corridor_origin is None or corridor_dest is None:
            return False
        return _is_off_corridor(
            candidate,
            corridor_origin[0], corridor_origin[1],
            corridor_dest[0], corridor_dest[1],
        )
    normalized_by_day: dict[int, list[PlaceOptionModel]] = {day: [] for day in range(1, day_count + 1)}
    seen_place_ids: set[str] = set()
    seen_names: set[str] = set()

    for day in raw_options.days:
        target_day = 1 if parsed.is_single_outing else min(max(1, day.day), day_count)
        normalized_by_day.setdefault(target_day, [])
        for option in day.options:
            candidate = candidate_map.get(option.place_id)
            if candidate is None or candidate.place_id in seen_place_ids:
                continue

            if _is_corridor_violation(candidate):
                logger.warning(
                    "Corridor filter rejected off-route candidate: %s (%s)",
                    candidate.name, candidate.address,
                )
                continue

            name_key = candidate.name.strip().lower()
            if name_key in seen_names:
                continue
                
            normalized_by_day[target_day].append(
                _place_option_from_candidate(
                    candidate,
                    persona_type,
                    description=option.description,
                    persona_note=option.persona_note,
                    suggested_duration=option.suggested_duration,
                    must_see=option.must_see,
                )
            )
            seen_place_ids.add(candidate.place_id)
            seen_names.add(name_key)

    for place in sorted(confirmed, key=lambda item: (item.get("day", 1), item.get("order", 999))):
        candidate = candidate_map.get(place["place_id"]) or _candidate_from_confirmed_place(place)
        day = place.get("day", 1)
        existing_ids = {option.place_id for option in normalized_by_day.setdefault(day, [])}
        if candidate.place_id in existing_ids:
            continue
            
        name_key = candidate.name.strip().lower()
            
        normalized_by_day[day].insert(
            0,
            _place_option_from_candidate(
                candidate,
                persona_type,
                description=place.get("description"),
                persona_note=place.get("persona_note"),
                suggested_duration=place.get("suggested_duration"),
                must_see=place.get("must_see"),
            ),
        )
        seen_place_ids.add(candidate.place_id)
        seen_names.add(name_key)

    fallback_options = _build_options_from_candidates(
        destination, persona_type, day_count, candidates, confirmed, parsed=parsed
    )
    fallback_by_day = {day.day: list(day.options) for day in fallback_options.days}
    per_day_target = max_options_per_day(parsed, day_count, len(confirmed))
    for day in range(1, day_count + 1):
        existing = normalized_by_day.setdefault(day, [])
        if len(existing) < per_day_target:
            for fallback_opt in fallback_by_day.get(day, []):
                if fallback_opt.place_id not in seen_place_ids:
                    name_key = fallback_opt.name.strip().lower()
                    if name_key not in seen_names:
                        existing.append(fallback_opt)
                        seen_place_ids.add(fallback_opt.place_id)
                        seen_names.add(name_key)
                if len(existing) >= per_day_target:
                    break

    days = [
        DayOptionsModel(day=day, options=normalized_by_day.get(day, []))
        for day in range(1, day_count + 1)
        if normalized_by_day.get(day)
    ]
    return ItineraryOptionsModel(destination=destination, days=days)


def _photo_lookup(confirmed: list[dict], candidates: list[PlaceSearchResult]) -> dict[str, str]:
    """Build place_id → photo_url map from confirmed selections and search candidates."""
    photos: dict[str, str] = {}
    for place in confirmed:
        place_id = place.get("place_id")
        photo_url = place.get("photo_url")
        if place_id and photo_url:
            photos[place_id] = photo_url
    for candidate in candidates:
        if candidate.place_id and candidate.photo_url and candidate.place_id not in photos:
            photos[candidate.place_id] = candidate.photo_url
    return photos


def _enrich_itinerary_photos(itinerary: ItineraryModel, photos: dict[str, str]) -> ItineraryModel:
    """Fill missing stop photo_url values from persisted place photos."""
    if not photos:
        return itinerary

    enriched_days: list[ItineraryDay] = []
    for day in itinerary.days:
        enriched_stops = [
            stop.model_copy(update={"photo_url": stop.photo_url or photos.get(stop.place_id, "")})
            for stop in day.stops
        ]
        enriched_days.append(ItineraryDay(day=day.day, stops=enriched_stops))
    return ItineraryModel(destination=itinerary.destination, days=enriched_days)


def _build_final_itinerary(
    destination: str,
    confirmed: list[dict],
    *,
    parsed: ParsedDuration | None = None,
) -> ItineraryModel:
    parsed = parsed or ParsedDuration(raw="", unit="unknown", amount=1, day_count=1)
    grouped: dict[int, list[dict]] = defaultdict(list)
    for place in confirmed:
        day_number = 1 if parsed.is_single_outing else min(max(1, place.get("day", 1)), parsed.day_count)
        grouped[day_number].append(place)

    days: list[ItineraryDay] = []
    for day_number in sorted(grouped):
        if day_number > parsed.day_count:
            continue
        ordered_places = sorted(grouped[day_number], key=lambda item: item.get("order", 999))
        stops = [
            StopModel(
                place_id=place["place_id"],
                name=place.get("name", "Unknown"),
                address=place.get("address", "Unknown"),
                photo_url=place.get("photo_url", ""),
                day=day_number,
                order=index,
            )
            for index, place in enumerate(ordered_places, start=1)
        ]
        if stops:
            days.append(ItineraryDay(day=day_number, stops=stops))

    return ItineraryModel(destination=destination, days=days)


def _enforce_final_itinerary(itinerary: ItineraryModel, parsed: ParsedDuration) -> ItineraryModel:
    """Clamp a final itinerary to the parsed day count and stop budget."""
    max_stops = max_stops_for_duration(parsed)

    if parsed.is_single_outing or parsed.day_count <= 1:
        merged: list[StopModel] = []
        seen: set[str] = set()
        for day in sorted(itinerary.days, key=lambda item: item.day):
            for stop in day.stops:
                if stop.place_id in seen:
                    continue
                merged.append(stop.model_copy(update={"day": 1, "order": len(merged) + 1}))
                seen.add(stop.place_id)
                if len(merged) >= max_stops:
                    break
            if len(merged) >= max_stops:
                break
        return ItineraryModel(
            destination=itinerary.destination,
            days=[ItineraryDay(day=1, stops=merged)],
        )

    days: list[ItineraryDay] = []
    for day_number in range(1, parsed.day_count + 1):
        source = next((day for day in itinerary.days if day.day == day_number), None)
        if source is None:
            continue
        stops = source.stops[:max_stops]
        days.append(ItineraryDay(day=day_number, stops=stops))
    return ItineraryModel(destination=itinerary.destination, days=days)


async def _call_model(
    history: list[types.Content],
    system_prompt: str,
) -> str:
    """Single Gemini call; returns stripped response text."""
    response = await generate_with_fallback(
        client=_client,
        primary_model=settings.model_name,
        fallback_models=_MODEL_FALLBACKS,
        contents=history,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        ),
        call_label="Itinerary.generate_content",
    )
    return (response.text or "").strip()


def _extract_json(raw: str) -> str | None:
    """
    Pull the outermost JSON object from raw text.
    Returns the JSON string if found, None otherwise.
    """
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return None


class ItineraryAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Skip if a finalised itinerary is already in state — no re-run needed.
        if ctx.session.state.get("itinerary"):
            logger.debug("ItineraryAgent skipping — itinerary already finalised in state.")
            return

        persona_dict = ctx.session.state.get("persona")
        if not persona_dict:
            logger.error("ItineraryAgent called but 'persona' is missing from state.")
            return

        confirmed: list[dict] = ctx.session.state.get("itinerary_options_confirmed", [])
        refinement_text: str | None = ctx.session.state.get("itinerary_refinement_text")
        itinerary_action: str | None = ctx.session.state.get("itinerary_action")

        logger.info("ItineraryAgent session state keys: %s", list(ctx.session.state.keys()))
        logger.info("ItineraryAgent full session state: %s", ctx.session.state)
        logger.info("ItineraryAgent confirmed options (finalize selection): %s", confirmed)

        logger.info(
            "ItineraryAgent starting. persona=(%s, %s, %s, %s, budget=%s) "
            "confirmed_places=%d refinement=%r",
            persona_dict.get("destination"),
            persona_dict.get("duration"),
            persona_dict.get("type"),
            persona_dict.get("pace"),
            persona_dict.get("budget"),
            len(confirmed),
            refinement_text,
        )

        destination = persona_dict.get("destination", "Unknown")
        duration_raw = persona_dict.get("duration", "")
        parsed = parse_trip_duration(duration_raw)
        day_count = parsed.day_count
        persona_type = persona_dict.get("type", "local-life")

        logger.info(
            "Itinerary duration parsed: raw=%r → %s (day_count=%d, single_outing=%s)",
            duration_raw,
            parsed.summary,
            day_count,
            parsed.is_single_outing,
        )

        if itinerary_action == "finalize" and confirmed:
            itinerary = _build_final_itinerary(destination, confirmed, parsed=parsed)
            logger.info(
                "Itinerary finalised from confirmed options for '%s' (%d days).",
                itinerary.destination,
                len(itinerary.days),
            )
            yield Event(
                author=self.name,
                actions=EventActions(state_delta={"itinerary": itinerary.model_dump()}),
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Itinerary finalised.")],
                ),
            )
            return

        search_candidates = await places_search(
            destination=destination,
            persona_type=persona_type,
            limit=_search_limit_for_days(day_count, parsed),
        )
        
        if refinement_text:
            refinement_candidates = await places_search(
                destination=destination,
                persona_type=persona_type,
                limit=3,
                explicit_query=f"{refinement_text} in {destination}"
            )
            existing_ids = {c.place_id for c in search_candidates}
            for candidate in refinement_candidates:
                if candidate.place_id not in existing_ids:
                    search_candidates.append(candidate)
                    existing_ids.add(candidate.place_id)
        current_usage = load_tool_usage(ctx.session.state.get("tool_usage"))
        updated_usage = merge_tool_usage(current_usage, usage_from_places_search(search_candidates))
        for place in confirmed:
            if place.get("place_id") and place["place_id"] not in {candidate.place_id for candidate in search_candidates}:
                search_candidates.append(_candidate_from_confirmed_place(place))

        # ── Corridor coordinates ────────────────────────────────────────────
        # When current_location is provided we resolve both endpoints to lat/lng
        # so the corridor filter can reject off-route candidates (Bug 1).
        # This is best-effort — if geocoding fails we log and disable the filter.
        current_location: str | None = persona_dict.get("current_location")
        corridor_origin: tuple[float, float] | None = None
        corridor_dest: tuple[float, float] | None = None

        if current_location:
            try:
                origin_hits = await places_search(
                    destination=current_location,
                    persona_type=persona_type,
                    limit=1,
                )
                if origin_hits and origin_hits[0].lat is not None and origin_hits[0].lng is not None:
                    corridor_origin = (origin_hits[0].lat, origin_hits[0].lng)
                    logger.info("Corridor origin resolved: %s → %s", current_location, corridor_origin)
                else:
                    logger.warning("Could not geocode current_location=%r for corridor filter.", current_location)
            except Exception as exc:
                logger.warning("Corridor origin geocode failed for %r: %s", current_location, exc)

            if corridor_origin is not None:
                # Use the centroid of the destination search results as the corridor destination.
                lats = [c.lat for c in search_candidates if c.lat is not None]
                lngs = [c.lng for c in search_candidates if c.lng is not None]
                if lats and lngs:
                    corridor_dest = (sum(lats) / len(lats), sum(lngs) / len(lngs))
                    logger.info("Corridor dest centroid: %s", corridor_dest)
                else:
                    logger.warning("No candidate coordinates available — corridor filter disabled.")
                    corridor_origin = None  # disable if we can't anchor the other end


        # Build system prompt, injecting confirmed places + refinement text.
        system_prompt = ITINERARY_SYSTEM_PROMPT.format(
            destination=destination,
            current_location=persona_dict.get("current_location", "Unknown"),
            transit_preference=persona_dict.get("transit_preference", "Unknown"),
            duration=duration_raw or "Unknown",
            type=persona_type,
            pace=persona_dict.get("pace", "Unknown"),
            budget=persona_dict.get("budget", "Unknown"),
            notes=persona_dict.get("notes", ""),
            duration_rules=_build_duration_rules(parsed, confirmed_count=len(confirmed)),
            confirmed_section=_build_confirmed_section(confirmed),
            refinement_section=_build_refinement_section(refinement_text),
            candidate_section=_build_candidate_section(search_candidates),
        )

        # Reconstruct conversation history so the model sees prior context.
        history: list[types.Content] = []
        for event in ctx.session.events:
            if event.content and event.content.parts and event.content.role in ("user", "model"):
                history.append(event.content)

        logger.debug("ItineraryAgent sending request to Gemini (history_turns=%d).", len(history))

        # ── First attempt ────────────────────────────────────────────────────
        raw = await _call_model(history, system_prompt)
        logger.info("Gemini response received (length=%d chars).", len(raw))
        logger.debug("Raw response:\n%s", raw)

        json_str = _extract_json(raw)
        if json_str is None:
            # ── Retry: model returned prose — ask again, explicitly ──────────
            logger.warning(
                "Response did not contain a JSON object — retrying with an explicit JSON demand. "
                "First response preview: %.200s",
                raw,
            )
            retry_history = history + [
                types.Content(role="model", parts=[types.Part(text=raw)]),
                types.Content(
                    role="user",
                    parts=[types.Part(
                        text=(
                            "Your previous response was not valid JSON. "
                            "Output ONLY the raw JSON object as specified in your instructions — "
                            "no markdown fences, no commentary, nothing else."
                        )
                    )],
                ),
            ]
            raw = await _call_model(retry_history, system_prompt)
            json_str = _extract_json(raw)
            logger.info(
                "Retry response received (length=%d chars). JSON found: %s",
                len(raw),
                json_str is not None,
            )

        if json_str is None:
            logger.error("Both attempts failed to produce JSON. Raw:\n%s", raw)
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=raw)]),
            )
            return

        # ── Parse & validate ─────────────────────────────────────────────────
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse failed after extraction: %s\nJSON string:\n%s", exc, json_str)
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=raw)]),
            )
            return

        mode = data.get("mode")
        inner_data = data.get("data")
        logger.info("Parsed itinerary response. mode=%r", mode)

        if mode == "options" and inner_data:
            try:
                raw_options = ItineraryOptionsModel.model_validate(inner_data)
            except ValidationError as exc:
                logger.warning("ItineraryOptionsModel validation failed, using candidate fallback: %s", exc)
                options = _build_options_from_candidates(
                    destination=destination,
                    persona_type=persona_type,
                    day_count=day_count,
                    candidates=search_candidates,
                    confirmed=confirmed,
                    parsed=parsed,
                )
            else:
                options = _normalize_options(
                    raw_options=raw_options,
                    destination=destination,
                    persona_type=persona_type,
                    day_count=day_count,
                    candidates=search_candidates,
                    confirmed=confirmed,
                    parsed=parsed,
                    corridor_origin=corridor_origin,
                    corridor_dest=corridor_dest,
                )
            options = _enforce_day_structure(options, day_count, parsed)

            # Log every option for dataflow visibility during development.
            logger.info("Options generated for '%s' (%d days):", options.destination, len(options.days))
            for day_opt in options.days:
                logger.info("  Day %d — %d options:", day_opt.day, len(day_opt.options))
                for place in day_opt.options:
                    logger.info(
                        "    [%s] %s | must_see=%s | duration=%s",
                        place.place_id, place.name, place.must_see, place.suggested_duration,
                    )
                    logger.info("      address  : %s", place.address)
                    logger.info("      hours    : %s", place.hours_of_operation)
                    logger.info("      note     : %s", place.persona_note)

            options_dict = options.model_dump()
            options_json = json.dumps({"mode": "options", "data": options_dict})

            place_photos = dict(ctx.session.state.get("place_photos") or {})
            for day_opt in options.days:
                for place in day_opt.options:
                    if place.place_id and place.photo_url:
                        place_photos[place.place_id] = place.photo_url

            # Write options to state so reconnecting SSE clients and the server
            # can broadcast an itinerary_options event.  We do NOT write to
            # "itinerary" here — that key is reserved for the finalised itinerary
            # and its presence is what lets the orchestrator continue past this agent.
            yield Event(
                author=self.name,
                actions=EventActions(
                    state_delta={
                        "itinerary_options": options_dict,
                        "place_photos": place_photos,
                        "tool_usage": updated_usage.model_dump(),
                    }
                ),
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=options_json)],
                ),
            )

        else:
            logger.warning(
                "Unrecognised mode %r in itinerary response. Raw:\n%s", mode, raw
            )
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=raw)]),
            )


itinerary_agent = ItineraryAgent(name="itinerary")
