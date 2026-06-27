from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types
from wandr.models.persona import PersonaModel

PROFILER_PROMPT = "MOCK PROFILER PROMPT"

class ProfilerAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        print("arrived at profiler agent")
        
        # Populate session state with mock PersonaModel
        ctx.session.state["persona"] = PersonaModel(
            type="historian",
            pace="moderate",
            budget="mid",
            notes="Interested in Edo history and temples"
        )
        
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text="Profiler completed. Persona set to historian.")]
            )
        )

profiler_agent = ProfilerAgent(name="profiler")
