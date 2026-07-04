"""Focused smoke test for place search -> itinerary option -> final itinerary flow."""

import asyncio
import json

from ai.agents.itinerary import _build_final_itinerary, _build_options_from_candidates
from ai.tools.maps import get_place_details, places_search


async def main() -> None:
    destination = "Tokyo"
    persona_type = "historian"
    day_count = 2

    print("=== Itinerary data flow smoke test ===\n")
    candidates = await places_search(destination, persona_type, limit=8)
    assert candidates, "places_search returned no candidates"
    assert all(candidate.place_id for candidate in candidates), "candidate missing place_id"
    assert all(candidate.address for candidate in candidates), "candidate missing address"

    options = _build_options_from_candidates(
        destination=destination,
        persona_type=persona_type,
        day_count=day_count,
        candidates=candidates,
        confirmed=[],
    )
    assert options.days, "no itinerary option days were generated"

    confirmed: list[dict] = []
    for day in options.days:
        if not day.options:
            continue
        selected = day.options[0]
        confirmed.append(
            {
                "place_id": selected.place_id,
                "name": selected.name,
                "address": selected.address,
                "photo_url": selected.photo_url,
                "suggested_duration": selected.suggested_duration,
                "description": selected.description,
                "must_see": selected.must_see,
                "hours_of_operation": selected.hours_of_operation,
                "persona_note": selected.persona_note,
                "day": day.day,
                "order": 1,
            }
        )

    itinerary = _build_final_itinerary(destination, confirmed)
    itinerary_ids = [stop.place_id for day in itinerary.days for stop in day.stops]
    confirmed_ids = [place["place_id"] for place in confirmed]
    assert itinerary_ids == confirmed_ids, "final itinerary did not preserve confirmed place_ids"

    for day in itinerary.days:
        for stop in day.stops:
            details = await get_place_details(stop.place_id)
            assert details.place_id == stop.place_id

    photo_count = sum(1 for candidate in candidates if candidate.photo_url)
    print(f"Candidates fetched: {len(candidates)}")
    print(f"Candidates with photo_url: {photo_count}")
    print(f"Confirmed stops: {len(confirmed)}")
    print()
    print(json.dumps(itinerary.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
