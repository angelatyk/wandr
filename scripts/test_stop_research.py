"""Manual test for Stop Research — run from project root with Python 3.10+."""

import asyncio
import json
import sys

from ai.agents.stop_research import run_stop_research
from ai.config.settings import settings
from ai.models.persona import PersonaModel
from ai.models.trip import StopModel

FAKE_STOP = StopModel(
    place_id="sensoji_id",
    name="Senso-ji",
    address="Asakusa, Tokyo",
    day=1,
    order=1,
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
    print("=== Stop Research test ===\n")
    print(f"Model: {settings.model_name}")
    print(f"Gemini key set: {bool(settings.gemini_api_key)}")
    print()

    if not settings.gemini_api_key:
        print("ERROR: Set GEMINI_API_KEY in .env before running this test.")
        sys.exit(1)

    result = await run_stop_research(FAKE_STOP, FAKE_PERSONA)

    print("=== StopResearchResult ===\n")
    print(json.dumps(result.model_dump(), indent=2))
    print(f"\npersona_score: {result.persona_score}")


if __name__ == "__main__":
    asyncio.run(main())
