import asyncio
import base64
import json
import logging
from urllib.parse import quote
from uuid import uuid4
from typing import Dict, Set

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response as FastAPIResponse
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai.types import Content, Part

from ai.config.settings import settings
from ai.agents.orchestrator import orchestrator_agent
from ai.api.auth import (
    clear_session_cookie,
    dev_login_allowed,
    dev_login_user,
    get_current_user,
    set_session_cookie,
    verify_google_id_token,
)
from ai.models.api import TripRequest, SelectRequest
from ai.models.auth import AuthUser
from ai.models.events import PipelineEvent
from ai.models.tool_usage import load_tool_usage
from ai.tools.audio_store import load_plan_audio
from ai.tools.maps import autocomplete_places
from ai.tools.plan_store import (
    async_save_plan_snapshot,
    derive_plan_status,
    enrich_itinerary_dict,
    is_valid_plan_id,
    list_plan_summaries,
    load_plan_snapshot,
    save_plan_snapshot,
    user_owns_plan,
)
from ai.tools.tts import generate_audio
from ai.agents.narrator import persona_voice_style
from ai.models.persona import PersonaModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
APP_NAME = "wandr"

_cors_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

app = FastAPI(title="Wandr API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

pipeline_queues: Dict[str, asyncio.Queue] = {}
session_service = InMemorySessionService()


async def _require_owned_plan(plan_id: str, user: AuthUser):
    """Load a plan and confirm the caller owns it, else 404 (avoids leaking existence)."""
    if not is_valid_plan_id(plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
    snapshot = load_plan_snapshot(plan_id)
    if not user_owns_plan(snapshot, user.id):
        # Return 404 rather than 403 so we don't confirm that a plan exists.
        raise HTTPException(status_code=404, detail="Plan not found")
    return snapshot


def _state_with_event_delta(state: dict, event) -> dict:
    """Merge event state_delta over persisted state for race-safe reads."""
    actions = getattr(event, "actions", None)
    if not actions or not actions.state_delta:
        return state
    return {**state, **actions.state_delta}


def _stop_audio_api_url(plan_id: str, place_id: str) -> str:
    return f"/api/plan/{plan_id}/audio?place_id={quote(place_id, safe='')}"


def _normalize_stop_audio_url(plan_id: str, place_id: str, audio_url: str) -> str:
    """Always expose query-param URLs — path-style place IDs break routing."""
    if not audio_url or not place_id:
        return audio_url
    if audio_url.startswith("data:audio/") or audio_url.startswith("http://") or audio_url.startswith("https://"):
        return audio_url
    if audio_url.startswith("/api/plan/"):
        return _stop_audio_api_url(plan_id, place_id)
    return audio_url


def _public_stop_payload(plan_id: str, script: dict) -> dict:
    """Send a browser-playable URL in SSE instead of a huge inline data URL."""
    payload = dict(script)
    place_id = payload.get("place_id") or ""
    audio_url = payload.get("audio_url") or ""
    if audio_url:
        payload["audio_url"] = _normalize_stop_audio_url(plan_id, place_id, audio_url)
    return payload


def _public_itinerary_payload(state: dict) -> dict:
    """Ensure itinerary stops include persisted photos when options were cleared."""
    itinerary = state.get("itinerary")
    if not itinerary:
        return itinerary
    place_photos = state.get("place_photos") or {}
    return enrich_itinerary_dict(itinerary, place_photos)


def _public_complete_payload(plan_id: str, state: dict) -> dict:
    """Normalize persisted state for frontend replay on complete."""
    payload = dict(state)
    if payload.get("itinerary"):
        payload["itinerary"] = _public_itinerary_payload(state)
    scripts_payload = payload.get("audio_scripts")
    if scripts_payload and isinstance(scripts_payload.get("scripts"), list):
        payload["audio_scripts"] = {
            "scripts": [
                _public_stop_payload(plan_id, script)
                for script in scripts_payload["scripts"]
            ],
        }
    return payload


def _find_script_in_state(state: dict, place_id: str) -> dict | None:
    scripts = (state.get("audio_scripts") or {}).get("scripts") or []
    for script in scripts:
        if script.get("place_id") == place_id:
            return script
    return None


async def _snapshot_session_state(plan_id: str, owner_id: str) -> None:
    """Persist the latest in-memory session to disk for My Trips replay."""
    session = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
    if session is None:
        return
    await async_save_plan_snapshot(plan_id, session.state, owner_id=owner_id)


async def _ensure_plan_session(plan_id: str, owner_id: str) -> dict:
    """Load a saved plan into the in-memory session when the server restarted."""
    session = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
    if session is not None:
        return session.state

    snapshot = load_plan_snapshot(plan_id)
    if snapshot is None:
        return {}

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=owner_id,
        session_id=plan_id,
    )
    session = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
    if session is None:
        return snapshot.state

    from google.adk.events import Event, EventActions

    await session_service.append_event(
        session=session,
        event=Event(
            author="system",
            actions=EventActions(state_delta=snapshot.state),
        ),
    )
    refreshed = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
    return {} if refreshed is None else refreshed.state


def _ensure_plan_queue(plan_id: str) -> asyncio.Queue:
    if plan_id not in pipeline_queues:
        pipeline_queues[plan_id] = asyncio.Queue()
    return pipeline_queues[plan_id]


def _rate_limit_error_message(error: Exception) -> str:
    text = str(error).lower()
    if any(token in text for token in ("429", "resource_exhausted", "rate limit", "quota")):
        return (
            "Wandr hit a temporary API quota/rate limit while planning your trip. "
            "Please retry in a minute."
        )
    if any(token in text for token in ("503", "unavailable", "high demand", "overloaded")):
        return (
            "Gemini is temporarily overloaded. Wandr tried multiple models — "
            "please wait a moment and tap Start Over."
        )
    return "Pipeline failed. Please try again or adjust your request."


async def _clear_pipeline_error(plan_id: str, owner_id: str) -> None:
    """Remove a stale error marker before a new pipeline run."""
    session = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
    if session is None or session.state.get("pipeline_error") is None:
        return
    from google.adk.events import Event, EventActions

    await session_service.append_event(
        session=session,
        event=Event(
            author="system",
            actions=EventActions(state_delta={"pipeline_error": None}),
        ),
    )


async def _persist_pipeline_error(plan_id: str, message: str, owner_id: str) -> None:
    """Persist user-facing errors so reconnecting SSE clients can replay them."""
    session = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
    if session is None:
        return
    from google.adk.events import Event, EventActions

    await session_service.append_event(
        session=session,
        event=Event(
            author="system",
            actions=EventActions(state_delta={"pipeline_error": {"message": message}}),
        ),
    )


async def run_pipeline(plan_id: str, request: TripRequest, queue: asyncio.Queue, owner_id: str):
    """
    Execute the orchestrator pipeline for one turn and stream PipelineEvents
    into the queue.  Handles both the initial plan request and subsequent
    re-runs triggered by VerifyPage (refine / finalize).
    """
    try:
        await _clear_pipeline_error(plan_id, owner_id)

        runner = Runner(
            agent=orchestrator_agent,
            app_name=APP_NAME,
            session_service=session_service,
        )

        existing = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
        if existing is None:
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=owner_id,
                session_id=plan_id,
            )

        parts = []
        if request.vibe:
            parts.append(f"Vibe/Description: {request.vibe}")
        if request.current_location:
            parts.append(f"Current location: {request.current_location}")
        if request.destination:
            parts.append(f"Destination: {request.destination}")
        if request.duration:
            parts.append(f"Duration: {request.duration}")
        if request.persona_type:
            parts.append(f"Preferred persona type: {request.persona_type}")
        if request.transit_preference:
            parts.append(f"Transit preference: {request.transit_preference}")
        # For SelectRequest (refine/finalize) include refinement_text in the message
        # so it lands in conversation history that the itinerary agent reads.
        if hasattr(request, "refinement_text") and request.refinement_text:
            parts.append(f"Refinement request: {request.refinement_text}")

        initial_text = "\n".join(parts) if parts else "Continue planning my trip."
        user_message = Content(role="user", parts=[Part(text=initial_text)])

        progress = 10
        emitted_phases: Set[str] = set()

        async for event in runner.run_async(
            user_id=owner_id,
            session_id=plan_id,
            new_message=user_message,
        ):
            current_session = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
            state = {} if current_session is None else current_session.state
            effective_state = _state_with_event_delta(state, event)

            author = event.author
            text = ""
            if event.content and event.content.parts:
                text = event.content.parts[0].text or ""

            if author == "profiler":
                persona_payload = effective_state.get("persona")
                if persona_payload is not None:
                    if "profiler_done" not in emitted_phases:
                        progress = 30
                        logger.info("Profiler resolved persona for plan %s.", plan_id)
                        await queue.put(PipelineEvent(
                            type="profiler_done",
                            data=persona_payload,
                            progress=progress
                        ).model_dump())
                        emitted_phases.add("profiler_done")
                        await _snapshot_session_state(plan_id, owner_id)
                else:
                    # Clarifying question — surface to user and pause
                    progress = 20
                    logger.info(
                        "Profiler clarification required for plan %s. message=%r",
                        plan_id,
                        text,
                    )
                    await queue.put(PipelineEvent(
                        type="profiler_clarification",
                        data={"message": text or "Where are you heading, and how much time do you have?"},
                        progress=progress
                    ).model_dump())
                    return

            elif author == "itinerary":
                itinerary_options_payload = effective_state.get("itinerary_options")
                itinerary_payload = effective_state.get("itinerary")

                if itinerary_options_payload is not None and "itinerary_options" not in emitted_phases:
                    # Options mode — user needs to review before we continue
                    progress = 40
                    logger.info(
                        "Itinerary options ready for plan %s — broadcasting itinerary_options event.",
                        plan_id,
                    )
                    await queue.put(PipelineEvent(
                        type="itinerary_options",
                        data=itinerary_options_payload,
                        progress=progress
                    ).model_dump())
                    emitted_phases.add("itinerary_options")
                    await _snapshot_session_state(plan_id, owner_id)
                    if itinerary_payload is None:
                        logger.info(
                            "Pipeline paused at itinerary options for plan %s. "
                            "Stop processor and logistics will run after finalize.",
                            plan_id,
                        )

                if itinerary_payload is not None and "itinerary_done" not in emitted_phases:
                    # Final mode — itinerary is locked in
                    progress = 50
                    logger.info(
                        "Itinerary finalised for plan %s — broadcasting itinerary_done event.",
                        plan_id,
                    )
                    await queue.put(PipelineEvent(
                        type="itinerary_done",
                        data=_public_itinerary_payload(effective_state),
                        progress=progress
                    ).model_dump())
                    emitted_phases.add("itinerary_done")
                    await _snapshot_session_state(plan_id, owner_id)

            elif author == "orchestrator":
                audio_scripts_payload = effective_state.get("audio_scripts")
                if (
                    audio_scripts_payload is not None
                    and "scripts" in audio_scripts_payload
                ):
                    if "stop_done" not in emitted_phases:
                        progress = 80
                        logger.info(
                            "Broadcasting %d stop_done events for plan %s.",
                            len(audio_scripts_payload["scripts"]),
                            plan_id,
                        )
                        for script in audio_scripts_payload["scripts"]:
                            await queue.put(PipelineEvent(
                                type="stop_done",
                                data=_public_stop_payload(plan_id, script),
                                progress=progress
                            ).model_dump())
                        emitted_phases.add("stop_done")
                        await _snapshot_session_state(plan_id, owner_id)

            elif author == "logistics":
                route_payload = effective_state.get("route")
                if route_payload is not None:
                    if "logistics_done" not in emitted_phases:
                        progress = 90
                        logger.info("Logistics route ready for plan %s.", plan_id)
                        await queue.put(PipelineEvent(
                            type="logistics_done",
                            data=route_payload,
                            progress=progress
                        ).model_dump())
                        emitted_phases.add("logistics_done")
                        await _snapshot_session_state(plan_id, owner_id)

        # Pipeline run complete
        current_session = await session_service.get_session(app_name=APP_NAME, user_id=owner_id, session_id=plan_id)
        final_state = {} if current_session is None else current_session.state
        if final_state.get("itinerary_options") is not None and final_state.get("itinerary") is None:
            logger.info(
                "Pipeline paused for plan %s with itinerary_options awaiting user confirmation; "
                "not emitting complete event yet.",
                plan_id,
            )
            await _snapshot_session_state(plan_id, owner_id)
            return

        progress = 100
        await _snapshot_session_state(plan_id, owner_id)
        await queue.put(PipelineEvent(
            type="complete",
            data=_public_complete_payload(plan_id, final_state),
            progress=progress
        ).model_dump())

    except Exception as e:
        logger.error("Pipeline error for plan %s: %s", plan_id, e, exc_info=True)
        user_message = _rate_limit_error_message(e)
        logger.info("Pipeline user-facing error for plan %s: %s", plan_id, user_message)
        await _persist_pipeline_error(plan_id, user_message, owner_id)
        await _snapshot_session_state(plan_id, owner_id)
        await queue.put(PipelineEvent(
            type="error",
            data={"message": user_message},
            progress=100
        ).model_dump())


@app.post("/api/auth/google")
async def auth_google(response: FastAPIResponse, credential: str = Body(..., embed=True)):
    """Exchange a Google Identity Services ID token for a session cookie."""
    user = verify_google_id_token(credential)
    set_session_cookie(response, user)
    return {"user": user.model_dump()}


@app.post("/api/auth/dev-login")
async def auth_dev_login(response: FastAPIResponse, email: str | None = Body(None, embed=True)):
    """Local-only login shortcut. Disabled in production (see dev_login_allowed)."""
    if not dev_login_allowed():
        raise HTTPException(status_code=403, detail="Dev login is disabled.")
    user = dev_login_user(email)
    set_session_cookie(response, user)
    return {"user": user.model_dump()}


@app.post("/api/auth/logout")
async def auth_logout(response: FastAPIResponse):
    clear_session_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me")
async def auth_me(user: AuthUser = Depends(get_current_user)):
    return {"user": user.model_dump(), "dev_login_available": dev_login_allowed()}


@app.get("/api/auth/config")
async def auth_config():
    """Public: tells the frontend which sign-in methods are available."""
    return {
        "google_client_id": settings.google_oauth_client_id or "",
        "dev_login_available": dev_login_allowed(),
    }


@app.post("/api/plan")
async def create_plan(request: TripRequest, user: AuthUser = Depends(get_current_user)):
    plan_id = str(uuid4())
    queue = asyncio.Queue()
    pipeline_queues[plan_id] = queue
    save_plan_snapshot(
        plan_id,
        {"trip_request": request.model_dump(exclude_none=True)},
        owner_id=user.id,
    )
    asyncio.create_task(run_pipeline(plan_id, request, queue, user.id))
    return {"plan_id": plan_id}


@app.post("/api/plan/{plan_id}/reply")
async def reply_plan(plan_id: str, request: TripRequest, user: AuthUser = Depends(get_current_user)):
    """Resume the pipeline after a profiler clarification answer."""
    await _require_owned_plan(plan_id, user)
    if plan_id not in pipeline_queues:
        pipeline_queues[plan_id] = asyncio.Queue()
    queue = pipeline_queues[plan_id]

    # Clear any stale finalised state so agents don't skip themselves when
    # the user is replying with a new clarification or starting a fresh run.
    # Without this, ItineraryAgent sees a non-null 'itinerary' and returns early,
    # and LogisticsAgent sees a non-null 'route' and does the same.
    current_session = await session_service.get_session(app_name=APP_NAME, user_id=user.id, session_id=plan_id)
    if current_session is not None:
        stale_keys = ("itinerary", "route", "audio_scripts", "itinerary_action",
                      "itinerary_options", "itinerary_options_confirmed", "itinerary_refinement_text")
        stale_state = {k: None for k in stale_keys if current_session.state.get(k) is not None}
        if stale_state:
            from google.adk.events import Event as _Event, EventActions as _EventActions
            await session_service.append_event(
                session=current_session,
                event=_Event(
                    author="system",
                    actions=_EventActions(state_delta=stale_state),
                ),
            )
            logger.info(
                "reply_plan: cleared stale state keys %s for plan %s",
                list(stale_state.keys()), plan_id,
            )

    asyncio.create_task(run_pipeline(plan_id, request, queue, user.id))
    return {"plan_id": plan_id}


@app.post("/api/plan/{plan_id}/select")
async def select_places(plan_id: str, body: SelectRequest, user: AuthUser = Depends(get_current_user)):
    """
    Called by VerifyPage when the user:
      1. Submits the refine textarea — reruns the itinerary agent with their
         refinement text while keeping already-confirmed places.
      2. Clicks "Finalize Itinerary" — runs the agent in final mode with
         the confirmed places.

    This endpoint:
    - Reads the current itinerary_options from session state
    - Builds the list of confirmed PlaceOptionModel dicts from the given IDs
    - Writes itinerary_options_confirmed + optional refinement_text to session state
    - For "finalize": clears itinerary_options from state so the agent runs in
      final mode and writes to the "itinerary" key
    - Runs the pipeline
    """
    await _require_owned_plan(plan_id, user)
    logger.info(
        "select_places called. plan_id=%s action=%s confirmed=%s refinement=%r",
        plan_id, body.action, body.confirmed_place_ids, body.refinement_text,
    )

    # Always create a fresh queue for the new pipeline run so no stale events
    # (e.g. the 'complete' event from the previous itinerary_options run) leak
    # into the new SSE stream and cause it to close prematurely.
    queue = asyncio.Queue()
    pipeline_queues[plan_id] = queue

    # Pull the current session so we can update state before re-running.
    # If the in-memory session is gone (e.g. server restarted), restore it
    # from the disk snapshot so we can read itinerary_options and proceed.
    current_session = await session_service.get_session(app_name=APP_NAME, user_id=user.id, session_id=plan_id)
    if current_session is None:
        logger.warning(
            "select_places: in-memory session %s not found — attempting snapshot restore.", plan_id
        )
        await _ensure_plan_session(plan_id, user.id)
        current_session = await session_service.get_session(app_name=APP_NAME, user_id=user.id, session_id=plan_id)
    if current_session is None:
        logger.error("select_places: session %s could not be restored.", plan_id)
        raise HTTPException(status_code=404, detail="Plan session not found. Please start over.")

    # Build confirmed place list from the stored options and the user's selection.
    options_dict = current_session.state.get("itinerary_options", {})
    confirmed_places: list[dict] = []
    confirmed_ids = set(body.confirmed_place_ids)
    for day in options_dict.get("days", []):
        for order, place in enumerate(day.get("options", []), start=1):
            if place.get("place_id") in confirmed_ids:
                confirmed_places.append({
                    "place_id": place["place_id"],
                    "name": place["name"],
                    "address": place.get("address", "Unknown"),
                    "photo_url": place.get("photo_url", ""),
                    "suggested_duration": place.get("suggested_duration", ""),
                    "description": place.get("description", ""),
                    "must_see": place.get("must_see", False),
                    "hours_of_operation": place.get("hours_of_operation", "Unknown"),
                    "persona_note": place.get("persona_note", ""),
                    "day": day["day"],
                    "order": order,
                })

    logger.info(
        "Resolved %d confirmed places from %d IDs provided.",
        len(confirmed_places), len(confirmed_ids),
    )

    # Persist photo URLs so the final itinerary and reconnecting clients keep images
    # even after itinerary_options is cleared from session state.
    place_photos: dict[str, str] = dict(current_session.state.get("place_photos") or {})
    for day in options_dict.get("days", []):
        for place in day.get("options", []):
            place_id = place.get("place_id")
            photo_url = place.get("photo_url")
            if place_id and photo_url:
                place_photos[place_id] = photo_url
    for place in confirmed_places:
        place_id = place.get("place_id")
        photo_url = place.get("photo_url")
        if place_id and photo_url:
            place_photos[place_id] = photo_url

    # Update session state properly by appending an event with a state_delta.
    # This persists the confirmed places and refinement text, and explicitly deletes
    # the stale itinerary_options so the pipeline doesn't immediately replay them.
    # We also MUST clear itinerary, route, and audio_scripts so that if the user
    # went "Back" from a finalized plan to refine again, the agents don't skip themselves.
    from google.adk.events import Event, EventActions
    update_event = Event(
        author="system",
        actions=EventActions(
            state_delta={
                "itinerary_options_confirmed": confirmed_places,
                "itinerary_refinement_text": body.refinement_text,
                "itinerary_action": body.action,
                "place_photos": place_photos,
                "itinerary_options": None,
                "itinerary": None,
                "route": None,
                "audio_scripts": None,
            }
        )
    )
    await session_service.append_event(
        session=current_session,
        event=update_event
    )
    await _snapshot_session_state(plan_id, user.id)

    if body.action == "finalize":
        # Inject a synthetic user message that triggers the agent's final mode.
        run_body = body.model_copy(update={
            "vibe": "Finalize my itinerary with the confirmed places. I am happy with my selection."
        })
        logger.info("Finalizing itinerary for plan %s.", plan_id)
    else:
        run_body = body
        logger.info(
            "Refining itinerary for plan %s with text: %r", plan_id, body.refinement_text
        )

    asyncio.create_task(run_pipeline(plan_id, run_body, queue, user.id))
    return {"plan_id": plan_id, "action": body.action}


@app.get("/api/places/autocomplete")
async def places_autocomplete(
    query: str = Query("", min_length=0, max_length=200),
    user: AuthUser = Depends(get_current_user),
):
    suggestions = await autocomplete_places(query)
    return {"suggestions": suggestions}


async def _regenerate_stop_audio(plan_id: str, place_id: str, state: dict) -> bytes | None:
    """Re-synthesize MP3 when the script exists but the file was never saved."""
    script = _find_script_in_state(state, place_id)
    if script is None:
        return None

    text = (script.get("script") or "").strip()
    if not text or text.startswith("We could not generate narration"):
        return None

    persona_dict = state.get("persona")
    if not persona_dict:
        return None

    try:
        persona = PersonaModel.model_validate(persona_dict)
        voice_style = persona_voice_style(persona)
        await generate_audio(
            text,
            voice_style,
            plan_id=plan_id,
            place_id=place_id,
        )
        logger.info("On-demand TTS regenerated audio for plan=%s place=%s", plan_id, place_id)
        return load_plan_audio(plan_id, place_id)
    except Exception as exc:
        logger.warning(
            "On-demand TTS regen failed for plan=%s place=%s: %s",
            plan_id,
            place_id,
            exc,
        )
        return None


async def _stream_stop_audio_bytes(plan_id: str, place_id: str, owner_id: str) -> Response:
    """Load or regenerate MP3 bytes for one stop narration."""
    audio_bytes = load_plan_audio(plan_id, place_id)
    if audio_bytes:
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "private, max-age=86400"},
        )

    state = await _ensure_plan_session(plan_id, owner_id)
    if not state:
        raise HTTPException(status_code=404, detail="Plan not found")

    script = _find_script_in_state(state, place_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Audio not found for this stop")

    stored_url = script.get("audio_url") or ""
    if stored_url.startswith("data:audio/"):
        try:
            _, encoded = stored_url.split(",", 1)
            audio_bytes = base64.b64decode(encoded)
        except (ValueError, base64.binascii.Error) as exc:
            raise HTTPException(status_code=500, detail="Stored audio is corrupt") from exc
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    if stored_url.startswith("http://") or stored_url.startswith("https://"):
        return RedirectResponse(stored_url, status_code=302)

    # API URL saved but file missing — try one on-demand TTS pass.
    audio_bytes = await _regenerate_stop_audio(plan_id, place_id, state)
    if audio_bytes:
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "private, max-age=86400"},
        )

    if not stored_url:
        raise HTTPException(status_code=404, detail="No audio generated for this stop")
    raise HTTPException(status_code=404, detail="Narration audio file missing for this stop")


@app.get("/api/plan/{plan_id}/audio")
async def stream_stop_audio(
    plan_id: str,
    place_id: str = Query(..., min_length=1),
    user: AuthUser = Depends(get_current_user),
):
    """Stream synthesized MP3 bytes for a stop — used by the frontend <audio> element."""
    await _require_owned_plan(plan_id, user)
    return await _stream_stop_audio_bytes(plan_id, place_id, user.id)


@app.get("/api/plan/{plan_id}/audio/{place_id:path}")
async def stream_stop_audio_legacy(
    plan_id: str,
    place_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Backwards-compatible path route for older saved audio URLs."""
    await _require_owned_plan(plan_id, user)
    return await _stream_stop_audio_bytes(plan_id, place_id, user.id)


@app.get("/api/trips")
async def list_trips(user: AuthUser = Depends(get_current_user)):
    """List saved trips for the My Trips page — scoped to the authenticated user."""
    summaries = list_plan_summaries(owner_id=user.id)
    return {"trips": [summary.model_dump(mode="json") for summary in summaries]}


@app.get("/api/plan/{plan_id}")
async def get_plan(plan_id: str, user: AuthUser = Depends(get_current_user)):
    """Return a saved plan summary + status for direct navigation."""
    snapshot = await _require_owned_plan(plan_id, user)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {
        "plan_id": snapshot.plan_id,
        "status": snapshot.status,
        "summary": snapshot.summary.model_dump(mode="json"),
    }


@app.get("/api/plan/{plan_id}/tool-usage")
async def get_tool_usage(plan_id: str, user: AuthUser = Depends(get_current_user)):
    await _require_owned_plan(plan_id, user)
    current_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user.id,
        session_id=plan_id,
    )
    usage = load_tool_usage(None if current_session is None else current_session.state.get("tool_usage"))
    return usage.model_dump()


@app.get("/api/plan/{plan_id}/stream")
async def stream_plan(plan_id: str, user: AuthUser = Depends(get_current_user)):
    owner_id = user.id
    await _require_owned_plan(plan_id, user)

    async def event_generator():
        state = await _ensure_plan_session(plan_id, owner_id)
        snapshot = load_plan_snapshot(plan_id)
        if not state and snapshot is None:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Plan not found'}, 'progress': 100})}\n\n"
            return

        queue = _ensure_plan_queue(plan_id)

        # Replay current state so reconnecting clients catch up immediately.
        try:
            pipeline_error = state.get("pipeline_error")
            if pipeline_error is not None:
                yield f"data: {json.dumps({'type': 'error', 'data': pipeline_error, 'progress': 100})}\n\n"
                return

            if state.get("persona") is not None:
                yield f"data: {json.dumps({'type': 'profiler_done', 'data': state['persona'], 'progress': 30})}\n\n"
            if state.get("itinerary_options") is not None:
                yield f"data: {json.dumps({'type': 'itinerary_options', 'data': state['itinerary_options'], 'progress': 40})}\n\n"
            if state.get("itinerary") is not None:
                yield f"data: {json.dumps({'type': 'itinerary_done', 'data': _public_itinerary_payload(state), 'progress': 50})}\n\n"
            if state.get("audio_scripts") is not None and "scripts" in state["audio_scripts"]:
                for script in state["audio_scripts"]["scripts"]:
                    public_script = _public_stop_payload(plan_id, script)
                    yield f"data: {json.dumps({'type': 'stop_done', 'data': public_script, 'progress': 80})}\n\n"
            if state.get("route") is not None:
                yield f"data: {json.dumps({'type': 'logistics_done', 'data': state['route'], 'progress': 90})}\n\n"

            status = derive_plan_status(state)
            if status == "complete":
                yield f"data: {json.dumps({'type': 'complete', 'data': _public_complete_payload(plan_id, state), 'progress': 100})}\n\n"
                return
            if status == "awaiting_selection":
                return
        except Exception:
            pass

        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] in ("complete", "error", "profiler_clarification", "itinerary_options"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
