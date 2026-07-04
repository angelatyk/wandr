"""Manual test for Narrator — research one stop, then generate narration."""

import asyncio
import json
import sys

from ai.agents.narrator import run_narrator
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
    print("=== Narrator test (research → narration) ===\n")
    print(f"Persona: {FAKE_PERSONA.type} / voice: dramatic")
    print(f"Stop: {FAKE_STOP.name}")
    print(f"Gemini key set: {bool(settings.gemini_api_key)}\n")

    if not settings.gemini_api_key:
        print("ERROR: Set GEMINI_API_KEY in .env before running this test.")
        sys.exit(1)

    research = await run_stop_research(FAKE_STOP, FAKE_PERSONA)
    print(f"Research persona_score: {research.persona_score}")
    print(f"Facts: {len(research.context_facts)}\n")

    audio = await run_narrator(FAKE_STOP, FAKE_PERSONA, research)

    print("=== AudioScript ===\n")
    print(json.dumps(audio.model_dump(), indent=2))
    print(f"\nduration_sec: {audio.duration_sec}")
    print(f"audio_url: {audio.audio_url or '(text-only — TTS stub)'}")
    print(f"\n--- Script ---\n{audio.script}")


if __name__ == "__main__":
    asyncio.run(main())
