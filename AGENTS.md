# AGENTS.md

Coding standards for Wandr. Read this before writing any code.

---

## Project overview

Wandr is a multi-agent travel guide built with Google ADK. The pipeline is:
**Profiler → Itinerary → Stop Processor (parallel fan-out) → Logistics → Orchestrator**

The FastAPI server runs in the same process as the ADK pipeline, streaming progress to the frontend over SSE.

---

## Separation of concerns

This is the most important rule. Each layer has one job — don't blur the lines.

| Layer       | Its job                                                                 | What it must NOT do                                  |
| ----------- | ----------------------------------------------------------------------- | ---------------------------------------------------- |
| `agents/`   | Define the agent, its system prompt, `output_key`, and registered tools | Call Google APIs directly, contain business logic    |
| `tools/`    | Wrap external APIs (Places, Maps, TTS) as plain async functions         | Know anything about agents or session state          |
| `pipeline/` | Coordinate the fan-out across stops                                     | Contain LLM prompts or API calls                     |
| `api/`      | Serve SSE and REST endpoints                                            | Import from `agents/` directly or run pipeline logic |
| `models/`   | Define Pydantic schemas                                                 | Contain methods with side effects                    |
| `config/`   | Load env vars and constants                                             | Import from any other wandr module                   |

If you find yourself calling a Google API inside an agent file, or importing `agents/` into `tools/`, stop and restructure.

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

- Models live in `ai/models/` — one file per domain (`persona.py`, `trip.py`, `audio.py`, etc.)
- Never define a model inside an agent file
- Use `Literal` for any field with a fixed set of values
- All model fields must have types — no bare `Any`

---

## Agents

Each agent file exports exactly one thing: the configured ADK agent instance.

```python
# ai/agents/itinerary.py

from google.adk.agents import LlmAgent
from wandr.models.trip import ItineraryModel
from wandr.tools.maps import places_search, get_place_details

ITINERARY_PROMPT = """
You are a travel itinerary planner...
"""

itinerary_agent = LlmAgent(
    name="itinerary",
    model=settings.MODEL_NAME,
    instruction=ITINERARY_PROMPT,
    tools=[places_search, get_place_details],
    output_key="itinerary",
    output_schema=ItineraryModel,
)
```

- System prompts go in a `SCREAMING_SNAKE_CASE` constant at the top of the file, not inline
- Never hardcode model names — use `settings.MODEL_NAME`
- Agents must not import from other agent files (only from `models/` and `tools/`)
- The `tools` list on each agent should only include tools that agent actually needs — see DESIGN.md for the tool-to-agent mapping

---

## Tools

Tool functions are plain async functions registered directly on ADK agents. ADK wraps them internally — no protocol layer needed.

```python
# ai/tools/maps.py

async def places_search(destination: str, persona_type: str, limit: int = 10) -> list[PlaceResult]:
    """Search for places matching a persona type at a destination."""
    ...

async def get_place_details(place_id: str) -> PlaceDetails:
    """Fetch opening hours, rating, and editorial summary for a place."""
    ...
```

- One file per external service (`maps.py`, `tts.py`)
- Every function has a docstring — one line describing what it does
- Return typed Pydantic models, never raw API response dicts
- Raise specific exceptions (`PlaceNotFoundError`, `TTSError`) — not bare `Exception`
- Tools must be pure functions with no side effects beyond their API call

---

## Async and the parallel fan-out

The Stop Processor is the only place that does concurrent execution. Keep parallelism contained there.

```python
# ai/pipeline/stop_processor.py

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

- Use `return_exceptions=True` on `asyncio.gather` — a single bad stop must not crash the whole pipeline
- Log which stop failed and fall back gracefully (text script, `audio_url=""`)
- Do not use `asyncio.gather` anywhere outside `stop_processor.py`

---

## SSE streaming

The backend streams pipeline progress to the frontend via Server-Sent Events. A few rules to keep it working correctly:

- Every SSE endpoint **must** include `X-Accel-Buffering: no` in the response headers — without it, Cloud Run's nginx layer buffers events and they arrive in a batch at the end, defeating the whole point
- Every event **must** conform to `PipelineEvent` from `models/events.py` — no ad-hoc dicts in the stream
- Emit a `stop_done` event immediately when each stop's Narrator finishes — don't wait for all stops
- Always emit a terminal event (`complete` or `error`) so the frontend knows to close the `EventSource`
- Never swallow exceptions silently in the generator — emit an `error` event so the UI can show a meaningful message

```python
# ✅ correct SSE response
return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",   # required — disables nginx buffering on Cloud Run
    }
)

# ❌ wrong — events will batch-deliver at the end on Cloud Run
return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Config and secrets

**No API keys, tokens, or secrets anywhere in code or committed files.**

```python
# ai/config/settings.py

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

- All modules import from `wandr.config.settings` — never from `os.environ` directly
- `.env` is gitignored — copy `.env.example` to get started
- In production, secrets come from Google Cloud Secret Manager injected as env vars at Cloud Run deploy time

---

## Error handling

- Catch errors at the boundary where you can do something useful (log, fallback, raise a cleaner error)
- Don't catch `Exception` broadly — be specific
- The Narrator agent must always return something: if TTS fails, return the text script with `audio_url=""`
- Log the stop name and error before falling back — silent failures are hard to debug

---

## Frontend

The frontend is React + TypeScript + Tailwind CSS, built with Vite. Same separation-of-concerns principle applies.

**Component rules:**

- One component per file, filename matches the component name (`StopCard.tsx` exports `StopCard`)
- Props must be typed — no implicit `any`, no prop drilling more than two levels deep (lift to context or a hook)
- Data fetching and SSE logic lives in hooks under `src/hooks/` — never directly in a component

```tsx
// ✅ correct — logic in a hook
const { stops, progress } = usePlanStream(planId);

// ❌ wrong — EventSource inside a component body
useEffect(() => {
  const es = new EventSource(...); // belongs in usePlanStream.ts
}, []);
```

**SSE on the frontend:**

- `EventSource` setup and teardown lives exclusively in `src/hooks/usePlanStream.ts`
- Always close the `EventSource` in the `useEffect` cleanup — memory leak otherwise
- Append stops incrementally as `stop_done` events arrive — never wait for `complete` to render

```tsx
// ✅ correct — render stops as they stream in
if (event.type === "stop_done") {
  setStops((prev) => [...prev, event.data]);
}

// ❌ wrong — blocks UI until everything is done
if (event.type === "complete") {
  setStops(event.data.all_stops);
}
```

**Naming conventions:**

| Thing           | Convention              | Example                           |
| --------------- | ----------------------- | --------------------------------- |
| Component files | `PascalCase.tsx`        | `StopCard.tsx`                    |
| Hook files      | `camelCase.ts`          | `usePlanStream.ts`                |
| Utility files   | `camelCase.ts`          | `formatDuration.ts`               |
| CSS             | Tailwind utilities only | `className="text-sm font-medium"` |

---

## Naming conventions (backend)

| Thing                   | Convention             | Example                          |
| ----------------------- | ---------------------- | -------------------------------- |
| Files                   | `snake_case`           | `stop_research.py`               |
| Classes / Models        | `PascalCase`           | `StopResearchResult`             |
| Functions / variables   | `snake_case`           | `process_single_stop`            |
| Agent instances         | `{name}_agent`         | `narrator_agent`                 |
| System prompt constants | `SCREAMING_SNAKE_CASE` | `NARRATOR_PROMPT`                |
| State keys              | `snake_case` strings   | `session.state["audio_scripts"]` |

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

## Python version

**Python 3.12.** Do not use 3.9, 3.10, or 3.11.

- ADK minimum is 3.10; we pin 3.12 for better `asyncio` task handling and Pydantic v2 compatibility
- The Dockerfile base image must be `python:3.12-slim`
- Use `pyenv` to switch locally if needed: `pyenv local 3.12`

---

## What not to do

- Don't add a new dependency without discussing it — keep `pyproject.toml` and `package.json` lean
- Don't call Google APIs inside agent files — that belongs in `tools/`
- Don't put frontend logic in the agent layer or vice versa
- Don't commit `.env`, audio output files, or anything in `outputs/`
- Don't use `print()` for debugging — use `logging.getLogger(__name__)`
- Don't skip types to save time — they're what makes the agent hand-offs trustworthy
- Don't omit `X-Accel-Buffering: no` on SSE endpoints — events will not stream on Cloud Run without it
