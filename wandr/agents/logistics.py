from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types
from wandr.models.route import RouteModel, RouteStop

LOGISTICS_PROMPT = "MOCK LOGISTICS PROMPT"

class LogisticsAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        print("arrived at logistics agent")
        
        # Populate session state with mock RouteModel
        ctx.session.state["route"] = RouteModel(
            stops=[
                RouteStop(
                    place_id="sensoji_id",
                    order=1,
                    travel_time_from_prev_min=0,
                    lat=35.7147,
                    lng=139.7967
                ),
                RouteStop(
                    place_id="edo_museum_id",
                    order=2,
                    travel_time_from_prev_min=15,
                    lat=35.6963,
                    lng=139.7964
                )
            ],
            total_travel_min=15
        )
        
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text="Logistics route optimization completed.")]
            )
        )

logistics_agent = LogisticsAgent(name="logistics")
