import json
import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import Client, types
from google.genai.errors import ClientError
from pydantic import ValidationError

from ai.config.settings import settings
from ai.models.persona import PersonaModel
from ai.models.place import PlaceDetails
from ai.models.research import StopResearchResult
from ai.models.trip import StopModel
from ai.tools.maps import get_place_details

logger = logging.getLogger(__name__)


def _gemini_client() -> Client:
    return Client(api_key=settings.gemini_api_key)

STOP_RESEARCH_PROMPT = """\
You are the Stop Research agent for Wandr, a personalized audio travel guide.

## Your job

Enrich **one itinerary stop** with real, persona-relevant facts so the Narrator agent can \
write a 60–90 second audio script. You research — you do **not** write narration.

You run once per stop, often in parallel with other stops. Focus only on the stop described \
in the user message.

## Workflow

1. Read the stop, traveler persona, and place data from the user message.
2. Place data comes from `get_place_details` — use it as your only source of truth.
3. Filter and rank what you learn for this persona type.
4. Return a single `StopResearchResult` object (structured output).

## Persona focus

Tailor `context_facts` and `persona_score` to the persona `type`:

| type | prioritize |
|------|------------|
| foodie | restaurants, markets, street food, local dishes, dining culture |
| artist | galleries, murals, architecture, design, creative scenes |
| historian | monuments, museums, heritage, founding stories, historical events |
| adventurer | parks, trails, viewpoints, active or outdoor experiences |
| local-life | neighborhoods, cafes, everyday rituals, where locals actually go |

Also respect `pace` (relaxed → fewer, deeper facts; packed → more highlights) and \
`budget` (flag splurge vs budget-friendly options when relevant). Use `notes` for any \
extra user preferences.

## Output fields

Return exactly these fields:

- **place_id**, **name**, **address** — copy from the stop input; confirm against place data \
if values differ.
- **persona_score** — float from 0.0 to 1.0. How well this stop fits the traveler persona. \
0.8+ = strong fit, 0.5–0.7 = decent, below 0.5 = weak fit (still return facts, but be honest).
- **context_facts** — 5 to 8 short, factual strings the Narrator can weave into a script. \
Each fact should be one idea (1–2 sentences max). Prioritize: what makes this place special, \
one surprising detail, one practical tip, and anything tied to the persona. \
Ground every fact in the provided place data — no invented history or reviews.
- **opening_hours** — human-readable summary from place data, or "Unknown".
- **is_seasonal** — true if place data shows seasonal hours, temporary closure, or unreliable access.

## Rules

- One stop per invocation. Ignore other stops.
- Facts must come from the provided place data — never hallucinate.
- Do not write audio scripts or tour-guide prose.
- Do not recommend other nearby places.
- Write in English.
- If place data is sparse, return fewer `context_facts` rather than inventing details.
"""


def build_stop_research_context(stop: StopModel, persona: PersonaModel) -> str:
    """Build the per-invocation user message injected when the agent runs for one stop."""
    return f"""\
Research this stop and return a StopResearchResult.

## Stop
- place_id: {stop.place_id}
- name: {stop.name}
- address: {stop.address}
- day: {stop.day}
- order: {stop.order}

## Traveler persona
- type: {persona.type}
- pace: {persona.pace}
- budget: {persona.budget}
- notes: {persona.notes or "(none)"}
"""


def _format_place_data(place: PlaceDetails) -> str:
    return f"""\
## Place data (from get_place_details)
- place_id: {place.place_id}
- name: {place.name}
- address: {place.address}
- opening_hours: {place.opening_hours}
- editorial_summary: {place.editorial_summary or "(none)"}
- rating: {place.rating}
- user_rating_count: {place.user_rating_count}
- types: {", ".join(place.types) or "(none)"}
- business_status: {place.business_status}
- is_seasonal_or_closed: {place.is_seasonal_or_closed}
- data_source: {place.source}
"""


async def run_stop_research(stop: StopModel, persona: PersonaModel) -> StopResearchResult:
    """Fetch place data, then ask Gemini to produce a validated StopResearchResult."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    place = await get_place_details(stop.place_id)
    user_message = (
        build_stop_research_context(stop, persona)
        + "\n\n"
        + _format_place_data(place)
        + "\n\nProduce the structured StopResearchResult JSON."
    )

    client = _gemini_client()
    try:
        response = await client.aio.models.generate_content(
            model=settings.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=user_message)],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=STOP_RESEARCH_PROMPT,
                response_mime_type="application/json",
                response_schema=StopResearchResult,
            ),
        )
    except ClientError as exc:
        if "API_KEY_SERVICE_BLOCKED" in str(exc):
            raise RuntimeError(
                "Gemini API key is blocked for generativelanguage.googleapis.com. "
                "Create a new key at https://aistudio.google.com/apikey and set "
                "GEMINI_API_KEY in .env — do not reuse your Places/Maps Cloud key."
            ) from exc
        raise

    raw = (response.text or "").strip()
    logger.debug("Stop research raw output: %s", raw)

    try:
        return StopResearchResult.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        logger.error("Stop research JSON validation failed: %s", exc)
        raise RuntimeError(f"Stop research returned invalid JSON: {raw}") from exc



class StopResearchAgent(BaseAgent):
    """ADK wrapper — delegates to run_stop_research when stop + persona are in state."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # Read the stop-scoped key set by the stop processor for this invocation
        stop_id = ctx.session.state.get("temp:active_stop_id", "unknown")
        stop_name = ctx.session.state.get(f"temp:stop:{stop_id}:name", "Unknown Stop")
        print(f"arrived at stop research agent: {stop_name}")

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"Stop research completed for {stop_name}.")],
            ),
        )


stop_research_agent = StopResearchAgent(name="stop_research")
