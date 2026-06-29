import asyncio
import logging

from ai.models.trip import ItineraryModel, StopModel
from ai.models.persona import PersonaModel
from ai.models.audio import AudioScriptsModel, AudioScript

logger = logging.getLogger(__name__)


async def process_all_stops(
    itinerary: ItineraryModel,
    persona: PersonaModel,
) -> AudioScriptsModel:
    """Run stop research and narration concurrently across all stops in the itinerary."""
    print("arrived at stop processor")
    logger.info("Processing all stops concurrently")

    async def process_single_stop(stop: StopModel) -> AudioScript:
        logger.info(f"Processing stop: {stop.name} ({stop.place_id})")

        # Return mock audio script — real implementation will call stop_research
        # and narrator agents via a dedicated StopAgent wrapper in agents/
        return AudioScript(
            place_id=stop.place_id,
            script=f"Mock narration for {stop.name}",
            audio_url="http://example.com/mock-audio.mp3",
            duration_sec=90,
        )

    tasks = [
        process_single_stop(stop)
        for day in itinerary.days
        for stop in day.stops
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    scripts: list[AudioScript] = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            # Log but don't crash the whole pipeline — a single bad stop yields a fallback
            logger.error(f"Stop {i} processing failed: {res}")
            scripts.append(AudioScript(
                place_id=f"failed_{i}",
                script="Fallback narration",
                audio_url="",
                duration_sec=0,
            ))
        else:
            scripts.append(res)

    return AudioScriptsModel(scripts=scripts)
