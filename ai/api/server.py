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
from ai.models.api import TripRequest
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
    try:
        # app_name must match the directory ADK infers from the agent file path ("agents")
        runner = Runner(
            agent=orchestrator_agent,
            app_name="agents",
            session_service=session_service,
        )
        
        # get_session() returns None if the session doesn't exist — it does not raise.
        # Always create the session before passing it to the runner.
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
            
        initial_text = "\n".join(parts) if parts else "Help me plan a trip."
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
                if "persona" in state:
                    if "profiler_done" not in emitted_phases:
                        progress = 30
                        await queue.put(PipelineEvent(
                            type="profiler_done", 
                            data=state["persona"],
                            progress=progress
                        ).model_dump())
                        emitted_phases.add("profiler_done")
                else:
                    # Clarifying question
                    progress = 20
                    await queue.put(PipelineEvent(
                        type="profiler_clarification",
                        data={"message": text},
                        progress=progress
                    ).model_dump())
                    return # Stop here to wait for user reply
                    
            elif author == "itinerary":
                if "itinerary" in state:
                    if "itinerary_done" not in emitted_phases:
                        progress = 50
                        await queue.put(PipelineEvent(
                            type="itinerary_done",
                            data=state["itinerary"],
                            progress=progress
                        ).model_dump())
                        emitted_phases.add("itinerary_done")
                    
            elif author == "orchestrator":
                if "audio_scripts" in state and "scripts" in state["audio_scripts"]:
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
                if "route" in state:
                    if "logistics_done" not in emitted_phases:
                        progress = 90
                        await queue.put(PipelineEvent(
                            type="logistics_done",
                            data=state["route"],
                            progress=progress
                        ).model_dump())
                        emitted_phases.add("logistics_done")

        # Complete
        progress = 100
        current_session = await session_service.get_session(app_name="agents", user_id="user", session_id=plan_id)
        await queue.put(PipelineEvent(
            type="complete",
            data=current_session.state,
            progress=progress
        ).model_dump())

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
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
    # If the user replies to a clarification question
    if plan_id not in pipeline_queues:
        pipeline_queues[plan_id] = asyncio.Queue()
    queue = pipeline_queues[plan_id]
    asyncio.create_task(run_pipeline(plan_id, request, queue))
    return {"plan_id": plan_id}

@app.get("/api/plan/{plan_id}/stream")
async def stream_plan(plan_id: str):
    async def event_generator():
        if plan_id not in pipeline_queues:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Plan not found'}, 'progress': 100})}\n\n"
            return
            
        # Yield a snapshot of current state so reconnecting clients get up to speed
        try:
            current_session = await session_service.get_session(app_name="agents", user_id="user", session_id=plan_id)
            state = current_session.state
            
            if "persona" in state:
                yield f"data: {json.dumps({'type': 'profiler_done', 'data': state['persona'], 'progress': 30})}\n\n"
            if "itinerary" in state:
                yield f"data: {json.dumps({'type': 'itinerary_done', 'data': state['itinerary'], 'progress': 50})}\n\n"
            if "audio_scripts" in state and "scripts" in state["audio_scripts"]:
                for script in state["audio_scripts"]["scripts"]:
                    yield f"data: {json.dumps({'type': 'stop_done', 'data': script, 'progress': 80})}\n\n"
            if "route" in state:
                yield f"data: {json.dumps({'type': 'logistics_done', 'data': state['route'], 'progress': 90})}\n\n"
        except Exception:
            pass
            
        queue = pipeline_queues[plan_id]
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] in ("complete", "error", "profiler_clarification"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
