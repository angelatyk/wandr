"""Test Stop Processor — parallel research + narrator for a mock itinerary."""

import asyncio
import json

from ai.models.persona import PersonaModel
from ai.models.trip import ItineraryDay, ItineraryModel, StopModel
from ai.pipeline.stop_processor import process_all_stops

FAKE_ITINERARY = ItineraryModel(
    destination="Tokyo",
    days=[
        ItineraryDay(
            day=1,
            stops=[
                StopModel(
                    place_id="sensoji_id",
                    name="Senso-ji",
                    address="Asakusa, Tokyo",
                    day=1,
                    order=1,
                ),
                StopModel(
                    place_id="edo_museum_id",
                    name="Edo-Tokyo Museum",
                    address="Ryogoku, Tokyo",
                    day=1,
                    order=2,
                ),
            ],
        )
    ],
)

FAKE_PERSONA = PersonaModel(
    destination="Tokyo",
    duration="2 days",
    type="historian",
    pace="moderate",
    budget="mid",
    notes="Interested in Edo history and temple architecture",
)


async def main() -> None:
    print("=== Stop Processor test ===\n")
    print("Persona:", json.dumps(FAKE_PERSONA.model_dump(), indent=2))
    print("Stops:", len(FAKE_ITINERARY.days[0].stops), "\n")

    result = await process_all_stops(FAKE_ITINERARY, FAKE_PERSONA)

    print(f"=== {len(result.scripts)} AudioScript(s) ===\n")
    for script in result.scripts:
        print(f"--- {script.place_id} ---")
        print(f"duration_sec: {script.duration_sec}")
        print(f"audio_url: {script.audio_url or '(text-only)'}")
        print(f"script preview: {script.script[:200]}...")
        print()


if __name__ == "__main__":
    asyncio.run(main())
