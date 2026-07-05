import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

from ai.models.tool_usage import load_tool_usage, merge_tool_usage, usage_from_route
from ai.models.route import RouteModel, RouteStop
from ai.models.trip import ItineraryModel, StopModel
from ai.tools.exceptions import MapsAPIError
from ai.tools.maps import get_directions, get_place_details

logger = logging.getLogger(__name__)

# Tokyo fallback when place details have no coordinates (e.g. LLM-generated place IDs)
_DEFAULT_LAT = 35.6812
_DEFAULT_LNG = 139.7671


async def run_logistics(itinerary: ItineraryModel) -> RouteModel:
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
        place = await get_place_details(stop.place_id)
        lat = place.lat if place.lat is not None else _DEFAULT_LAT
        lng = place.lng if place.lng is not None else _DEFAULT_LNG

        travel_min = 0
        travel_source = "none"
        if index > 0:
            prev = ordered[index - 1]
            try:
                leg = await get_directions(prev.place_id, stop.place_id)
                travel_min = int(leg.get("duration_min", 0))
                travel_source = "api" if leg.get("source") == "api" else "none"
                total_travel_min += travel_min
            except MapsAPIError as exc:
                logger.warning(
                    "Skipping synthetic travel leg for %s -> %s: %s",
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
                place_source=place.source,
                travel_source=travel_source,
            )
        )

    logger.info(
        "Route built for %s: %d stops, %d min total walking",
        itinerary.destination,
        len(route_stops),
        total_travel_min,
    )
    return RouteModel(stops=route_stops, total_travel_min=total_travel_min)


class LogisticsAgent(BaseAgent):
    """Builds ordered route + map pins after stop processing completes."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if ctx.session.state.get("route"):
            logger.debug("LogisticsAgent skipping — route already in state.")
            return

        itinerary_dict = ctx.session.state.get("itinerary")
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
        route = await run_logistics(itinerary)
        current_usage = load_tool_usage(ctx.session.state.get("tool_usage"))
        updated_usage = merge_tool_usage(current_usage, usage_from_route(route))

        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "route": route.model_dump(),
                    "tool_usage": updated_usage.model_dump(),
                }
            ),
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=(
                            f"Route ready: {len(route.stops)} stops, "
                            f"{route.total_travel_min} min walking between them."
                        )
                    )
                ],
            ),
        )


logistics_agent = LogisticsAgent(name="logistics")
