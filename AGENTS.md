# AGENTS.md

Coding standards for Wandr. Read this before writing any code.

---

## Project overview

Wandr is a multi-agent travel guide built with Google ADK. The pipeline is:
**Profiler → Itinerary → Stop Processor (parallel fan-out) → Logistics → Orchestrator**

The MCP server is a separate FastAPI app that wraps Google Places, Maps Directions, and Cloud TTS.

---

## Separation of concerns

This is the most important rule. Each layer has one job — don't blur the lines.

| Layer | Its job | What it must NOT do |
|---|---|---|
| `agents/` | Define the agent, its system prompt, and `output_key` | Call Google APIs directly, contain business logic |
| `tools/` | Wrap external APIs (Places, Maps, TTS) | Know anything about agents or session state |
| `pipeline/` | Coordinate the fan-out across stops | Contain LLM prompts or API calls |
| `mcp_server/` | Expose MCP tools over FastAPI transport | Import from `agents/` |
| `models/` | Define Pydantic schemas | Contain methods with side effects |
| `config/` | Load env vars and constants | Import from any other wandr module |

If you find yourself importing `agents/` into `tools/` or calling an API inside an agent file, stop and restructure.

---

## Models

**All inter-agent data must be a typed Pydantic model. No raw dicts between agents.**

```python
# ✅ correct
async def process_single_stop(stop: StopModel, persona: PersonaModel) -> AudioScript:
    ...

# ❌ wrong
async def process_single_stop(stop: dict, persona: dict) -> dict:
    ...
```

- Models live in `wandr/models/` — one file per domain (`persona.py`, `trip.py`, `audio.py`, etc.)
- Never define a model inside an agent file
- Use `Literal` for any field with a fixed set of values
- All model fields must have types — no bare `Any`

---

## Agents

Each agent file exports exactly one thing: the configured ADK agent instance.

```python
# wandr/agents/profiler.py

from google.adk.agents import LlmAgent
from wandr.models.persona import PersonaModel

profiler_agent = LlmAgent(
    name="profiler",
    model="gemini-2.5-flash",
    instruction=PROFILER_PROMPT,
    output_key="persona",
    output_schema=PersonaModel,
)
```

- System prompts go in a `SCREAMING_SNAKE_CASE` constant at the top of the file, not inline
- Never hardcode model names — use `settings.MODEL_NAME`
- Agents must not import from other agent files (only from `models/` and `tools/`)

---

## Tools

Tool functions are plain async functions that call one external service and return a typed result.

```python
# wandr/tools/maps.py

async def get_place_details(place_id: str) -> PlaceDetails:
    """Fetch opening hours, rating, and editorial summary for a place."""
    ...
```

- One file per external service (`maps.py`, `tts.py`)
- Every function has a docstring — one line describing what it does
- Return typed models, never raw API response dicts
- Raise specific exceptions (`PlaceNotFoundError`, `TTSError`) — not bare `Exception`

---

## Async and the parallel fan-out

The Stop Processor is the only place that does concurrent execution. Keep parallelism contained there.

```python
# wandr/pipeline/stop_processor.py

async def process_all_stops(
    itinerary: ItineraryModel,
    persona: PersonaModel,
) -> AudioScriptsModel:
    tasks = [
        process_single_stop(stop, persona)
        for day in itinerary.days
        for stop in day.stops
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # handle any failed stops before returning
    ...
```

- Use `return_exceptions=True` on `asyncio.gather` — a single bad stop should not crash the whole pipeline
- Log which stop failed and fall back gracefully (text script, no audio)
- Do not use `asyncio.gather` anywhere outside `stop_processor.py`

---

## Config and secrets

**No API keys, tokens, or secrets anywhere in code or committed files.**

```python
# wandr/config/settings.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    google_places_api_key: str
    google_maps_api_key: str
    google_tts_api_key: str
    gcs_bucket_name: str
    model_name: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"

settings = Settings()
```

- All other modules import from `wandr.config.settings` — never from `os.environ` directly
- `.env` is gitignored — copy `.env.example` to get started
- In production, secrets come from Google Cloud Secret Manager, not env files

---

## Error handling

- Catch errors at the boundary where you can do something useful (log, fallback, raise a cleaner error)
- Don't catch `Exception` broadly — be specific
- The Narrator agent must always return something: if TTS fails, return the text script with `audio_url=""`
- Log the stop name and error before falling back — silent failures are hard to debug

---

## Naming conventions

| Thing | Convention | Example |
|---|---|---|
| Files | `snake_case` | `stop_research.py` |
| Classes / Models | `PascalCase` | `StopResearchResult` |
| Functions / variables | `snake_case` | `process_single_stop` |
| Agent instances | `{name}_agent` | `narrator_agent` |
| System prompt constants | `SCREAMING_SNAKE_CASE` | `NARRATOR_PROMPT` |
| State keys | `snake_case` strings | `session.state["audio_scripts"]` |

---

## Comments

Write comments that explain **why**, not **what**. The code already shows what.

```python
# ✅ useful
# persona_score threshold of 0.6 chosen after testing — below this, stops felt off-brand
PERSONA_SCORE_THRESHOLD = 0.6

# ❌ noise
# set the threshold to 0.6
PERSONA_SCORE_THRESHOLD = 0.6
```

ADK-specific comments: if a behaviour is required by ADK (e.g. `output_schema` limitations on older models), leave a short note so neither of us wastes time re-investigating it.

---

## What not to do

- Don't add a new dependency without discussing it — keep `pyproject.toml` lean
- Don't put frontend logic in the agent layer or vice versa
- Don't commit `.env`, audio output files, or anything in `outputs/`
- Don't use `print()` for debugging — use `logging.getLogger(__name__)`
- Don't skip types to save time — they're what makes the agent hand-offs trustworthy
