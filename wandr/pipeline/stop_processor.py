import asyncio
import logging
from google.adk.agents.invocation_context import InvocationContext
from wandr.models.trip import ItineraryModel, StopModel
from wandr.models.persona import PersonaModel
from wandr.models.audio import AudioScriptsModel, AudioScript

logger = logging.getLogger(__name__)

async def process_all_stops(
    itinerary: ItineraryModel,
    persona: PersonaModel,
    ctx: InvocationContext
) -> AudioScriptsModel:
    from wandr.agents.stop_research import stop_research_agent
    from wandr.agents.narrator import narrator_agent

    print("arrived at stop processor")
    logger.info("Processing all stops concurrently")

    async def process_single_stop(stop: StopModel) -> AudioScript:
        # Save stop details in temp context state so the child agents can trace what stop they are working on
        ctx.session.state[f"temp:current_stop_name"] = stop.name
        ctx.session.state[f"temp:current_stop_id"] = stop.place_id
        
        # Run stop research
        async for _ in stop_research_agent.run_async(ctx):
            pass
        
        # Run narrator agent
        async for _ in narrator_agent.run_async(ctx):
            pass
            
        # Return mock audio script
        return AudioScript(
            place_id=stop.place_id,
            script=f"Mock narration for {stop.name}",
            audio_url="http://example.com/mock-audio.mp3",
            duration_sec=90
        )

    tasks = []
    for day in itinerary.days:
        for stop in day.stops:
            tasks.append(process_single_stop(stop))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    scripts = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(f"Stop processing failed: {res}")
            # Fallback text script with no audio
            scripts.append(AudioScript(
                place_id=f"failed_{i}",
                script="Fallback narration",
                audio_url="",
                duration_sec=0
            ))
        else:
            scripts.append(res)
            
    return AudioScriptsModel(scripts=scripts)
