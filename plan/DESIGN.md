# Wandr

> AI-powered personalized travel guide with audio narration — Kaggle AI Agents Capstone

**Track:** Concierge Agents | **Stack:** Google ADK multi-agent | **Timeline:** 1 week

---

## Evaluation checklist

| Requirement              | How we satisfy it                                                               |
| ------------------------ | ------------------------------------------------------------------------------- |
| Multi-agent system (ADK) | 6 specialized agents — sequential pipeline + parallel fan-out via Google ADK    |
| Security features        | Persona stored locally in browser, no PII sent to any API, Cloud Secret Manager |
| Deployability            | Dockerized, deployed to Cloud Run — live URL for judges                         |

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
**Tools:** none
**State:** `output_key="persona"` | `output_schema=PersonaModel`

Captures and enriches the user's travel persona. Asks follow-up questions if destination, duration, or preferences are missing. Produces a structured Pydantic object written to `session.state["persona"]`.

- Classifies persona: foodie / artist / historian / adventurer / local-life
- Infers pace, budget level, accessibility needs from conversation
- Persona object stored locally in browser (never sent to backend)
- On repeat visits, reads saved persona from localStorage and skips elicitation

---

### Itinerary agent

**ADK type:** `LlmAgent`
**Tools:** `places_search`, `get_place_details`
**State:** reads `session.state["persona"]` | `output_key="itinerary"` | `output_schema=ItineraryModel`

Takes the persona and trip parameters, calls Google Places via its registered tools to gather candidates, then builds a structured day-by-day stop list. Does not do deep research on each stop — that is delegated to the parallel Stop Research agents.

- Calls `places_search(destination, persona_type)` for initial candidates
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
    results = await asyncio.gather(*tasks, return_exceptions=True)
    session.state["audio_scripts"] = AudioScriptsModel(scripts=results)

async def process_single_stop(stop, persona, session):
    research = await stop_research_agent.run(stop, persona)
    audio = await narrator_agent.run(stop, research, persona)
    return audio
```

---

### Stop Research agent

**ADK type:** `LlmAgent`
**Tools:** `get_place_details`
**State:** receives stop + persona as invocation args | returns `StopResearchResult`

Runs in parallel (one per stop). Pulls real enriched data for a single location — hours, context, hidden gems — and packages it for the Narrator.

- Calls `get_place_details(place_id)` for opening hours, ratings, editorial summary
- Surfaces hidden gems and local tips relevant to persona type
- Flags locations that may be closed or seasonal

---

### Narrator agent

**ADK type:** `LlmAgent`
**Tools:** `generate_audio`
**State:** receives stop + research result + persona as invocation args | returns `AudioScript`

Runs in parallel (one per stop), immediately after Stop Research for the same stop. Writes a 60–90s audio script in a persona-matched tone, then calls Google Cloud TTS.

- Tone adapts per persona: dramatic / enthusiastic / contemplative / energetic / warm
- Script length tuned for walking pace between stops
- Calls `generate_audio(script, voice_style)` → returns signed GCS audio URL
- Audio responses cached by script hash to avoid re-billing on re-renders
- Graceful fallback: returns text script with `audio_url=""` if TTS call fails

---

### Logistics agent

**ADK type:** `LlmAgent`
**Tools:** `get_directions`
**State:** reads `session.state["itinerary"]`, `session.state["audio_scripts"]` | `output_key="route"`

Runs after all parallel stop processing is complete. Optimizes the route order across stops, calculates travel times, and generates the map data.

- Route optimization via nearest-neighbor across stops per day
- Calculates travel time between stops using Google Maps Directions API
- Respects opening hours to flag scheduling conflicts
- Outputs ordered route with map pin data for the frontend

---

## Tools

Plain async Python functions registered directly on each agent. ADK wraps them internally — no protocol overhead, fully testable in isolation.

| Tool                                                   | Used by                  | Wraps                      |
| ------------------------------------------------------ | ------------------------ | -------------------------- |
| `places_search(destination, persona_type, limit)`      | Itinerary                | Google Places API          |
| `get_place_details(place_id)`                          | Itinerary, Stop Research | Google Places API          |
| `get_directions(origin_place_id, dest_place_id, mode)` | Logistics                | Google Maps Directions API |
| `generate_audio(script, voice_style)`                  | Narrator                 | Google Cloud TTS + GCS     |

```python
# Example — how tools are registered on an agent
from wandr.tools.maps import places_search, get_place_details

itinerary_agent = LlmAgent(
    name="itinerary",
    model=settings.MODEL_NAME,
    instruction=ITINERARY_PROMPT,
    tools=[places_search, get_place_details],
    output_key="itinerary",
    output_schema=ItineraryModel,
)
```

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
    audio_url: str     # signed GCS URL; empty string on TTS failure
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

## Frontend → backend communication (SSE)

The frontend connects over **Server-Sent Events** rather than a blocking REST call. The pipeline takes 20–40 seconds; SSE lets the UI update as each agent completes rather than showing a spinner until everything is done.

### Flow

```
Browser                          FastAPI                         ADK Pipeline
   |                                |                                |
   |  POST /plan {destination...}   |                                |
   |------------------------------> |  kick off pipeline async       |
   |  <-- { plan_id }               |                                |
   |                                |                                |
   |  GET /plan/{id}/stream (SSE)   |                                |
   |------------------------------> |                                |
   |  <-- profiler_done  ────────── | <── profiler writes state      |
   |  <-- itinerary_done ────────── | <── itinerary writes state     |
   |  <-- stop_done (1/6) ───────── | <── stop A fan-out completes   |
   |  <-- stop_done (2/6) ───────── | <── stop B fan-out completes   |
   |  <-- stop_done (3/6) ───────── | <── stop C fan-out completes   |
   |  <-- logistics_done ────────── | <── route optimized            |
   |  <-- complete ─────────────── | <── full payload assembled      |
```

Each `stop_done` event carries that stop's full data immediately — the UI renders stops one by one as they land.

### Event schema

```python
class PipelineEvent(BaseModel):
    type: Literal[
        "profiler_done",
        "itinerary_done",
        "stop_done",       # fires once per stop as fan-out completes
        "logistics_done",
        "complete",
        "error"
    ]
    data: dict             # payload varies by type
    progress: int          # 0–100, drives the progress bar
```

### Backend (FastAPI)

```python
@app.post("/plan")
async def create_plan(request: TripRequest):
    plan_id = str(uuid4())
    queue = asyncio.Queue()
    pipeline_queues[plan_id] = queue
    asyncio.create_task(run_pipeline(plan_id, request, queue))
    return {"plan_id": plan_id}

@app.get("/plan/{plan_id}/stream")
async def stream_plan(plan_id: str):
    async def event_generator():
        queue = pipeline_queues[plan_id]
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] in ("complete", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # required — disables nginx buffering on Cloud Run
        }
    )
```

### Frontend hook

```typescript
// src/hooks/usePlanStream.ts
export function usePlanStream(planId: string) {
  const [stops, setStops] = useState<AudioStop[]>([]);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const es = new EventSource(`/api/plan/${planId}/stream`);

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      setProgress(event.progress);

      if (event.type === "stop_done") {
        setStops((prev) => [...prev, event.data]); // render each stop as it arrives
      }
      if (event.type === "complete" || event.type === "error") {
        es.close();
      }
    };

    return () => es.close(); // always clean up
  }, [planId]);

  return { stops, progress };
}
```

---

## Tech stack

| Layer       | Choices                                                                                                    |
| ----------- | ---------------------------------------------------------------------------------------------------------- |
| Agent layer | Google ADK (Python 3.12), `SequentialAgent` + `asyncio.gather` fan-out, Gemini 2.5 Flash, Pydantic schemas |
| API server  | FastAPI + Uvicorn, SSE streaming, `asyncio.Queue` per plan                                                 |
| Tools       | Google Places API, Google Maps Directions API, Google Cloud TTS, Google Cloud Storage                      |
| Frontend    | React + TypeScript, Tailwind CSS, Vite, shadcn/ui, `@vis.gl/react-google-maps`, Web Audio API              |
| Realtime    | Server-Sent Events (SSE) — pipeline progress streams from FastAPI to browser as agents complete            |
| Infra       | Docker (`python:3.12-slim`), Google Cloud Run, GitHub (public repo), GitHub Actions CI                     |
| Security    | localStorage persona, no PII to APIs, Cloud Secret Manager, HTTPS + signed GCS URLs                        |

---

## Security features

| Feature               | Detail                                                                                               |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| Local persona storage | User preferences stored in browser localStorage only — never sent to the backend or any external API |
| No PII to APIs        | Only destination strings and place IDs go to Google Places. No names, emails, or identifiers         |
| Secret management     | All API keys stored in Google Cloud Secret Manager. Never in env files or the repo                   |
| HTTPS + signed URLs   | Cloud Run enforces TLS. Generated audio URLs are signed and expire after 1 hour                      |

---

## Deployment

Two services. One deploy command each.

```
Vercel                   Cloud Run (wandr-api)
┌──────────┐             ┌──────────────────────────────────┐
│ React    │   SSE       │ FastAPI + ADK pipeline            │
│ frontend │ ─────────── │                                  │
│          │             │  Tools called directly:          │
│          │             │  - places_search()               │
│          │             │  - get_place_details()           │
│          │             │  - get_directions()              │
│          │             │  - generate_audio()              │
└──────────┘             └──────────────────────────────────┘
                                      │
                         Cloud Secret Manager
                         Cloud Storage (audio files)
```

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY ai/pyproject.toml .
RUN pip install .

COPY ai/ .

EXPOSE 8080
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Deploy backend

```bash
# one-time setup
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# store secrets
echo -n "your-key" | gcloud secrets create google-places-api-key --data-file=-
echo -n "your-key" | gcloud secrets create google-maps-api-key --data-file=-
echo -n "your-key" | gcloud secrets create google-tts-api-key --data-file=-

# build and deploy
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/wandr-api
gcloud run deploy wandr-api \
  --image gcr.io/YOUR_PROJECT_ID/wandr-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances=1 \
  --timeout=300 \
  --set-secrets="GOOGLE_PLACES_API_KEY=google-places-api-key:latest,GOOGLE_MAPS_API_KEY=google-maps-api-key:latest,GOOGLE_TTS_API_KEY=google-tts-api-key:latest"
```

`--min-instances=1` prevents cold starts during the demo. `--timeout=300` gives the pipeline enough time to complete.

### Deploy frontend

Set `VITE_API_URL` to your Cloud Run URL in Vercel environment variables. Push to main — Vercel handles the rest.

---

## 7-day sprint

| Day | Focus             | Goal                                                                                                 |
| --- | ----------------- | ---------------------------------------------------------------------------------------------------- |
| 1   | Setup + skeleton  | Repo, ADK project init, GCP APIs enabled, shared Pydantic schemas, tool stubs in `tools/`            |
| 2   | Agent cores       | Profiler + Itinerary hitting real Places API. Narrator with mock audio. Stop Processor fan-out wired |
| 3   | Integration       | First end-to-end run: "Paris, 2 days, foodie". SSE endpoint live, frontend consuming events          |
| 4   | TTS + maps        | Google TTS live. Audio player in React. Map pins via `@vis.gl/react-google-maps`                     |
| 5   | Polish + security | localStorage persona caching, error handling, skeleton loaders, UI polish. 5 personas × 3 cities     |
| 6   | Deploy + video    | Docker build, Cloud Run deploy, public URL. Record 5-min demo video                                  |
| 7   | Writeup + submit  | Kaggle writeup (2,500 words max), attach video + GitHub link, submit                                 |

---

## Project file structure

```
wandr/
├── README.md
├── .env.example                    # never commit .env
├── Dockerfile
├── .github/
│   └── workflows/
│       └── deploy.yml              # build + deploy to Cloud Run on push to main
│
├── ai/
│   ├── pyproject.toml
│   ├── __init__.py
│   ├── main.py                     # entrypoint, orchestrator bootstrap
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # root SequentialAgent, manages pipeline
│   │   ├── profiler.py             # captures user persona + trip params
│   │   ├── itinerary.py            # builds stop list, tools: places_search, get_place_details
│   │   ├── stop_research.py        # per-stop research, tools: get_place_details
│   │   ├── narrator.py             # per-stop audio, tools: generate_audio
│   │   └── logistics.py            # route optimization, tools: get_directions
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── stop_processor.py       # asyncio.gather fan-out across stops
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── server.py               # FastAPI app — /plan POST + /plan/{id}/stream SSE
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── maps.py                 # places_search, get_place_details, get_directions
│   │   └── tts.py                  # generate_audio + GCS upload + script hash cache
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── persona.py              # PersonaModel
│   │   ├── trip.py                 # StopModel, ItineraryDay, ItineraryModel
│   │   ├── research.py             # StopResearchResult
│   │   ├── audio.py                # AudioScript, AudioScriptsModel
│   │   ├── route.py                # RouteStop, RouteModel
│   │   └── events.py               # PipelineEvent
│   │
│   └── config/
│       ├── __init__.py
│       └── settings.py             # env vars, model names, constants
│
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css               # Tailwind + design tokens
│       ├── hooks/
│       │   └── usePlanStream.ts    # SSE connection + incremental state
│       ├── components/
│       │   ├── TopNav.tsx
│       │   ├── PersonaGrid.tsx
│       │   ├── StopCard.tsx
│       │   └── AudioPlayer.tsx
│       └── pages/
│           ├── HomePage.tsx
│           ├── RefinePage.tsx
│           ├── VerifyPage.tsx
│           └── ItineraryPage.tsx
│
├── outputs/                        # gitignored — generated audio files
│   └── .gitkeep
│
└── tests/
    ├── test_agents/
    ├── test_pipeline/
    ├── test_tools/
    └── fixtures/
```

**Key design decisions:**

- `agents/` contains only ADK agent definitions and system prompts — no business logic
- `tools/` holds raw API wrappers registered directly on agents — plain async functions, no protocol layer
- `pipeline/stop_processor.py` owns all parallel fan-out logic — concurrency is explicit and contained
- `api/server.py` is the only FastAPI surface — SSE streaming + plan creation, nothing else
- `models/` typed Pydantic schemas for all inter-agent hand-offs — no raw dicts anywhere

---

## The demo wow moment

Same city, two personas, back to back — 60 seconds apart in the video:

**Foodie → Tokyo**
Tsukiji outer market at 6am → best ramen in Shinjuku → Depachika basement food halls → hidden yakitori alley. Audio: enthusiastic, fast-paced, sensory language.

**Historian → Tokyo**
Senso-ji at dawn → Edo-Tokyo Museum → Imperial Palace East Gardens → Yanaka old town. Audio: contemplative, rich context, slower cadence.

> Make sure the audio actually plays out loud in the video. Judges need to hear the tone difference, not just read about it. Show the stops appearing one by one as the pipeline streams — don't cut to a finished itinerary.
