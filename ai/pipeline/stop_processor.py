import asyncio
import logging
from typing import Union

from google.adk.agents.invocation_context import InvocationContext

from wandr.agents.narrator import run_narrator
from wandr.agents.stop_research import run_stop_research
from wandr.models.audio import AudioScript, AudioScriptsModel
from wandr.models.persona import PersonaModel
from wandr.models.trip import ItineraryModel, StopModel

logger = logging.getLogger(__name__)


def _coerce_persona(persona: Union[PersonaModel, dict]) -> PersonaModel:
    if isinstance(persona, PersonaModel):
        return persona
    return PersonaModel.model_validate(persona)


def _coerce_itinerary(itinerary: Union[ItineraryModel, dict]) -> ItineraryModel:
    if isinstance(itinerary, ItineraryModel):
        return itinerary
    return ItineraryModel.model_validate(itinerary)


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
    itinerary: Union[ItineraryModel, dict],
    persona: Union[PersonaModel, dict],
    ctx: InvocationContext | None = None,
) -> AudioScriptsModel:
    """Fan out (Stop Research → Narrator) for every stop in parallel."""
    itinerary_model = _coerce_itinerary(itinerary)
    persona_model = _coerce_persona(persona)

    logger.info(
        "Stop processor starting: %d stop(s), persona=%s pace=%s",
        sum(len(day.stops) for day in itinerary_model.days),
        persona_model.type,
        persona_model.pace,
    )

    stops = [stop for day in itinerary_model.days for stop in day.stops]
    tasks = [process_single_stop(stop, persona_model) for stop in stops]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scripts: list[AudioScript] = []
    for stop, result in zip(stops, results):
        if isinstance(result, Exception):
            logger.error("Stop processing failed for %s (%s): %s", stop.name, stop.place_id, result)
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
