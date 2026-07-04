# Local test scripts

Run from project root with the venv active:

```bash
cd /Users/andreslinero/travel-planner-agent
source .venv/bin/activate
```

| Script | What it tests |
|--------|----------------|
| `python scripts/test_itinerary_data_flow.py` | Place search candidates -> itinerary options -> finalized place_id handoff |
| `python scripts/test_stop_research.py` | Stop Research agent + Gemini + place data |
| `python scripts/test_narrator.py` | Full research → narration for one stop |
| `python scripts/test_stop_processor.py` | Parallel pipeline (2 stops) |
| `python scripts/test_logistics.py` | Route + map pins + travel times |
| `python scripts/test_tts.py` | Standalone TTS generation, returning either inline audio or a signed GCS URL |
| `python scripts/test_tts_phase2.py` | Focused regression checks for Phase 2 signed-URL fallback behavior |

Requires `GEMINI_API_KEY` in `.env` for research/narrator/processor tests.
`test_tts.py` requires `GOOGLE_TTS_API_KEY` and returns inline audio unless both `GCS_BUCKET_NAME`
and Google Cloud credentials with upload + signing permissions are available
(`GOOGLE_APPLICATION_CREDENTIALS` locally or ambient service-account credentials in deploy).
Logistics test does not call Gemini.

Run all agent tests:

```bash
python scripts/test_stop_research.py && \
python scripts/test_narrator.py && \
python scripts/test_stop_processor.py && \
python scripts/test_logistics.py
```

## Backend + frontend (UI)

Terminal 1 — API (port 8080):

```bash
source .venv/bin/activate
cd /Users/andreslinero/travel-planner-agent
uvicorn ai.api.server:app --reload --port 8080
```

Terminal 2 — frontend (port 5173, proxies `/api` → backend):

```bash
cd /Users/andreslinero/travel-planner-agent/frontend
npm install   # first time only
npm run dev
```

Open http://localhost:5173

## Security checklist (local vs deploy)

| Item | Local dev | Before Cloud Run deploy |
|------|-----------|-------------------------|
| `.env` in `.gitignore` | OK | Never commit keys |
| CORS | `ALLOWED_ORIGINS` → Vite only | Set to your Vercel URL |
| API errors | Generic message to client | Same — details only in server logs |
| Persona in backend | Profiler builds persona server-side for pipeline | DESIGN goal: localStorage-only persona is future UI work |
| Places / Maps / TTS | Mock fallbacks when keys unset | Enable APIs + Secret Manager |
| Audio URLs | TTS stub | Signed GCS URLs with expiry |
