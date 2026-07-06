import asyncio
import json
import logging
from collections import defaultdict
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import Client, types
from pydantic import BaseModel, ValidationError

from ai.agents.model_fallback import generate_with_fallback
from ai.config.settings import settings
from ai.models.duration import parse_trip_duration
from ai.models.tool_usage import load_tool_usage, merge_tool_usage, usage_from_route
from ai.models.route import RouteModel, RouteStop
from ai.models.trip import ItineraryModel, StopModel
from ai.tools.exceptions import MapsAPIError
from ai.tools.maps import get_directions, get_place_details

logger = logging.getLogger(__name__)

# Tokyo fallback when place details have no coordinates (e.g. LLM-generated place IDs)
_DEFAULT_LAT = 35.6812
_DEFAULT_LNG = 139.7671

_client = Client()
_MODEL_FALLBACKS = [m.strip() for m in settings.model_fallbacks.split(",") if m.strip()]

LOGISTICS_SYSTEM_PROMPT = """\
You are the Logistics Planner for Wandr, an AI travel guide.
Your job is to determine the absolute optimal chronological route sequence for the stops on each day of a trip.

## User Persona
Destination: {destination}
Current Location: {current_location}
Transit Preference: {transit_preference}
Duration: {duration}
Pace: {pace}
Type: {type}

## Provided Stops & Context
{stops_section}

## Your Task
You are given a list of finalized stops grouped by day. For each day, you must output the most optimal chronological sequence of place IDs.
When determining the order, you MUST consider:
1. Geographic proximity (use the coordinates provided to minimize zig-zagging).
2. Opening hours (don't suggest visiting a place before it opens or after it closes).
3. The user's pace and logical resting/eating patterns.
4. The general flow of a day (e.g., start early at popular spots, end at scenic or nightlife areas).

## Day 1 Starting Point (CRITICAL)
- If Current Location is provided (not "Unknown" or empty): Day 1 MUST begin with the stop whose coordinates are geographically nearest to the Current Location. Use the Current Location as the anchor point — route Day 1 outward from there.
- If Current Location is NOT provided: Choose whichever Day 1 stop, when used as the starting point, produces the most geographically efficient overall route for that day (minimizes total travel distance). Do NOT default to the list order — evaluate which stop makes the best anchor.

Output ONLY a raw JSON object (no markdown fences, no commentary) that matches this schema exactly:
{{
  "days": [
    {{
      "day": 1,
      "ordered_place_ids": [
        "<place_id_1>",
        "<place_id_2>"
      ]
    }}
  ]
}}

IMPORTANT:
- Every `place_id` provided in the input MUST be included in the output for its respective day.
- Do not invent any new `place_id`s. Do not inject explicit "lunch" or "rest" stops if they aren't provided — just arrange the provided stops logically.
- Never output prose, never wrap the JSON in markdown fences, never add any text before or after the JSON object.
"""

class DayOrderModel(BaseModel):
    day: int
    ordered_place_ids: list[str]


class LogisticsResponseModel(BaseModel):
    days: list[DayOrderModel]


def _extract_json(raw: str) -> str | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return None


async def _call_model(history: list[types.Content], system_prompt: str) -> str:
    response = await generate_with_fallback(
        client=_client,
        primary_model=settings.model_name,
        fallback_models=_MODEL_FALLBACKS,
        contents=history,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        ),
        call_label="Logistics.generate_content",
    )
    return (response.text or "").strip()


def _build_stops_section(itinerary: ItineraryModel, place_details: dict) -> str:
    lines = []
    for day in itinerary.days:
        lines.append(f"Day {day.day}:")
        for stop in day.stops:
            details = place_details.get(stop.place_id)
            lat = details.lat if details and details.lat is not None else _DEFAULT_LAT
            lng = details.lng if details and details.lng is not None else _DEFAULT_LNG
            hours = details.opening_hours if details and details.opening_hours else "Unknown"
            types_str = ", ".join(details.types) if details and details.types else "Unknown"
            
            lines.append(f"  - Place ID: {stop.place_id}")
            lines.append(f"    Name: {stop.name}")
            lines.append(f"    Types: {types_str}")
            lines.append(f"    Opening Hours: {hours}")
            lines.append(f"    Coordinates: ({lat}, {lng})")
    return "\n".join(lines)


async def _get_optimal_directions(prev_place_id: str, stop_place_id: str, transit_preference: str) -> dict:
    pref = transit_preference.lower()
    
    if pref in ("driving", "transit", "walking"):
        return await get_directions(prev_place_id, stop_place_id, mode=pref)
    
    # If mixed or unknown, fetch all 3 and pick the one with the minimum duration > 0.
    results = await asyncio.gather(
        get_directions(prev_place_id, stop_place_id, mode="driving"),
        get_directions(prev_place_id, stop_place_id, mode="transit"),
        get_directions(prev_place_id, stop_place_id, mode="walking"),
        return_exceptions=True
    )
    
    valid_results = [r for r in results if not isinstance(r, Exception) and r.get("source") == "api" and r.get("duration_min", 0) > 0]
    
    if not valid_results:
        # Fallback if API fails or returns no valid routes
        return {"duration_min": 0, "distance_m": 0, "mode": "walking", "source": "none"}
        
    # Sort by duration_min to find the fastest mode
    valid_results.sort(key=lambda x: x["duration_min"])
    return valid_results[0]


async def run_logistics(itinerary: ItineraryModel, place_details: dict, transit_preference: str = "mixed") -> RouteModel:
    """Order stops by day/order, attach map pins, sum walking times between legs."""
    ordered: list[StopModel] = sorted(
        (stop for day in itinerary.days for stop in day.stops),
        key=lambda s: (s.day, s.order),
    )

    if not ordered:
        return RouteModel(stops=[], total_travel_min=0)

    route_stops: list[RouteStop] = []
    total_travel_min = 0

    for index, stop in enumerate(ordered):
        place = place_details.get(stop.place_id)
        if not place:
            try:
                place = await get_place_details(stop.place_id)
            except Exception as exc:
                logger.error("Failed to fetch place details for %s during route generation: %s", stop.place_id, exc)
                place = None
            
        lat = place.lat if place and place.lat is not None else _DEFAULT_LAT
        lng = place.lng if place and place.lng is not None else _DEFAULT_LNG

        travel_min = 0
        travel_source = "none"
        travel_mode = "none"
        if index > 0:
            prev = ordered[index - 1]
            is_same_day = prev.day == stop.day
            try:
                leg = await _get_optimal_directions(prev.place_id, stop.place_id, transit_preference)
                travel_min = int(leg.get("duration_min", 0))
                travel_mode = leg.get("mode", "unknown")
                if is_same_day:
                    travel_source = "api" if leg.get("source") == "api" else "none"
                else:
                    # Cross-day leg: tag as "overnight" so the UI can present it
                    # as "~N min drive to tomorrow's first stop" rather than in-day travel.
                    travel_source = "overnight"
                total_travel_min += travel_min
            except MapsAPIError as exc:
                logger.warning(
                    "Skipping travel leg for %s -> %s: %s",
                    prev.place_id,
                    stop.place_id,
                    exc,
                )

        route_stops.append(
            RouteStop(
                place_id=stop.place_id,
                order=index + 1,
                travel_time_from_prev_min=travel_min,
                lat=lat,
                lng=lng,
                place_source=place.source if place else "unknown",
                travel_source=travel_source,
                travel_mode=travel_mode,
            )
        )

    logger.info(
        "Route built for %s: %d stops, %d min total travel",
        itinerary.destination,
        len(route_stops),
        total_travel_min,
    )
    return RouteModel(stops=route_stops, total_travel_min=total_travel_min)


class LogisticsAgent(BaseAgent):
    """Builds ordered route + map pins using an LLM to optimize the sequence."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if ctx.session.state.get("route"):
            logger.debug("LogisticsAgent skipping — route already in state.")
            return

        itinerary_dict = ctx.session.state.get("itinerary")
        persona_dict = ctx.session.state.get("persona") or {}
        if not itinerary_dict:
            logger.warning("LogisticsAgent called but itinerary is missing from state.")
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Logistics skipped: no itinerary in session state.")],
                ),
            )
            return

        itinerary = ItineraryModel.model_validate(itinerary_dict)
        
        # Gather place details for all stops to provide context to LLM
        all_stops = [stop for day in itinerary.days for stop in day.stops]
        place_tasks = [get_place_details(s.place_id) for s in all_stops]
        place_results = await asyncio.gather(*place_tasks, return_exceptions=True)
        
        place_details = {}
        for stop, result in zip(all_stops, place_results):
            if not isinstance(result, Exception):
                place_details[stop.place_id] = result
            else:
                logger.warning("Failed to fetch place details for %s: %s", stop.place_id, result)

        system_prompt = LOGISTICS_SYSTEM_PROMPT.format(
            destination=persona_dict.get("destination", itinerary.destination),
            current_location=persona_dict.get("current_location", "Unknown"),
            transit_preference=persona_dict.get("transit_preference", "Unknown"),
            duration=persona_dict.get("duration", "Unknown"),
            pace=persona_dict.get("pace", "Unknown"),
            type=persona_dict.get("type", "Unknown"),
            stops_section=_build_stops_section(itinerary, place_details)
        )
        
        # History (from past messages)
        history: list[types.Content] = []
        for event in ctx.session.events:
            if event.content and event.content.parts and event.content.role in ("user", "model"):
                history.append(event.content)

        logger.info("LogisticsAgent calling Gemini to optimize route...")
        raw = await _call_model(history, system_prompt)
        json_str = _extract_json(raw)
        
        if json_str is None:
            logger.warning("Response did not contain JSON object — retrying...")
            retry_history = history + [
                types.Content(role="model", parts=[types.Part(text=raw)]),
                types.Content(
                    role="user",
                    parts=[types.Part(
                        text=(
                            "Your previous response was not valid JSON. "
                            "Output ONLY the raw JSON object as specified in your instructions."
                        )
                    )],
                ),
            ]
            raw = await _call_model(retry_history, system_prompt)
            json_str = _extract_json(raw)
            
        optimized = False
        if json_str:
            try:
                data = json.loads(json_str)
                logistics_resp = LogisticsResponseModel.model_validate(data)
                
                # Re-order the itinerary based on the LLM's response
                new_days = []
                for day in itinerary.days:
                    ordered_ids = next((d.ordered_place_ids for d in logistics_resp.days if d.day == day.day), [])
                    
                    if not ordered_ids:
                        new_days.append(day)
                        continue
                        
                    stop_map = {s.place_id: s for s in day.stops}
                    new_stops = []
                    order_idx = 1
                    for pid in ordered_ids:
                        if pid in stop_map:
                            new_stops.append(stop_map[pid].model_copy(update={"order": order_idx}))
                            order_idx += 1
                            del stop_map[pid]
                            
                    # Append any missing stops that the LLM forgot
                    for pid, stop in stop_map.items():
                        new_stops.append(stop.model_copy(update={"order": order_idx}))
                        order_idx += 1
                        
                    new_days.append(day.model_copy(update={"stops": new_stops}))
                    
                itinerary = itinerary.model_copy(update={"days": new_days})
                optimized = True
            except Exception as exc:
                logger.error("Failed to parse Logistics LLM response: %s\nRaw:\n%s", exc, raw)
        else:
            logger.error("Logistics LLM failed to produce JSON. Proceeding with unoptimized route.")

        if not optimized:
            logger.info("LogisticsAgent proceeding without LLM optimization due to parsing errors.")
            
        transit_pref = persona_dict.get("transit_preference", "mixed")
        route = await run_logistics(itinerary, place_details, transit_preference=transit_pref)

        # Sanity check: warn when total travel time implausibly exceeds the trip duration.
        # This catches outlier stops (e.g. a stop in the wrong country) that inflate the sum.
        duration_raw = persona_dict.get("duration", "")
        if duration_raw:
            parsed_duration = parse_trip_duration(duration_raw)
            total_hours = parsed_duration.total_hours or (parsed_duration.day_count * 24)
            trip_minutes = total_hours * 60
            if trip_minutes > 0 and route.total_travel_min > trip_minutes:
                logger.warning(
                    "total_travel_min=%d exceeds trip duration of %d min (%s). "
                    "Possible off-route stop in the itinerary.",
                    route.total_travel_min,
                    int(trip_minutes),
                    duration_raw,
                )

        current_usage = load_tool_usage(ctx.session.state.get("tool_usage"))
        updated_usage = merge_tool_usage(current_usage, usage_from_route(route))


        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "route": route.model_dump(),
                    "tool_usage": updated_usage.model_dump(),
                    "itinerary": itinerary.model_dump(),
                }
            ),
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=(
                            f"Route ready (Optimized: {optimized}): {len(route.stops)} stops, "
                            f"{route.total_travel_min} min walking between them."
                        )
                    )
                ],
            ),
        )


logistics_agent = LogisticsAgent(name="logistics")
