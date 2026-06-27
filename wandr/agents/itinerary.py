from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types
from wandr.models.trip import ItineraryModel, ItineraryDay, StopModel

ITINERARY_PROMPT = "MOCK ITINERARY PROMPT"

class ItineraryAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        print("arrived at itinerary agent")
        
        # Populate session state with mock ItineraryModel
        ctx.session.state["itinerary"] = ItineraryModel(
            destination="Tokyo",
            days=[
                ItineraryDay(
                    day=1,
                    stops=[
                        StopModel(
                            place_id="sensoji_id",
                            name="Senso-ji",
                            address="Asakusa, Tokyo",
                            day=1,
                            order=1
                        ),
                        StopModel(
                            place_id="edo_museum_id",
                            name="Edo-Tokyo Museum",
                            address="Ryogoku, Tokyo",
                            day=1,
                            order=2
                        )
                    ]
                )
            ]
        )
        
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text="Itinerary completed. Created route with Senso-ji and Edo-Tokyo Museum.")]
            )
        )

itinerary_agent = ItineraryAgent(name="itinerary")
