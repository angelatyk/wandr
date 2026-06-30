import asyncio
import json
import logging
from uuid import uuid4
from typing import Dict, Set

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai.types import Content, Part

from ai.agents.orchestrator import orchestrator_agent
from ai.models.api import TripRequest, SelectRequest
from ai.models.events import PipelineEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Wandr API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline_queues: Dict[str, asyncio.Queue] = {}
session_service = InMemorySessionService()


async def run_pipeline(plan_id: str, request: TripRequest, queue: asyncio.Queue):
    """
    Execute the orchestrator pipeline for one turn and stream PipelineEvents
    into the queue.  Handles both the initial plan request and subsequent
    re-runs triggered by VerifyPage (refine / finalize).
    """
    try:
        runner = Runner(
            agent=orchestrator_agent,
            app_name="agents",
            session_service=session_service,
        )

        existing = await session_service.get_session(app_name="agents", user_id="user", session_id=plan_id)
        if existing is None:
            await session_service.create_session(
                app_name="agents",
                user_id="user",
                session_id=plan_id,
            )

        parts = []
        if request.vibe:
            parts.append(f"Vibe/Description: {request.vibe}")
        if request.location:
            parts.append(f"Location: {request.location}")
        if request.duration:
            parts.append(f"Duration: {request.duration}")
        # For SelectRequest (refine/finalize) include refinement_text in the message
        # so it lands in conversation history that the itinerary agent reads.
        if hasattr(request, "refinement_text") and request.refinement_text:
            parts.append(f"Refinement request: {request.refinement_text}")

        initial_text = "\n".join(parts) if parts else "Continue planning my trip."
        user_message = Content(role="user", parts=[Part(text=initial_text)])

        progress = 10
        emitted_phases: Set[str] = set()

        async for event in runner.run_async(
            user_id="user",
            session_id=plan_id,
            new_message=user_message,
        ):
            current_session = await session_service.get_session(app_name="agents", user_id="user", session_id=plan_id)
            state = current_session.state

            author = event.author
            text = ""
            if event.content and event.content.parts:
                text = event.content.parts[0].text or ""

            if author == "profiler":
                if state.get("persona") is not None:
                    if "profiler_done" not in emitted_phases:
                        progress = 30
                        await queue.put(PipelineEvent(
                            type="profiler_done",
                            data=state["persona"],
                            progress=progress
                        ).model_dump())
                        emitted_phases.add("profiler_done")
                else:
                    # Clarifying question — surface to user and pause
                    progress = 20
                    await queue.put(PipelineEvent(
                        type="profiler_clarification",
                        data={"message": text},
                        progress=progress
                    ).model_dump())
                    return

            elif author == "itinerary":
                if state.get("itinerary_options") is not None and "itinerary_options" not in emitted_phases:
                    # Options mode — user needs to review before we continue
                    progress = 40
                    logger.info(
                        "Itinerary options ready for plan %s — broadcasting itinerary_options event.",
                        plan_id,
                    )
                    await queue.put(PipelineEvent(
                        type="itinerary_options",
                        data=state["itinerary_options"],
                        progress=progress
                    ).model_dump())
                    emitted_phases.add("itinerary_options")

                if state.get("itinerary") is not None and "itinerary_done" not in emitted_phases:
                    # Final mode — itinerary is locked in
                    progress = 50
                    logger.info(
                        "Itinerary finalised for plan %s — broadcasting itinerary_done event.",
                        plan_id,
                    )
                    await queue.put(PipelineEvent(
                        type="itinerary_done",
                        data=state["itinerary"],
                        progress=progress
                    ).model_dump())
                    emitted_phases.add("itinerary_done")

            elif author == "orchestrator":
                if state.get("audio_scripts") is not None and "scripts" in state["audio_scripts"]:
                    if "stop_done" not in emitted_phases:
                        progress = 80
                        for script in state["audio_scripts"]["scripts"]:
                            await queue.put(PipelineEvent(
                                type="stop_done",
                                data=script,
                                progress=progress
                            ).model_dump())
                        emitted_phases.add("stop_done")

            elif author == "logistics":
                if state.get("route") is not None:
                    if "logistics_done" not in emitted_phases:
                        progress = 90
                        await queue.put(PipelineEvent(
                            type="logistics_done",
                            data=state["route"],
                            progress=progress
                        ).model_dump())
                        emitted_phases.add("logistics_done")

        # Pipeline run complete
        progress = 100
        current_session = await session_service.get_session(app_name="agents", user_id="user", session_id=plan_id)
        await queue.put(PipelineEvent(
            type="complete",
            data=current_session.state,
            progress=progress
        ).model_dump())

    except Exception as e:
        logger.error("Pipeline error for plan %s: %s", plan_id, e, exc_info=True)
        await queue.put(PipelineEvent(
            type="error",
            data={"message": str(e)},
            progress=100
        ).model_dump())


@app.post("/api/plan")
async def create_plan(request: TripRequest):
    plan_id = str(uuid4())
    queue = asyncio.Queue()
    pipeline_queues[plan_id] = queue
    asyncio.create_task(run_pipeline(plan_id, request, queue))
    return {"plan_id": plan_id}


@app.post("/api/plan/{plan_id}/reply")
async def reply_plan(plan_id: str, request: TripRequest):
    """Resume the pipeline after a profiler clarification answer."""
    if plan_id not in pipeline_queues:
        pipeline_queues[plan_id] = asyncio.Queue()
    queue = pipeline_queues[plan_id]
    asyncio.create_task(run_pipeline(plan_id, request, queue))
    return {"plan_id": plan_id}


@app.post("/api/plan/{plan_id}/select")
async def select_places(plan_id: str, body: SelectRequest):
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
    current_session = await session_service.get_session(app_name="agents", user_id="user", session_id=plan_id)
    if current_session is None:
        logger.error("select_places: session %s not found.", plan_id)
        return {"error": "Session not found"}, 404

    # Build confirmed place list from the stored options and the user's selection.
    options_dict = current_session.state.get("itinerary_options", {})
    confirmed_places: list[dict] = []
    confirmed_ids = set(body.confirmed_place_ids)
    for day in options_dict.get("days", []):
        for place in day.get("options", []):
            if place.get("place_id") in confirmed_ids:
                confirmed_places.append({
                    "place_id": place["place_id"],
                    "name": place["name"],
                    "day": day["day"],
                })

    logger.info(
        "Resolved %d confirmed places from %d IDs provided.",
        len(confirmed_places), len(confirmed_ids),
    )

    # Update session state properly by appending an event with a state_delta.
    # This persists the confirmed places and refinement text, and explicitly deletes
    # the stale itinerary_options so the pipeline doesn't immediately replay them.
    from google.adk.events import Event, EventActions
    update_event = Event(
        author="system",
        actions=EventActions(
            state_delta={
                "itinerary_options_confirmed": confirmed_places,
                "itinerary_refinement_text": body.refinement_text,
                "itinerary_options": None
            }
        )
    )
    await session_service.append_event(
        session=current_session,
        event=update_event
    )

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

    asyncio.create_task(run_pipeline(plan_id, run_body, queue))
    return {"plan_id": plan_id, "action": body.action}



@app.get("/api/plan/{plan_id}/stream")
async def stream_plan(plan_id: str):
    async def event_generator():
        if plan_id not in pipeline_queues:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Plan not found'}, 'progress': 100})}\n\n"
            return

        # Replay current state so reconnecting clients (e.g. after page refresh)
        # catch up immediately without waiting for the next pipeline event.
        try:
            current_session = await session_service.get_session(app_name="agents", user_id="user", session_id=plan_id)
            state = current_session.state

            if state.get("persona") is not None:
                yield f"data: {json.dumps({'type': 'profiler_done', 'data': state['persona'], 'progress': 30})}\n\n"
            if state.get("itinerary_options") is not None:
                yield f"data: {json.dumps({'type': 'itinerary_options', 'data': state['itinerary_options'], 'progress': 40})}\n\n"
            if state.get("itinerary") is not None:
                yield f"data: {json.dumps({'type': 'itinerary_done', 'data': state['itinerary'], 'progress': 50})}\n\n"
            if state.get("audio_scripts") is not None and "scripts" in state["audio_scripts"]:
                for script in state["audio_scripts"]["scripts"]:
                    yield f"data: {json.dumps({'type': 'stop_done', 'data': script, 'progress': 80})}\n\n"
            if state.get("route") is not None:
                yield f"data: {json.dumps({'type': 'logistics_done', 'data': state['route'], 'progress': 90})}\n\n"
        except Exception:
            pass

        queue = pipeline_queues[plan_id]
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] in ("complete", "error", "profiler_clarification", "itinerary_options"):
                # Pause the stream here — VerifyPage will re-open it when the
                # user takes an action (refine or finalize).
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
