import json
import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import Client, types
from pydantic import ValidationError

from ai.models.persona import PersonaModel
from ai.config.settings import settings

logger = logging.getLogger(__name__)

PROFILER_SYSTEM_PROMPT = """\
You are the Profiler for Wandr, an AI travel guide. Your job is to collect the
minimum information needed to plan a personalised trip and classify the user's
travel persona from the conversation so far.

## Required fields
You MUST have both of these before producing a persona:
- destination — where the user wants to go (city, region, or country)
- duration — how long the trip or outing will last (e.g. "2 days", "3 hours", "a weekend")

## Optional fields
- current_location — if the user mentions they are already at a specific location
  or landmark (e.g. "under the CN tower", "at the airport"), capture it here.

## Location Rules & Clarifications
- If the user provides a current_location but NO explicit destination, infer the
  destination to be the city/area of the current location (e.g., "I'm under the CN tower" -> destination = "Toronto").
- If the user provides a short duration (e.g. "2 hours") for a destination that is
  physically far from their current_location (e.g. "I'm in Toronto, want to explore Tokyo in 2 hours"),
  this is impossible. Ask a clarifying question about this.
- However, if they are planning a future trip with a reasonable duration (e.g., "I'm in Toronto, want to explore Tokyo for 3 days"), that is perfectly fine.

## If either required field is missing or conflicts exist
Ask the single most important missing question or point out the impossibility.
Be short and friendly.
Examples:
  "Where are you heading?"
  "How much time do you have to explore?"
  "You're in Toronto but want to explore Tokyo in 2 hours — are you planning a future trip?"
Do NOT output JSON. Output the question only — nothing else.

## If you have both required fields
Determine the following and output ONLY a raw JSON object (no markdown fences,
no commentary, nothing else before or after the braces):

{
  "destination": "<city or region>",
  "duration": "<e.g. 2 hours, 3 days>",
  "current_location": "<specific landmark/location or null>",
  "type": "<one of: foodie | artist | historian | adventurer | local-life>",
  "pace": "<one of: relaxed | moderate | packed>",
  "budget": "<one of: budget | mid | luxury>",
  "notes": "<any special requests, interests, dietary needs, must-sees, etc. — empty string if none>"
}

Rules for each field:
- type: if the user explicitly says "I'm a foodie" etc., use that directly.
  Otherwise infer from language clues. Default to "adventurer" if ambiguous.
- pace: infer from "take it easy", "see as much as possible", etc. Default "moderate".
- budget: infer from "backpacking", "boutique", "Michelin", etc. Default "mid".
- notes: preserve the user's own wording. Use "" if nothing extra was mentioned.
"""

_client = Client()


class ProfilerAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        logger.debug("ProfilerAgent building conversation history from session events")

        # Reconstruct the conversation history so the model sees the full context
        # across multiple turns, not just the latest message.
        history: list[types.Content] = []
        for event in ctx.session.events:
            if event.content and event.content.parts and event.content.role in ("user", "model"):
                history.append(event.content)

        if not history:
            logger.warning("Profiler received an empty conversation history")
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Hi! Where would you like to travel, and for how many days?")],
                ),
            )
            return

        response = await _client.aio.models.generate_content(
            model=settings.model_name,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=PROFILER_SYSTEM_PROMPT,
            ),
        )

        raw = (response.text or "").strip()
        logger.debug("Profiler raw LLM output: %s", raw)

        # Try to interpret the response as a PersonaModel JSON.
        persona: PersonaModel | None = None
        if raw.startswith("{"):
            try:
                persona = PersonaModel.model_validate_json(raw)
            except (ValidationError, ValueError) as exc:
                logger.warning("Profiler output looked like JSON but failed validation: %s", exc)

        if persona is not None:
            # We have a valid persona — write it to state and let the pipeline continue.
            yield Event(
                author=self.name,
                actions=EventActions(state_delta={"persona": persona.model_dump()}),
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=raw)],
                ),
            )
        else:
            # The model asked a clarifying question — surface it to the user.
            # Nothing is written to state, so the orchestrator knows to pause.
            logger.info("Profiler is asking a clarifying question: %s", raw)
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=raw)],
                ),
            )


profiler_agent = ProfilerAgent(name="profiler")
