import json
import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import Client, types
from pydantic import ValidationError

from ai.models.route import RouteModel, RouteStop
from ai.models.trip import ItineraryModel
from ai.config.settings import settings
from ai.tools.maps import get_directions

logger = logging.getLogger(__name__)

LOGISTICS_PROMPT = """\
You are the Logistics Agent for Wandr.
Your job is to take the finalized itinerary and order the stops optimally for each day, \
accounting for travel times, opening hours, and practical flow.

## The Itinerary
{itinerary_json}

## Transit Preference
{transit_preference}

## Your Task
1. Analyze the stops for each day.
2. Determine a logical order for the stops to minimize travel time.
3. Explicitly add a `break_duration` (in minutes) for lunch, dinner, or rest between stops if needed.
4. Set the `transit_mode` according to the user's transit preference ("driving", "transit", "walking", or mix if "mixed").
5. Output the route matching the exact JSON schema provided.

Output ONLY a raw JSON object matching this schema exactly (no markdown, no prose):
{{
  "stops": [
    {{
      "place_id": "<place_id>",
      "day": 1,
      "order": 1,
      "travel_time_from_prev_min": 0,
      "transit_mode": "walking",
      "break_duration": 0,
      "lat": 0.0,
      "lng": 0.0
    }}
  ],
  "total_travel_min": 0
}}
"""

_client = Client()


def _extract_json(raw: str) -> str | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return None


class LogisticsAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        logger.info("LogisticsAgent starting.")

        itinerary_dict = ctx.session.state.get("itinerary")
        if not itinerary_dict:
            logger.error("No itinerary found in session state.")
            return

        itinerary = ItineraryModel.model_validate(itinerary_dict)

        persona_dict = ctx.session.state.get("persona", {})

        system_prompt = LOGISTICS_PROMPT.format(
            itinerary_json=itinerary.model_dump_json(indent=2),
            transit_preference=persona_dict.get("transit_preference", "mixed")
        )

        logger.info("Calling Gemini for route optimization...")
        response = await _client.aio.models.generate_content(
            model=settings.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text="Please generate the optimized route.")],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=RouteModel,
            ),
        )

        raw = (response.text or "").strip()
        logger.debug("Logistics raw output: %s", raw)

        json_str = _extract_json(raw) or raw
        try:
            route = RouteModel.model_validate_json(json_str)
        except (ValidationError, ValueError) as exc:
            logger.error("Failed to parse RouteModel: %s", exc)
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model", parts=[types.Part(text=f"Logistics failed: {exc}")]
                ),
            )
            return

        # Fetch actual directions and coordinates for the ordered stops
        total_travel = 0
        for i in range(len(route.stops)):
            current = route.stops[i]
            if i > 0 and route.stops[i - 1].day == current.day:
                prev = route.stops[i - 1]
                directions = await get_directions(
                    prev.place_id, current.place_id, current.transit_mode
                )
                current.travel_time_from_prev_min = (
                    directions.get("duration_seconds", 0) // 60
                )
                current.lat = directions.get("lat", 0.0)
                current.lng = directions.get("lng", 0.0)
                total_travel += current.travel_time_from_prev_min
            else:
                current.travel_time_from_prev_min = 0
                # Just get the place details or directions to itself to get lat/lng
                directions = await get_directions(
                    current.place_id, current.place_id, current.transit_mode
                )
                current.lat = directions.get("lat", 0.0)
                current.lng = directions.get("lng", 0.0)

        route.total_travel_min = total_travel

        logger.info(
            "Logistics routing complete. Total travel min: %d", route.total_travel_min
        )

        yield Event(
            author=self.name,
            actions=EventActions(state_delta={"route": route.model_dump()}),
            content=types.Content(
                role="model",
                parts=[types.Part(text="Logistics route optimization completed.")],
            ),
        )


logistics_agent = LogisticsAgent(name="logistics")
