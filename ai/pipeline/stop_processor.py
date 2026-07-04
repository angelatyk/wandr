import asyncio
import logging

from ai.agents.narrator import run_narrator
from ai.agents.stop_research import run_stop_research
from ai.models.audio import AudioScript, AudioScriptsModel
from ai.models.persona import PersonaModel
from ai.models.trip import ItineraryModel, StopModel

logger = logging.getLogger(__name__)


async def process_single_stop(stop: StopModel, persona: PersonaModel) -> AudioScript:
    """Research one stop for this persona, then produce narration."""
    logger.info(
        "Processing stop %s for persona type=%s notes=%r",
        stop.name,
        persona.type,
        persona.notes,
    )

    research = await run_stop_research(stop, persona)

    logger.info(
        "Research done for %s: persona_score=%.2f facts=%d",
        research.name,
        research.persona_score,
        len(research.context_facts),
    )

    return await run_narrator(stop, persona, research)


async def process_all_stops(
    itinerary: ItineraryModel,
    persona: PersonaModel,
) -> AudioScriptsModel:
    """Fan out (Stop Research → Narrator) for every stop in parallel."""
    stops = [stop for day in itinerary.days for stop in day.stops]

    logger.info(
        "Stop processor starting: %d stop(s), persona=%s pace=%s",
        len(stops),
        persona.type,
        persona.pace,
    )

    tasks = [process_single_stop(stop, persona) for stop in stops]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scripts: list[AudioScript] = []
    for stop, result in zip(stops, results):
        if isinstance(result, Exception):
            logger.error(
                "Stop processing failed for %s (%s): %s",
                stop.name,
                stop.place_id,
                result,
            )
            scripts.append(
                AudioScript(
                    place_id=stop.place_id,
                    script=f"We could not generate narration for {stop.name}.",
                    audio_url="",
                    duration_sec=0,
                )
            )
        else:
            scripts.append(result)

    return AudioScriptsModel(scripts=scripts)
