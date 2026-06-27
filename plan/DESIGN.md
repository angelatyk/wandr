# Wandr

> AI-powered personalized travel guide with audio narration — Kaggle AI Agents Capstone

**Track:** Concierge Agents | **Stack:** Google ADK multi-agent | **Timeline:** 1 week

---

## Evaluation checklist

| Requirement              | How we satisfy it                                         |
| ------------------------ | --------------------------------------------------------- |
| Multi-agent system (ADK) | 5 specialized agents via Google ADK `SequentialAgent`     |
| MCP server               | Custom MCP server wrapping Google Places + Cloud TTS      |
| Security features        | Persona stored locally in browser, no PII sent to any API |
| Deployability            | Dockerized, deployed to Cloud Run — live URL for judges   |
| Agent skills / CLI       | ADK CLI configures persona skill per agent                |
| Antigravity              | Persona switch + live audio playback in demo video        |

---

## Agent architecture

### How state flows

All agents run inside a `SequentialAgent`, sharing a single `session.state` dict. Each agent writes its output to a named key via `output_key`; the next agent reads it directly from state or via `{key}` injection in its instruction string. Structured outputs use Pydantic schemas.

```
Profiler → session.state["persona"]
         ↓
Research → reads: persona  →  writes: session.state["locations"]
         ↓
Itinerary → reads: locations, persona  →  writes: session.state["itinerary"]
         ↓
Narrator → reads: itinerary, persona  →  writes: session.state["audio_scripts"]
         ↓
Orchestrator assembles final response
```

---

### Orchestrator

**ADK type:** `SequentialAgent`

The ADK root. Wraps all sub-agents in a `SequentialAgent`, owns the `session.state`, and assembles the final response. Handles errors if any sub-agent fails and triggers re-runs on user edits.

- Parses and validates the initial user request
- Passes `InvocationContext` to each sub-agent in sequence
- Merges all state keys into final itinerary + audio response
- Supports re-generation when user changes persona or destination

---

### Profiler agent

**ADK type:** `LlmAgent`
**State:** `output_key="persona"` | `output_schema=PersonaModel`

Captures and enriches the user's travel persona. Produces a structured Pydantic object written to `session.state["persona"]`.

- Classifies persona: foodie / artist / historian / adventurer / local-life
- Infers pace, budget level, accessibility needs from conversation
- Persona object stored locally in browser (never sent to backend)
- On repeat visits, reads saved persona from localStorage and skips elicitation

---

### Research agent

**ADK type:** `LlmAgent`
**State:** reads `session.state["persona"]` via `{persona}` injection | `output_key="locations"`

Reads `{persona}` from state (injected into its instruction), queries the MCP server for location candidates, ranks them by persona fit, and enriches each with context facts for the narrator.

- Calls `places_search(destination, persona_type)` via MCP
- Scores and filters locations by persona vector
- Calls `get_place_details(place_id)` to enrich each result
- Flags locations that may be closed or seasonal

---

### Itinerary agent

**ADK type:** `LlmAgent`
**State:** reads `session.state["locations"]`, `session.state["persona"]` | `output_key="itinerary"` | `output_schema=ItineraryModel`

Reads the location list and persona, builds a structured day-by-day plan optimized for route efficiency, visit duration, meal timing, and persona fit.

- Route optimization via nearest-neighbor across stops
- Time-slots meals, attractions, and breaks by persona rhythm
- Balances must-see vs hidden gem ratio per persona type
- Handles multi-day trips with clean day boundaries

---

### Narrator agent

**ADK type:** `LlmAgent`
**State:** reads `session.state["itinerary"]`, `session.state["persona"]` | `output_key="audio_scripts"` | `output_schema=AudioScriptsModel`

For each stop, writes a 60–90s audio script in a persona-matched tone, then calls Google Cloud TTS via MCP to generate the actual audio file.

- Tone adapts per persona: dramatic / enthusiastic / contemplative / energetic / warm
- Script length tuned for walking pace between stops
- Calls `generate_audio(script, voice_style)` via MCP → returns signed GCS audio URL
- Audio responses cached by script hash to avoid re-billing on re-renders
- Graceful fallback: returns text script if TTS call fails

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

# Research output
class LocationModel(BaseModel):
    place_id: str
    name: str
    address: str
    persona_score: float        # 0–1 fit score
    context_facts: list[str]   # fed to narrator

# Itinerary output
class ItineraryDay(BaseModel):
    day: int
    stops: list[LocationModel]

class ItineraryModel(BaseModel):
    destination: str
    days: list[ItineraryDay]

# Narrator output
class AudioScript(BaseModel):
    place_id: str
    script: str        # narration text
    audio_url: str     # signed GCS URL from TTS
    duration_sec: int

class AudioScriptsModel(BaseModel):
    scripts: list[AudioScript]
```

---

## MCP server

The MCP server exposes three tools, wrapping Google Places API and Google Cloud TTS.

### `places_search(destination, persona_type, limit)`

Wraps Google Places API. Returns top N locations ranked by persona type.

- Foodie → restaurants, markets
- Artist → galleries, murals
- Historian → monuments, museums
- Adventurer → parks, trails
- Local-life → neighbourhoods, cafes

### `get_place_details(place_id)`

Fetches enriched data for a specific place: opening hours, rating, editorial summary. Used by the Research agent to validate and enrich candidates before passing to the Narrator.

### `generate_audio(script, voice_style)`

Wraps Google Cloud TTS. Accepts a narration script and voice style (dramatic / enthusiastic / contemplative / energetic / warm). Returns a signed GCS audio URL. Responses are cached by script hash — the same script is never billed twice.

---

## Tech stack

| Layer       | Choices                                                                         |
| ----------- | ------------------------------------------------------------------------------- |
| Agent layer | Google ADK (Python), `SequentialAgent`, Gemini 2.5 Flash, Pydantic schemas      |
| MCP server  | Python MCP server, Google Places API, Google Cloud TTS, FastAPI transport       |
| Frontend    | React + TypeScript, Tailwind CSS, Web Audio API, Vite                           |
| Infra       | Docker, Google Cloud Run, GitHub (public repo), GitHub Actions CI               |
| Security    | localStorage persona, no PII to APIs, Cloud Secret Manager, HTTPS + signed URLs |

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

## The demo wow moment

Same city, two personas, back to back — 60 seconds apart in the video:

**Foodie → Tokyo**
Tsukiji outer market at 6am → best ramen in Shinjuku → Depachika basement food halls → hidden yakitori alley. Audio: enthusiastic, fast-paced, sensory language.

**Historian → Tokyo**
Senso-ji at dawn → Edo-Tokyo Museum → Imperial Palace East Gardens → Yanaka old town. Audio: contemplative, rich context, slower cadence.

> Make sure the audio actually plays out loud in the video. Judges need to hear the tone difference, not just read about it.
