import json
import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import Client, types
from pydantic import ValidationError

from ai.models.trip import ItineraryModel, ItineraryOptionsModel
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

## Your Task
You have access to Google Search. Use it to find real, popular places (with real
addresses and opening hours) that match the persona. Aim for 3–5 options per day.

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
        lines.append(f"  • {p.get('name', 'Unknown')} (ID: {p.get('place_id', '?')}, Day {p.get('day', '?')})")
    return "\n".join(lines)


def _build_refinement_section(text: str | None) -> str:
    """Format the user's refinement request."""
    if not text:
        return "No refinement requested — generate options normally."
    return f'The user wants to refine the itinerary: "{text}". Incorporate this into your options.'


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
            tools=[types.Tool(google_search=types.GoogleSearch())],
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

        # Build system prompt, injecting confirmed places + refinement text.
        system_prompt = ITINERARY_SYSTEM_PROMPT.format(
            destination=persona_dict.get("destination", "Unknown"),
            duration=persona_dict.get("duration", "Unknown"),
            type=persona_dict.get("type", "Unknown"),
            pace=persona_dict.get("pace", "Unknown"),
            budget=persona_dict.get("budget", "Unknown"),
            notes=persona_dict.get("notes", ""),
            confirmed_section=_build_confirmed_section(confirmed),
            refinement_section=_build_refinement_section(refinement_text),
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
                options = ItineraryOptionsModel.model_validate(inner_data)
            except ValidationError as exc:
                logger.error("ItineraryOptionsModel validation failed: %s", exc)
                yield Event(
                    author=self.name,
                    content=types.Content(role="model", parts=[types.Part(text=raw)]),
                )
                return

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

            # Write options to state so reconnecting SSE clients and the server
            # can broadcast an itinerary_options event.  We do NOT write to
            # "itinerary" here — that key is reserved for the finalised itinerary
            # and its presence is what lets the orchestrator continue past this agent.
            yield Event(
                author=self.name,
                actions=EventActions(state_delta={"itinerary_options": options_dict}),
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=json_str)],
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
