import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

from ai.agents.profiler import profiler_agent
from ai.agents.itinerary import itinerary_agent
from ai.agents.logistics import logistics_agent
from ai.models.trip import ItineraryModel
from ai.models.persona import PersonaModel
from ai.pipeline.stop_processor import process_all_stops

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    def __init__(self, name: str = "orchestrator"):
        super().__init__(
            name=name,
            sub_agents=[profiler_agent, itinerary_agent, logistics_agent],
        )

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        print("arrived at orchestrator agent")
        logger.info("Orchestrator starting pipeline execution")

        # 1. Run Profiler — emits state_delta(persona) which runner applies to ctx.session.state
        logger.info("Running Profiler...")
        async for event in profiler_agent.run_async(ctx):
            yield event

        # Log what the profiler determined so the pipeline output is visible during development.
        # State delta is applied by the runner synchronously as each event is yielded, so
        # ctx.session.state["persona"] is populated by the time we reach here.
        persona_dict = ctx.session.state.get("persona")
        if persona_dict:
            logger.info(
                "Profiler determined persona:\n"
                "  destination   : %s\n"
                "  duration      : %s\n"
                "  current_loc   : %s\n"
                "  type          : %s\n"
                "  pace          : %s\n"
                "  budget        : %s\n"
                "  notes         : %s",
                persona_dict.get("destination"),
                persona_dict.get("duration"),
                persona_dict.get("current_location") or "(none)",
                persona_dict.get("type"),
                persona_dict.get("pace"),
                persona_dict.get("budget"),
                persona_dict.get("notes") or "(none)",
            )
        else:
            logger.info(
                "Profiler asked a clarifying question — pipeline paused, "
                "waiting for user to supply missing information."
            )
            return  # stop here; the clarifying question is already yielded above

        # 2. Run Itinerary — emits state_delta(itinerary) which runner applies to ctx.session.state
        logger.info("Running Itinerary...")
        async for event in itinerary_agent.run_async(ctx):
            yield event

        # 3. Parallel Stop Processing fan-out
        # At this point ctx.session.state reflects the state_delta writes from steps 1 & 2
        # because the runner processes each yielded event synchronously before resuming here.
        itinerary_dict = ctx.session.state.get("itinerary")
        persona_dict = ctx.session.state.get("persona")

        if not itinerary_dict:
            logger.info("Itinerary missing — pipeline paused, waiting for user to select options.")
            return

        if itinerary_dict and persona_dict:
            # Deserialize dicts back to typed models before passing to the pipeline layer
            itinerary = ItineraryModel.model_validate(itinerary_dict)
            persona = PersonaModel.model_validate(persona_dict)

            logger.info("Running parallel Stop Processor...")
            # process_all_stops is a plain async function — no ctx passed (pipeline must not touch ADK)
            audio_scripts = await process_all_stops(itinerary, persona)

            # Emit the result as state_delta so it's persisted via the runner, not via direct mutation
            yield Event(
                author=self.name,
                actions=EventActions(state_delta={"audio_scripts": audio_scripts.model_dump()}),
                content=types.Content(
                    role="model",
                    parts=[types.Part(
                        text=f"Stop processing complete. {len(audio_scripts.scripts)} scripts produced."
                    )],
                ),
            )
        else:
            logger.error("Missing persona in state — skipping stop processor.")

        # 4. Run Logistics — emits state_delta(route) which runner applies to ctx.session.state
        logger.info("Running Logistics...")
        async for event in logistics_agent.run_async(ctx):
            yield event

        # Final completion event
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text="Orchestration completed successfully.")],
            ),
        )


orchestrator_agent = OrchestratorAgent()
orchestrator_agent._adk_origin_app_name = "wandr"
orchestrator_agent._adk_origin_path = __file__
