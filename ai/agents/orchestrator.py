import logging
import asyncio
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

from ai.models.tool_usage import load_tool_usage, merge_tool_usage, usage_from_audio_scripts
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
        itinerary_options_dict = ctx.session.state.get("itinerary_options")

        if not itinerary_dict:
            if itinerary_options_dict:
                option_count = sum(len(day.get("options", [])) for day in itinerary_options_dict.get("days", []))
                logger.info(
                    "Itinerary missing but itinerary_options exists (%d options). "
                    "Pipeline paused awaiting user finalize before stop processor/logistics.",
                    option_count,
                )
            else:
                logger.info("Itinerary missing and no itinerary_options in state — pipeline paused.")
            return

        if itinerary_dict and persona_dict:
            # Deserialize dicts back to typed models before passing to the pipeline layer
            itinerary = ItineraryModel.model_validate(itinerary_dict)
            persona = PersonaModel.model_validate(persona_dict)

            logger.info("Finalized itinerary contains %d days.", len(itinerary.days))
            for day in itinerary.days:
                logger.info("  Day %d:", day.day)
                for stop in day.stops:
                    logger.info("    Stop %d: %s (%s)", stop.order, stop.name, stop.place_id)
        # 3. Run Logistics and Stop Processor in parallel
        itinerary_dict = ctx.session.state.get("itinerary")
        needs_audio = itinerary_dict and not ctx.session.state.get("audio_scripts")
        route_exists = bool(ctx.session.state.get("route"))

        logger.info(
            "Preparing parallel logistics & stop processor (has_itinerary=%s route_already_exists=%s needs_audio=%s).",
            bool(itinerary_dict),
            route_exists,
            needs_audio,
        )

        async def run_stop_processor_task():
            logger.info("Running parallel Stop Processor task...")
            plan_id = ctx.session.id
            audio_scripts = await process_all_stops(itinerary, persona, plan_id=plan_id)
            current_usage = load_tool_usage(ctx.session.state.get("tool_usage"))
            updated_usage = merge_tool_usage(current_usage, usage_from_audio_scripts(audio_scripts.scripts))
            return audio_scripts, updated_usage

        stop_task = None
        if needs_audio:
            stop_task = asyncio.create_task(run_stop_processor_task())
        elif not itinerary_dict:
            logger.error("Missing itinerary in state — skipping stop processor.")

        logger.info("Running Logistics...")
        async for event in logistics_agent.run_async(ctx):
            yield event

        if stop_task:
            audio_scripts, updated_usage = await stop_task
            # Emit the result as state_delta so it's persisted via the runner, not via direct mutation
            yield Event(
                author=self.name,
                actions=EventActions(
                    state_delta={
                        "audio_scripts": audio_scripts.model_dump(),
                        "tool_usage": updated_usage.model_dump(),
                    }
                ),
                content=types.Content(
                    role="model",
                    parts=[types.Part(
                        text=f"Stop processing complete. {len(audio_scripts.scripts)} scripts produced."
                    )],
                ),
            )

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
