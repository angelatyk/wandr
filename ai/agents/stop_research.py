from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

STOP_RESEARCH_PROMPT = "MOCK STOP RESEARCH PROMPT"


class StopResearchAgent(BaseAgent):
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
