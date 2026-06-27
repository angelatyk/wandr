import asyncio
import logging
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai.types import Content, Part
from wandr.agents.orchestrator import orchestrator_agent

logging.basicConfig(level=logging.INFO)

async def main():
    app_name = "wandr"
    user_id = "test-user"
    session_id = "test-session"
    
    session_service = InMemorySessionService()
    runner = Runner(
        agent=orchestrator_agent,
        app_name=app_name,
        session_service=session_service
    )
    
    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )
    
    print(f"Initial state: {session.state}")
    print("\nStarting orchestrator execution run...\n")
    
    user_message = Content(
        role="user",
        parts=[Part(text="I want a 2-day historical trip to Tokyo.")]
    )
    
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message
    ):
        pass

    updated_session = await session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )
    
    print("\n--- Final Session State Keys & Values ---")
    for key, val in updated_session.state.items():
        print(f"\nState Key: {key}")
        print(f"Type: {type(val).__name__}")
        print(f"Value: {val}")

if __name__ == "__main__":
    asyncio.run(main())
