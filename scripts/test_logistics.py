"""Manual test for Logistics — build route from a mock itinerary."""

import asyncio
import json

from ai.agents.logistics import run_logistics
from ai.models.trip import ItineraryDay, ItineraryModel, StopModel

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


async def main() -> None:
    print("=== Logistics test ===\n")
    route = await run_logistics(FAKE_ITINERARY)
    print(json.dumps(route.model_dump(), indent=2))
    print(f"\nTotal walking: {route.total_travel_min} min")


if __name__ == "__main__":
    asyncio.run(main())
