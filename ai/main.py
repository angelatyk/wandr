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

    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    print(f"Initial state: {session.state}")
    print("\nStarting orchestrator execution run...\n")

    user_message = Content(
        role="user",
        parts=[Part(text="I want a 2-day historical trip to Tokyo.")],
    )

    # Log each event as it arrives so the agent pipeline sequence is visible
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    ):
        if event.content and event.content.parts:
            text = event.content.parts[0].text or ""
            print(f"  [event] author={event.author!r:20s} | {text[:120]}")

    updated_session = await session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    print("\n--- Final Session State ---")
    for key, val in updated_session.state.items():
        print(f"\n[{key}]  ({type(val).__name__})")
        if isinstance(val, dict):
            print(json.dumps(val, indent=2, default=str))
        elif isinstance(val, list):
            pprint.pprint(val)
        else:
            pprint.pprint(val)


if __name__ == "__main__":
    asyncio.run(main())
