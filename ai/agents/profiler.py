import json
import logging
import re
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import Client, types
from pydantic import ValidationError

from ai.models.persona import PersonaModel
from ai.config.settings import settings
from ai.agents.model_fallback import generate_with_fallback

logger = logging.getLogger(__name__)

PROFILER_SYSTEM_PROMPT = """\
You are the Profiler for Wandr, an AI travel guide. Your job is to collect the
minimum information needed to plan a personalised trip and classify the user's
travel persona from the conversation so far.

## Required fields
You MUST have ALL THREE of these before producing a persona:
- destination — where the user wants to go (city, region, or country)
- duration — how long the trip or outing will last (e.g. "2 days", "7 hours", "a weekend").
  Preserve the user's unit exactly: if they say "7 hours", output "7 hours" — never convert to days.
- transit_preference — how the user prefers to get around (driving, transit, walking, or mixed). Do NOT guess this. If they haven't explicitly mentioned it, you MUST ask a clarifying question.

## Optional fields
- current_location — if the user mentions they are already at a specific location
  or landmark (e.g. "under the CN tower", "at the airport"), capture it here.

## Edge Cases & Clarifications
- If the user's message is completely unrelated to travel, exploring, or planning a trip (e.g. asking for a recipe, coding help, or random facts), refuse politely and steer them back to travel planning. Do NOT extract fields.
- If the user provides a current_location but NO explicit destination, infer the
  destination to be the city/area of the current location (e.g., "I'm under the CN tower" -> destination = "Toronto").
- If the user provides a short duration (e.g. "2 hours") for a destination that is
  physically far from their current_location (e.g. "I'm in Toronto, want to explore Tokyo in 2 hours"),
  this is impossible. Ask a clarifying question about this.
- However, if they are planning a future trip with a reasonable duration (e.g., "I'm in Toronto, want to explore Tokyo for 3 days"), that is perfectly fine.

## If ANY required field is missing or conflicts exist
Ask the single most important missing question or point out the impossibility.
Be short and friendly.
Examples:
  "Where are you heading?"
  "How much time do you have to explore?"
  "How do you prefer to get around? (e.g. walking, transit, driving)"
  "You're in Toronto but want to explore Tokyo in 2 hours — are you planning a future trip?"
Do NOT output JSON. Output the question only — nothing else.

## If you have ALL required fields
Determine the following and output ONLY a raw JSON object (no markdown fences,
no commentary, nothing else before or after the braces):

{
  "destination": "<city or region>",
  "duration": "<e.g. 2 hours, 3 days>",
  "transit_preference": "<one of: driving | transit | walking | mixed>",
  "current_location": "<specific landmark/location or null>",
  "type": "<one of: foodie | artist | historian | adventurer | local-life | tourist>",
  "pace": "<one of: relaxed | moderate | packed>",
  "budget": "<one of: budget | mid | luxury>",
  "notes": "<any special requests, interests, dietary needs, must-sees, etc. — empty string if none>"
}

Rules for each field:
- transit_preference: Determine from the user's input (e.g., "I have a rental car" -> driving).
- type: if the user explicitly says "I'm a foodie" etc., use that directly.
  Otherwise infer from language clues. Default to "tourist" if ambiguous.
- pace: infer from "take it easy", "see as much as possible", etc. Default "moderate".
- budget: infer from "backpacking", "boutique", "Michelin", etc. Default "mid".
- notes: preserve the user's own wording. Use "" if nothing extra was mentioned.
"""

_client = Client()
_MODEL_FALLBACKS = [m.strip() for m in settings.model_fallbacks.split(",") if m.strip()]


def _extract_json(raw: str) -> str | None:
    """
    Pull the first balanced JSON object from raw text.
    Returns the JSON string if found, None otherwise.
    """
    start = raw.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(raw)):
        ch = raw[i]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]

    return None


def _normalise_enum(value: str | None, mapping: dict[str, str], fallback: str) -> str:
    if not value:
        return fallback
    v = value.strip().lower()
    return mapping.get(v, fallback)


def _extract_named_fields(text: str) -> dict[str, str]:
    """
    Extract structured fields from run_pipeline's message format:
      Destination: ...
      Duration: ...
      Current location: ...
    """
    extracted: dict[str, str] = {}
    field_patterns = {
        "destination": r"(?mi)^Destination:\s*(.+)$",
        "duration": r"(?mi)^Duration:\s*(.+)$",
        "current_location": r"(?mi)^Current location:\s*(.+)$",
        "transit_preference": r"(?mi)^Transit preference:\s*(.+)$",
        "notes": r"(?mi)^Vibe/Description:\s*(.+)$",
    }
    for key, pattern in field_patterns.items():
        match = re.search(pattern, text)
        if match:
            extracted[key] = match.group(1).strip()

    # Handle common unlabelled shorthand from free-form messages
    # (e.g. "Tokyo for 3 days", "3 days in Tokyo").
    if "destination" not in extracted or "duration" not in extracted:
        patterns = [
            (
                r"(?i)\b(?:in|to|visit(?:ing)?|explore|around)\s+([A-Za-z][A-Za-z\s\-.']{1,80}?)\s+for\s+(\d+\s*(?:hours?|hrs?|days?|weeks?|months?))\b",
                "destination_first",
            ),
            (
                r"(?i)\bfor\s+(\d+\s*(?:hours?|hrs?|days?|weeks?|months?))\s+(?:in|at)\s+([A-Za-z][A-Za-z\s\-.']{1,80})\b",
                "duration_first",
            ),
        ]
        for pattern, order in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            if order == "destination_first":
                destination_candidate = match.group(1).strip()
                duration_candidate = match.group(2).strip()
            else:
                duration_candidate = match.group(1).strip()
                destination_candidate = match.group(2).strip()
            if "destination" not in extracted and destination_candidate:
                extracted["destination"] = destination_candidate
            if "duration" not in extracted and duration_candidate:
                extracted["duration"] = duration_candidate
            break
    return extracted


def _duration_is_short(duration: str | None) -> bool:
    """
    Consider hour-scale durations as potentially impossible for international travel.
    """
    if not duration:
        return False
    duration_lower = duration.lower()
    if "hour" in duration_lower or "hr" in duration_lower:
        return True
    return False


def _looks_impossible_trip(
    current_location: str | None,
    destination: str | None,
    duration: str | None,
) -> bool:
    """
    Keep a safeguard for impossible requests, but only with high confidence.
    We only flag when:
      - duration is hour-scale
      - both locations provide explicit country suffixes that differ
    """
    if not (_duration_is_short(duration) and current_location and destination):
        return False

    def country_suffix(loc: str) -> str | None:
        parts = [p.strip().lower() for p in loc.split(",") if p.strip()]
        if len(parts) >= 2:
            return parts[-1]
        return None

    current_country = country_suffix(current_location)
    destination_country = country_suffix(destination)
    if current_country and destination_country and current_country != destination_country:
        return True
    return False


def _persona_from_json_or_none(raw: str) -> PersonaModel | None:
    json_str = _extract_json(raw)
    if not json_str:
        return None

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    # Normalise common enum variants before strict model validation.
    data["transit_preference"] = _normalise_enum(
        data.get("transit_preference"),
        {
            "drive": "driving",
            "car": "driving",
            "driving": "driving",
            "public transit": "transit",
            "public_transport": "transit",
            "transit": "transit",
            "subway": "transit",
            "bus": "transit",
            "walk": "walking",
            "walking": "walking",
            "mixed": "mixed",
            "either": "mixed",
            "any": "mixed",
        },
        "mixed",
    )
    data["type"] = _normalise_enum(
        data.get("type"),
        {
            "foodie": "foodie",
            "artist": "artist",
            "historian": "historian",
            "adventurer": "adventurer",
            "adventure": "adventurer",
            "local-life": "local-life",
            "local life": "local-life",
            "local": "local-life",
            "tourist": "tourist",
        },
        "tourist",
    )
    data["pace"] = _normalise_enum(
        data.get("pace"),
        {
            "relaxed": "relaxed",
            "slow": "relaxed",
            "moderate": "moderate",
            "balanced": "moderate",
            "packed": "packed",
            "fast": "packed",
        },
        "moderate",
    )
    data["budget"] = _normalise_enum(
        data.get("budget"),
        {
            "budget": "budget",
            "cheap": "budget",
            "mid": "mid",
            "moderate": "mid",
            "mid-range": "mid",
            "luxury": "luxury",
            "high": "luxury",
            "premium": "luxury",
        },
        "mid",
    )
    if "notes" not in data or data["notes"] is None:
        data["notes"] = ""

    try:
        return PersonaModel.model_validate(data)
    except ValidationError:
        return None


class ProfilerAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if ctx.session.state.get("persona"):
            logger.debug("ProfilerAgent skipping because persona is already in state.")
            return

        logger.debug("ProfilerAgent building conversation history from session events")

        # Reconstruct the conversation history so the model sees the full context
        # across multiple turns, not just the latest message.
        history: list[types.Content] = []
        for event in ctx.session.events:
            if event.content and event.content.parts and event.content.role in ("user", "model"):
                history.append(event.content)

        if not history:
            logger.warning("Profiler received an empty conversation history")
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Hi! Where would you like to travel, and for how many days?")],
                ),
            )
            return

        last_user_msg = next((m.parts[0].text for m in reversed(history) if m.role == "user" and m.parts), "Unknown")
        logger.info("Profiler processing user prompt: %s", last_user_msg)

        response = await generate_with_fallback(
            client=_client,
            primary_model=settings.model_name,
            fallback_models=_MODEL_FALLBACKS,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=PROFILER_SYSTEM_PROMPT,
                max_output_tokens=settings.gemini_max_output_tokens_profiler,
            ),
            call_label="Profiler.generate_content",
        )

        raw = (response.text or "").strip()
        logger.debug("Profiler raw LLM output: %s", raw)

        # Try to interpret the response as a PersonaModel JSON.
        persona = _persona_from_json_or_none(raw)
        if persona is None:
            logger.warning("Profiler output was not a valid persona JSON. raw=%s", raw)

        # Fallback path: if required fields are present in the structured user payload and
        # request is not clearly impossible, force one strict JSON retry instead of clarifying.
        combined_user_text = "\n".join(
            m.parts[0].text for m in history if m.role == "user" and m.parts and m.parts[0].text
        )
        fields = _extract_named_fields(combined_user_text)
        has_required_fields = bool(fields.get("destination")) and bool(fields.get("duration")) and bool(fields.get("transit_preference"))
        impossible_trip = _looks_impossible_trip(
            fields.get("current_location"),
            fields.get("destination"),
            fields.get("duration"),
        )
        logger.info(
            "Profiler structured extraction: has_required=%s impossible_trip=%s destination=%r duration=%r current_location=%r",
            has_required_fields,
            impossible_trip,
            fields.get("destination"),
            fields.get("duration"),
            fields.get("current_location"),
        )

        if persona is None and has_required_fields and not impossible_trip:
            retry_prompt = (
                "Output only a JSON object for PersonaModel using these guaranteed fields:\n"
                f'- destination: "{fields["destination"]}"\n'
                f'- duration: "{fields["duration"]}"\n'
                f'- current_location: "{fields.get("current_location", "")}"\n'
                f'- transit_preference: "{fields.get("transit_preference", "mixed")}"\n'
                f'- notes: "{fields.get("notes", "")}"\n'
                "Fill missing persona dimensions with sensible defaults if uncertain."
            )
            retry_response = await generate_with_fallback(
                client=_client,
                primary_model=settings.model_name,
                fallback_models=_MODEL_FALLBACKS,
                contents=[types.Content(role="user", parts=[types.Part(text=retry_prompt)])],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=settings.gemini_max_output_tokens_profiler,
                ),
                call_label="Profiler.retry_generate_content",
            )
            retry_raw = (retry_response.text or "").strip()
            logger.debug("Profiler retry raw output: %s", retry_raw)
            persona = _persona_from_json_or_none(retry_raw)

        if persona is None and has_required_fields and not impossible_trip:
            # Last-resort deterministic fallback to avoid false clarification loops.
            persona = PersonaModel(
                destination=fields["destination"],
                duration=fields["duration"],
                current_location=fields.get("current_location"),
                transit_preference=_normalise_enum(
                    fields.get("transit_preference"),
                    {
                        "drive": "driving",
                        "car": "driving",
                        "driving": "driving",
                        "public transit": "transit",
                        "transit": "transit",
                        "walk": "walking",
                        "walking": "walking",
                        "mixed": "mixed",
                    },
                    "mixed",
                ),
                type="tourist",
                pace="moderate",
                budget="mid",
                notes=fields.get("notes", ""),
            )
            logger.info(
                "Profiler used deterministic fallback persona for complete request: %s",
                persona.model_dump(),
            )

        if persona is not None:
            # Preserve the existing current_location from session state unless the user
            # explicitly signals a location change in their message. current_location is a
            # one-time fact (where the trip starts from) — it must never be silently cleared
            # or re-derived on a refine pass.
            existing_persona = ctx.session.state.get("persona") or {}
            existing_origin = existing_persona.get("current_location")
            if existing_origin:
                location_change_signals = (
                    "actually i'm",
                    "i'm now at",
                    "i am now at",
                    "starting from",
                    "leaving from",
                    "departing from",
                    "new starting point",
                )
                user_text_lower = combined_user_text.lower()
                user_changed_origin = any(sig in user_text_lower for sig in location_change_signals)
                if not user_changed_origin:
                    # Carry the original origin forward unconditionally.
                    persona = persona.model_copy(update={"current_location": existing_origin})
                    logger.debug(
                        "Profiler preserved existing current_location=%r on refine pass.",
                        existing_origin,
                    )

            # We have a valid persona — write it to state and let the pipeline continue.
            logger.info("Profiler successfully resolved persona: %s", persona.model_dump())

            payload_text = json.dumps(persona.model_dump())
            yield Event(
                author=self.name,
                actions=EventActions(state_delta={"persona": persona.model_dump()}),
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=payload_text)],
                ),
            )
        else:
            # The model asked a clarifying question — surface it to the user.
            # Nothing is written to state, so the orchestrator knows to pause.
            clarification_text = raw or "Where are you heading, and how much time do you have?"
            logger.info("Profiler is asking a clarifying question: %s", clarification_text)
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=clarification_text)],
                ),
            )


profiler_agent = ProfilerAgent(name="profiler")
