import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import Client, types
from google.genai.errors import ClientError
from pydantic import ValidationError

from wandr.config.settings import settings
from wandr.models.audio import AudioScript
from wandr.models.persona import PersonaModel
from wandr.models.research import StopResearchResult
from wandr.models.trip import StopModel
from wandr.tools.exceptions import TTSError
from wandr.tools.tts import generate_audio

logger = logging.getLogger(__name__)


def _gemini_client() -> Client:
    return Client(api_key=settings.gemini_api_key)


def persona_voice_style(persona: PersonaModel) -> str:
    return {
        "historian": "dramatic",
        "foodie": "enthusiastic",
        "artist": "contemplative",
        "adventurer": "energetic",
        "local-life": "warm",
    }[persona.type]


def _estimate_duration_sec(script: str) -> int:
    word_count = len(script.split())
    return max(30, min(90, round(word_count / 2.5)))


NARRATOR_PROMPT = """\
You are the Narrator agent for Wandr, a personalized audio travel guide.

## Your job

Write a **60–90 second walking narration** for **one itinerary stop**. You run immediately after \
Stop Research for the same stop — use its research output as your source of truth.

You run once per stop, often in parallel with other stops. Focus only on the stop described \
in the user message.

## Workflow

1. Read the stop, traveler persona, and Stop Research result from the user message.
2. Write a narration script matched to the persona tone and pace.
3. Return a single `AudioScript` object (structured output) with `audio_url` set to `""`.

Audio is generated separately after you return the script. Always return the full script even \
if audio would fail later.

## Voice style by persona

| persona type | voice_style |
|--------------|-------------|
| historian | dramatic |
| foodie | enthusiastic |
| artist | contemplative |
| adventurer | energetic |
| local-life | warm |

## Script guidelines

- **Length:** 60–90 seconds when spoken (~150–225 words). Tune to `pace`: \
relaxed → closer to 90s, packed → closer to 60s.
- **Tone:** Match the persona `type` and `voice_style`. Sound like a knowledgeable local guide, \
not a brochure.
- **Structure:** Open with the place name and a hook, weave in 3–5 facts from `context_facts`, \
mention practical details (hours, seasonal notes) only when useful, end with a natural closing \
as the traveler arrives.
- **Grounding:** Use only facts from the Stop Research result. Do not invent history, quotes, \
or reviews. If `is_seasonal` is true, briefly warn the traveler.
- **Budget & notes:** Weave in `budget` and persona `notes` only when naturally relevant.

## Output fields

Return exactly these fields:

- **place_id** — copy from the stop input.
- **script** — the full narration text you wrote (plain text, no markdown). **Required.**
- **audio_url** — always return `""` (audio is attached after your response).
- **duration_sec** — estimated spoken duration in seconds (typically 60–90, ~2.5 words per second).

## Rules

- One stop per invocation. Ignore other stops.
- Do not re-research the place — Stop Research already did that.
- Do not recommend other nearby places or change the itinerary.
- Do not output bullet lists or metadata — only the script goes in the `script` field.
- Write in English.
"""


def build_narrator_context(
    stop: StopModel,
    persona: PersonaModel,
    research: StopResearchResult,
) -> str:
    """Build the per-invocation user message injected when the agent runs for one stop."""
    facts = "\n".join(f"- {fact}" for fact in research.context_facts) or "- (none)"
    voice_style = persona_voice_style(persona)

    return f"""\
Write a narration for this stop and return an AudioScript.

## Stop
- place_id: {stop.place_id}
- name: {stop.name}
- address: {stop.address}
- day: {stop.day}
- order: {stop.order}

## Traveler persona
- type: {persona.type}
- pace: {persona.pace}
- budget: {persona.budget}
- notes: {persona.notes or "(none)"}
- voice_style: {voice_style}

## Stop Research result
- persona_score: {research.persona_score}
- opening_hours: {research.opening_hours}
- is_seasonal: {research.is_seasonal}
- context_facts:
{facts}

Produce the structured AudioScript JSON with audio_url="".
"""


async def run_narrator(
    stop: StopModel,
    persona: PersonaModel,
    research: StopResearchResult,
) -> AudioScript:
    """Ask Gemini for a narration script, then attach TTS audio when available."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    voice_style = persona_voice_style(persona)
    user_message = build_narrator_context(stop, persona, research)

    client = _gemini_client()
    try:
        response = await client.aio.models.generate_content(
            model=settings.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=user_message)],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=NARRATOR_PROMPT,
                response_mime_type="application/json",
                response_schema=AudioScript,
            ),
        )
    except ClientError as exc:
        if "API_KEY_SERVICE_BLOCKED" in str(exc):
            raise RuntimeError(
                "Gemini API key is blocked for generativelanguage.googleapis.com. "
                "Create a new key at https://aistudio.google.com/apikey and set "
                "GEMINI_API_KEY in .env — do not reuse your Places/Maps Cloud key."
            ) from exc
        raise

    raw = (response.text or "").strip()
    logger.debug("Narrator raw output: %s", raw)

    try:
        audio = AudioScript.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        logger.error("Narrator JSON validation failed: %s", exc)
        raise RuntimeError(f"Narrator returned invalid JSON: {raw}") from exc

    audio = audio.model_copy(update={"place_id": stop.place_id, "audio_url": ""})
    if not audio.duration_sec:
        audio = audio.model_copy(update={"duration_sec": _estimate_duration_sec(audio.script)})

    try:
        audio_url = await generate_audio(audio.script, voice_style)
        audio = audio.model_copy(update={"audio_url": audio_url})
    except TTSError as exc:
        logger.warning("TTS failed for %s — returning text-only script: %s", stop.name, exc)

    logger.info(
        "Narration completed for %s (%ds, audio=%s)",
        stop.name,
        audio.duration_sec,
        "yes" if audio.audio_url else "text-only",
    )
    return audio


class NarratorAgent(BaseAgent):
    """ADK wrapper — pipeline uses run_narrator() directly."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        logger.warning("NarratorAgent ADK wrapper is deprecated — use run_narrator() from stop processor")
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text="Narrator should be invoked via run_narrator() in stop processor.")],
            ),
        )


narrator_agent = NarratorAgent(name="narrator")
