from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

STOP_RESEARCH_PROMPT = "MOCK STOP RESEARCH PROMPT"

class StopResearchAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        stop_name = ctx.session.state.get("temp:current_stop_name", "Unknown Stop")
        print(f"arrived at stop research agent: {stop_name}")
        
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"Stop research completed for {stop_name}.")]
            )
        )

stop_research_agent = StopResearchAgent(name="stop_research")
