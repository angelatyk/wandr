# Wandr

> AI-powered personalized travel guide with audio narration — Kaggle AI Agents Capstone

**Track:** Concierge Agents | **Stack:** Google ADK multi-agent | **Timeline:** 1 week

---

## Evaluation checklist

| Requirement              | How we satisfy it                                                            |
| ------------------------ | ---------------------------------------------------------------------------- |
| Multi-agent system (ADK) | 6 specialized agents — sequential pipeline + parallel fan-out via Google ADK |
| MCP server               | Custom MCP server wrapping Google Places + Cloud TTS                         |
| Security features        | Persona stored locally in browser, no PII sent to any API                    |
| Deployability            | Dockerized, deployed to Cloud Run — live URL for judges                      |
| Agent skills / CLI       | ADK CLI configures persona skill per agent                                   |
| Antigravity              | Persona switch + live audio playback in demo video                           |

---

## Agent architecture

### How state flows

The pipeline has two phases: a **sequential setup phase** (Profiler → Itinerary) that establishes the trip plan, followed by a **parallel fan-out phase** where a Stop Processor spawns a (Stop Research, Narrator) pair concurrently for every stop. Logistics runs last once all audio is ready. All agents share `session.state`; structured outputs use Pydantic schemas.

```
User prompt
    ↓
Profiler ──────────────────────────── writes: session.state["persona"]
    ↓
Itinerary ─────────────────────────── reads: persona
                                       writes: session.state["itinerary"]
    ↓
Stop Processor (parallel fan-out)
    ├── Stop A: StopResearch → Narrator ─┐
    ├── Stop B: StopResearch → Narrator ─┤── asyncio.gather()
    ├── Stop C: StopResearch → Narrator ─┤
    └── Stop N: StopResearch → Narrator ─┘
                                       writes: session.state["audio_scripts"]
    ↓
Logistics ─────────────────────────── reads: itinerary, audio_scripts
                                       writes: session.state["route"]
    ↓
Orchestrator assembles final response (itinerary + audio + map)
```

---

### Orchestrator

**ADK type:** `SequentialAgent`

The ADK root. Bootstraps the sequential pipeline, hands off to the Stop Processor for parallel execution, then merges all state keys into the final response. Handles errors if any sub-agent fails and triggers re-runs on user edits.

- Parses and validates the initial user request
- Passes `InvocationContext` to each sub-agent in order
- Merges `itinerary`, `audio_scripts`, and `route` into the final response
- Supports re-generation when user changes persona or destination

---

### Profiler agent

**ADK type:** `LlmAgent`
**State:** `output_key="persona"` | `output_schema=PersonaModel`

Captures and enriches the user's travel persona. Asks follow-up questions if destination, duration, or preferences are missing. Produces a structured Pydantic object written to `session.state["persona"]`.

- Classifies persona: foodie / artist / historian / adventurer / local-life
- Infers pace, budget level, accessibility needs from conversation
- Persona object stored locally in browser (never sent to backend)
- On repeat visits, reads saved persona from localStorage and skips elicitation

---

### Itinerary agent

**ADK type:** `LlmAgent`
**State:** reads `session.state["persona"]` | `output_key="itinerary"` | `output_schema=ItineraryModel`

Takes the persona and trip parameters, calls `places_search` via MCP to gather candidates, then builds a structured day-by-day stop list. Does not do deep research on each stop — that is delegated to the parallel Stop Research agents.

- Calls `places_search(destination, persona_type)` via MCP for initial candidates
- Balances must-see vs hidden gem ratio per persona type
- Produces a flat ordered stop list per day, ready for fan-out
- Handles multi-day trips with clean day boundaries

---

### Stop Processor (parallel fan-out)

**ADK type:** `asyncio.gather` orchestration in `pipeline/stop_processor.py`

Not an LLM agent — a Python coordinator that receives `session.state["itinerary"]` and spawns a (Stop Research → Narrator) pair for every stop concurrently. This is the primary showcase of multi-agent parallelism.

```python
# pipeline/stop_processor.py (simplified)
async def process_all_stops(itinerary, persona, session):
    tasks = [
        process_single_stop(stop, persona, session)
        for day in itinerary.days
        for stop in day.stops
    ]
    results = await asyncio.gather(*tasks)
    session.state["audio_scripts"] = AudioScriptsModel(scripts=results)

async def process_single_stop(stop, persona, session):
    research = await stop_research_agent.run(stop, persona)
    audio = await narrator_agent.run(stop, research, persona)
    return audio
```

---

### Stop Research agent

**ADK type:** `LlmAgent`
**State:** receives stop + persona as invocation args | returns `StopResearchResult`

Runs in parallel (one per stop). Pulls real enriched data for a single location — hours, context, hidden gems — and packages it for the Narrator.

- Calls `get_place_details(place_id)` via MCP
- Extracts opening hours, ratings, editorial summary
- Surfaces hidden gems and local tips relevant to persona type
- Flags locations that may be closed or seasonal

---

### Narrator agent

**ADK type:** `LlmAgent`
**State:** receives stop + research result + persona as invocation args | returns `AudioScript`

Runs in parallel (one per stop), immediately after Stop Research for the same stop. Writes a 60–90s audio script in a persona-matched tone, then calls Google Cloud TTS via MCP.

- Tone adapts per persona: dramatic / enthusiastic / contemplative / energetic / warm
- Script length tuned for walking pace between stops
- Calls `generate_audio(script, voice_style)` via MCP → returns signed GCS audio URL
- Audio responses cached by script hash to avoid re-billing on re-renders
- Graceful fallback: returns text script if TTS call fails

---

### Logistics agent

**ADK type:** `LlmAgent`
**State:** reads `session.state["itinerary"]`, `session.state["audio_scripts"]` | `output_key="route"`

Runs after all parallel stop processing is complete. Optimizes the route order across stops, calculates travel times, and generates the map data.

- Route optimization via nearest-neighbor across stops per day
- Calculates travel time between stops using Google Maps Directions API
- Respects opening hours to flag scheduling conflicts
- Outputs ordered route with map pin data for the frontend

---

## Pydantic schemas (structured output)

Each agent uses an `output_schema` so outputs are typed and validated before the next agent reads them.

> **Note:** `output_schema` + tools in the same agent only works reliably on Gemini 2.5+. For earlier models, use a lightweight formatting sub-agent to convert the LLM's free text into the schema.

```python
# Profiler output
class PersonaModel(BaseModel):
    type: Literal["foodie", "artist", "historian", "adventurer", "local-life"]
    pace: Literal["relaxed", "moderate", "packed"]
    budget: Literal["budget", "mid", "luxury"]
    notes: str  # any freeform user context

# Itinerary output — stop list ready for fan-out
class StopModel(BaseModel):
    place_id: str
    name: str
    address: str
    day: int
    order: int  # position within the day

class ItineraryDay(BaseModel):
    day: int
    stops: list[StopModel]

class ItineraryModel(BaseModel):
    destination: str
    days: list[ItineraryDay]

# Stop Research output — one per stop, returned by parallel agent
class StopResearchResult(BaseModel):
    place_id: str
    name: str
    address: str
    persona_score: float        # 0–1 fit score
    context_facts: list[str]   # fed to narrator
    opening_hours: str
    is_seasonal: bool

# Narrator output — one per stop, assembled by Stop Processor
class AudioScript(BaseModel):
    place_id: str
    script: str        # narration text
    audio_url: str     # signed GCS URL from TTS
    duration_sec: int

class AudioScriptsModel(BaseModel):
    scripts: list[AudioScript]

# Logistics output
class RouteStop(BaseModel):
    place_id: str
    order: int
    travel_time_from_prev_min: int
    lat: float
    lng: float

class RouteModel(BaseModel):
    stops: list[RouteStop]
    total_travel_min: int
```

---

## MCP server

The MCP server exposes four tools, wrapping Google Places API, Google Maps Directions API, and Google Cloud TTS.

### `places_search(destination, persona_type, limit)`

Wraps Google Places API. Returns top N locations ranked by persona type.

- Foodie → restaurants, markets
- Artist → galleries, murals
- Historian → monuments, museums
- Adventurer → parks, trails
- Local-life → neighbourhoods, cafes

### `get_place_details(place_id)`

Fetches enriched data for a specific place: opening hours, rating, editorial summary. Used by the Stop Research agent to validate and enrich each stop before passing to the Narrator.

### `get_directions(origin_place_id, destination_place_id, mode)`

Wraps Google Maps Directions API. Returns travel time and distance between two stops. Used by the Logistics agent to calculate realistic inter-stop travel times.

### `generate_audio(script, voice_style)`

Wraps Google Cloud TTS. Accepts a narration script and voice style (dramatic / enthusiastic / contemplative / energetic / warm). Returns a signed GCS audio URL. Responses are cached by script hash — the same script is never billed twice.

---

## Tech stack

| Layer       | Choices                                                                                               |
| ----------- | ----------------------------------------------------------------------------------------------------- |
| Agent layer | Google ADK (Python), `SequentialAgent` + `asyncio.gather` fan-out, Gemini 2.5 Flash, Pydantic schemas |
| MCP server  | Python MCP server, Google Places API, Google Maps Directions API, Google Cloud TTS, FastAPI transport |
| Frontend    | React + TypeScript, Tailwind CSS, Web Audio API, Vite                                                 |
| Infra       | Docker, Google Cloud Run, GitHub (public repo), GitHub Actions CI                                     |
| Security    | localStorage persona, no PII to APIs, Cloud Secret Manager, HTTPS + signed URLs                       |

---

## Security features

| Feature               | Detail                                                                                               |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| Local persona storage | User preferences stored in browser localStorage only — never sent to the backend or any external API |
| No PII to APIs        | Only destination strings and place IDs go to Google Places. No names, emails, or identifiers         |
| Secret management     | All API keys stored in Google Cloud Secret Manager. Never in env files or the repo                   |
| HTTPS + signed URLs   | Cloud Run enforces TLS. Generated audio URLs are signed and expire after 1 hour                      |

---

## 7-day sprint

| Day | Focus             | Goal                                                                                                |
| --- | ----------------- | --------------------------------------------------------------------------------------------------- |
| 1   | Setup + skeleton  | Repo, ADK project init, GCP APIs enabled, MCP server scaffold, shared Pydantic schemas defined      |
| 2   | Agent cores       | Profiler + Narrator logic (mock audio). Orchestrator + Research agent hitting real Places API       |
| 3   | Integration       | Wire all agents through `SequentialAgent`. First end-to-end run: "Paris, 2 days, foodie"            |
| 4   | TTS + frontend    | MCP → Google TTS live. Audio player in React. Itinerary route optimization + persona scoring        |
| 5   | Polish + security | localStorage persona caching, error handling, loading states, UI polish. Test 5 personas × 3 cities |
| 6   | Deploy + video    | Docker build, Cloud Run deploy, public URL. Record 5-min demo video                                 |
| 7   | Writeup + submit  | Kaggle writeup (2,500 words max), attach video + GitHub link, submit                                |

---

## Project file structure

```
wandr/
├── README.md
├── .env.example                    # never commit .env
├── pyproject.toml
├── ai/
│   ├── __init__.py
│   ├── main.py                     # entrypoint, orchestrator bootstrap
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # root SequentialAgent, manages pipeline
│   │   ├── profiler.py             # captures user persona + trip params
│   │   ├── itinerary.py            # builds stop list from preferences + Places API
│   │   ├── stop_research.py        # per-stop: hours, context, hidden gems
│   │   ├── narrator.py             # per-stop: generates audio script + TTS
│   │   └── logistics.py            # route optimization, travel times
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── stop_processor.py       # asyncio.gather fan-out across stops
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── maps.py                 # Google Places + Directions API calls
│   │   └── tts.py                  # Google Cloud TTS wrapper + cache
│   │
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py               # FastAPI MCP transport
│   │   └── handlers/
│   │       ├── places.py           # places_search, get_place_details, get_directions
│   │       └── audio.py            # generate_audio + script hash cache
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── persona.py              # PersonaModel
│   │   ├── trip.py                 # StopModel, ItineraryDay, ItineraryModel
│   │   ├── research.py             # StopResearchResult
│   │   ├── audio.py                # AudioScript, AudioScriptsModel
│   │   └── route.py                # RouteStop, RouteModel
│   │
│   └── config/
│       ├── __init__.py
│       └── settings.py             # env vars, model names, constants
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PersonaSetup.tsx    # persona elicitation UI
│   │   │   ├── Itinerary.tsx       # day-by-day stop list
│   │   │   ├── AudioPlayer.tsx     # per-stop audio playback
│   │   │   └── RouteMap.tsx        # Google Maps JS embed
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── outputs/                        # gitignored — generated audio + maps
│   └── .gitkeep
│
├── tests/
│   ├── test_agents/
│   ├── test_pipeline/
│   ├── test_tools/
│   └── fixtures/
│
├── docs/
│   ├── architecture.png
│   └── demo.md
│
└── Dockerfile
```

**Key design decisions:**

- `agents/` contains only ADK agent definitions and system prompts — no business logic
- `tools/` holds the raw API wrappers called by agents; testable in isolation without ADK
- `pipeline/stop_processor.py` is where parallel fan-out lives — isolated so the concurrency pattern is explicit and easy to explain in the writeup
- `mcp_server/` is a self-contained FastAPI app; can be deployed independently of the agent layer
- `models/` uses typed Pydantic dataclasses for all inter-agent hand-offs — no raw dicts

---

Same city, two personas, back to back — 60 seconds apart in the video:

**Foodie → Tokyo**
Tsukiji outer market at 6am → best ramen in Shinjuku → Depachika basement food halls → hidden yakitori alley. Audio: enthusiastic, fast-paced, sensory language.

**Historian → Tokyo**
Senso-ji at dawn → Edo-Tokyo Museum → Imperial Palace East Gardens → Yanaka old town. Audio: contemplative, rich context, slower cadence.

> Make sure the audio actually plays out loud in the video. Judges need to hear the tone difference, not just read about it.
