import logging
from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

from wandr.agents.profiler import profiler_agent
from wandr.agents.itinerary import itinerary_agent
from wandr.pipeline.stop_processor import process_all_stops
from wandr.agents.logistics import logistics_agent

logger = logging.getLogger(__name__)

class OrchestratorAgent(BaseAgent):
    def __init__(self, name: str = "orchestrator"):
        super().__init__(name=name, sub_agents=[profiler_agent, itinerary_agent, logistics_agent])

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        logger.info("Orchestrator starting pipeline execution")

        # 1. Run Profiler
        logger.info("Running Profiler...")
        async for event in profiler_agent.run_async(ctx):
            yield event

        # 2. Run Itinerary
        logger.info("Running Itinerary...")
        async for event in itinerary_agent.run_async(ctx):
            yield event

        # 3. Parallel Stop Processing Fan-out
        itinerary = ctx.session.state.get("itinerary")
        persona = ctx.session.state.get("persona")
        if itinerary and persona:
            logger.info("Running parallel Stop Processor...")
            audio_scripts = await process_all_stops(itinerary, persona, ctx)
            ctx.session.state["audio_scripts"] = audio_scripts.model_dump()
        else:
            logger.error("Missing itinerary or persona in state for stop processor.")

        # 4. Run Logistics
        logger.info("Running Logistics...")
        async for event in logistics_agent.run_async(ctx):
            yield event

        # Final completion event
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text="Orchestration completed successfully.")]
            )
        )

orchestrator_agent = OrchestratorAgent()
