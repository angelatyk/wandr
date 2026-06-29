import asyncio
import json
import logging
import pprint

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai.types import Content, Part

from ai.agents.orchestrator import orchestrator_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    app_name = "wandr"
    user_id = "test-user"
    session_id = "test-session"

    session_service = InMemorySessionService()
    runner = Runner(
        agent=orchestrator_agent,
        app_name=app_name,
        session_service=session_service,
    )

    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    # Seed the first message from the user.
    user_input = (
        input("Wandr > ").strip() or "I have 2 hours to explore downtown toronto."
    )
    user_message = Content(role="user", parts=[Part(text=user_input)])

    # Multi-turn loop: keep running until the profiler has a complete persona
    # and the pipeline finishes. Each loop iteration is one conversation turn.
    while True:
        print()
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        ):
            if event.content and event.content.parts:
                text = event.content.parts[0].text or ""
                print(f"  [event] author={event.author!r:20s} | {text[:120]}")

        # Check whether the profiler completed and the pipeline ran to the end.
        current_session = await session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        if current_session.state.get("persona"):
            # Persona confirmed — pipeline ran to completion (or as far as it can).
            break

        # Profiler asked a clarifying question — prompt the user and loop back.
        print()
        user_input = input("Wandr > ").strip()
        if not user_input:
            continue
        user_message = Content(role="user", parts=[Part(text=user_input)])

    print("\n--- Final Session State ---")
    for key, val in current_session.state.items():
        print(f"\n[{key}]  ({type(val).__name__})")
        if isinstance(val, dict):
            print(json.dumps(val, indent=2, default=str))
        elif isinstance(val, list):
            pprint.pprint(val)
        else:
            pprint.pprint(val)


if __name__ == "__main__":
    asyncio.run(main())
