from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

NARRATOR_PROMPT = "MOCK NARRATOR PROMPT"


class NarratorAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # Read the stop-scoped key set by the stop processor for this invocation
        stop_id = ctx.session.state.get("temp:active_stop_id", "unknown")
        stop_name = ctx.session.state.get(f"temp:stop:{stop_id}:name", "Unknown Stop")
        print(f"arrived at narrator agent: {stop_name}")

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"Narrator script generated for {stop_name}.")],
            ),
        )


narrator_agent = NarratorAgent(name="narrator")
