import json
import logging
import re
from collections import defaultdict
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import Client, types
from pydantic import ValidationError

from ai.models.place import PlaceSearchResult
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

You operate in two modes:

### Mode 1 — Present Options
Use this mode unless the user explicitly says they are ready to finalise.

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

### Mode 2 — Finalise Itinerary
Use this mode ONLY when the user's most recent message explicitly confirms they
are done selecting (e.g. "Finalize my itinerary", "I'm happy with these").

Output ONLY a raw JSON object matching this schema:
{{
  "mode": "final",
  "data": {{
    "destination": "<destination>",
    "days": [
      {{
        "day": 1,
        "stops": [
          {{
            "place_id": "<same id from options>",
            "name": "<place name>",
            "address": "<address>",
            "day": 1,
            "order": 1
          }}
        ]
      }}
    ]
  }}
}}
"""

_client = Client()


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


def _day_count_from_duration(duration: str | None) -> int:
    if not duration:
        return 1
    match = re.search(r"\d+", duration)
    if not match:
        return 1
    return max(1, int(match.group(0)))


def _search_limit_for_days(day_count: int) -> int:
    return max(6, min(18, day_count * 6))


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
    if candidate.editorial_summary:
        return candidate.editorial_summary
    return f"A notable stop in {candidate.address}."


def _default_persona_note(candidate: PlaceSearchResult, persona_type: str) -> str:
    types = ", ".join(candidate.types[:2]) or "local highlights"
    return f"Fits a {persona_type} itinerary with its focus on {types}."


def _is_must_see(candidate: PlaceSearchResult) -> bool:
    if candidate.rating is None:
        return False
    return candidate.rating >= 4.5 or (candidate.user_rating_count or 0) >= 15000


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
) -> ItineraryOptionsModel:
    day_numbers = list(range(1, day_count + 1))
    options_by_day: dict[int, list[PlaceOptionModel]] = {day: [] for day in day_numbers}
    seen_place_ids: set[str] = set()

    for place in sorted(confirmed, key=lambda item: (item.get("day", 1), item.get("order", 999))):
        candidate = _candidate_from_confirmed_place(place)
        if candidate.place_id in seen_place_ids:
            continue
        options_by_day.setdefault(place.get("day", 1), []).append(
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

    per_day_target = max(1, min(5, (len(candidates) + max(day_count, 1) - 1) // max(day_count, 1)))
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


def _normalize_options(
    raw_options: ItineraryOptionsModel,
    destination: str,
    persona_type: str,
    day_count: int,
    candidates: list[PlaceSearchResult],
    confirmed: list[dict],
) -> ItineraryOptionsModel:
    candidate_map = {candidate.place_id: candidate for candidate in candidates}
    normalized_by_day: dict[int, list[PlaceOptionModel]] = {day: [] for day in range(1, day_count + 1)}
    seen_place_ids: set[str] = set()

    for day in raw_options.days:
        normalized_by_day.setdefault(day.day, [])
        for option in day.options:
            candidate = candidate_map.get(option.place_id)
            if candidate is None or candidate.place_id in seen_place_ids:
                continue
            normalized_by_day[day.day].append(
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

    for place in sorted(confirmed, key=lambda item: (item.get("day", 1), item.get("order", 999))):
        candidate = candidate_map.get(place["place_id"]) or _candidate_from_confirmed_place(place)
        day = place.get("day", 1)
        existing_ids = {option.place_id for option in normalized_by_day.setdefault(day, [])}
        if candidate.place_id in existing_ids:
            continue
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

    fallback_options = _build_options_from_candidates(destination, persona_type, day_count, candidates, confirmed)
    fallback_by_day = {day.day: list(day.options) for day in fallback_options.days}
    for day in range(1, day_count + 1):
        if normalized_by_day.get(day):
            continue
        normalized_by_day[day] = fallback_by_day.get(day, [])

    days = [
        DayOptionsModel(day=day, options=normalized_by_day.get(day, []))
        for day in range(1, day_count + 1)
        if normalized_by_day.get(day)
    ]
    return ItineraryOptionsModel(destination=destination, days=days)


def _build_final_itinerary(destination: str, confirmed: list[dict]) -> ItineraryModel:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for place in confirmed:
        grouped[place.get("day", 1)].append(place)

    days: list[ItineraryDay] = []
    for day_number in sorted(grouped):
        ordered_places = sorted(grouped[day_number], key=lambda item: item.get("order", 999))
        stops = [
            StopModel(
                place_id=place["place_id"],
                name=place.get("name", "Unknown"),
                address=place.get("address", "Unknown"),
                day=day_number,
                order=index,
            )
            for index, place in enumerate(ordered_places, start=1)
        ]
        if stops:
            days.append(ItineraryDay(day=day_number, stops=stops))

    return ItineraryModel(destination=destination, days=days)


async def _call_model(
    history: list[types.Content],
    system_prompt: str,
) -> str:
    """Single Gemini call; returns stripped response text."""
    response = await _client.aio.models.generate_content(
        model=settings.model_name,
        contents=history,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        ),
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
        day_count = _day_count_from_duration(persona_dict.get("duration"))
        persona_type = persona_dict.get("type", "local-life")

        if itinerary_action == "finalize" and confirmed:
            itinerary = _build_final_itinerary(destination, confirmed)
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
            limit=_search_limit_for_days(day_count),
        )
        for place in confirmed:
            if place.get("place_id") and place["place_id"] not in {candidate.place_id for candidate in search_candidates}:
                search_candidates.append(_candidate_from_confirmed_place(place))

        # Build system prompt, injecting confirmed places + refinement text.
        system_prompt = ITINERARY_SYSTEM_PROMPT.format(
            destination=destination,
            duration=persona_dict.get("duration", "Unknown"),
            type=persona_type,
            pace=persona_dict.get("pace", "Unknown"),
            budget=persona_dict.get("budget", "Unknown"),
            notes=persona_dict.get("notes", ""),
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
                )
            else:
                options = _normalize_options(
                    raw_options=raw_options,
                    destination=destination,
                    persona_type=persona_type,
                    day_count=day_count,
                    candidates=search_candidates,
                    confirmed=confirmed,
                )

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

            # Write options to state so reconnecting SSE clients and the server
            # can broadcast an itinerary_options event.  We do NOT write to
            # "itinerary" here — that key is reserved for the finalised itinerary
            # and its presence is what lets the orchestrator continue past this agent.
            yield Event(
                author=self.name,
                actions=EventActions(state_delta={"itinerary_options": options_dict}),
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=options_json)],
                ),
            )

        elif mode == "final" and inner_data:
            try:
                itinerary = ItineraryModel.model_validate(inner_data)
            except ValidationError as exc:
                logger.error("ItineraryModel validation failed: %s", exc)
                yield Event(
                    author=self.name,
                    content=types.Content(role="model", parts=[types.Part(text=raw)]),
                )
                return

            logger.info("Itinerary finalised for '%s' (%d days):", itinerary.destination, len(itinerary.days))
            for day in itinerary.days:
                logger.info("  Day %d — %d stops:", day.day, len(day.stops))
                for stop in day.stops:
                    logger.info(
                        "    Stop %d: [%s] %s — %s",
                        stop.order, stop.place_id, stop.name, stop.address,
                    )

            yield Event(
                author=self.name,
                actions=EventActions(state_delta={"itinerary": itinerary.model_dump()}),
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Itinerary finalised.")],
                ),
            )

            # Log predicted state after applying the state delta
            predicted_state = {**ctx.session.state, "itinerary": itinerary.model_dump()}
            logger.info("ItineraryAgent state after finalize itinerary was hit and processed: %s", predicted_state)

        else:
            logger.warning(
                "Unrecognised mode %r in itinerary response. Raw:\n%s", mode, raw
            )
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=raw)]),
            )


itinerary_agent = ItineraryAgent(name="itinerary")
