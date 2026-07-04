"""ADK web entrypoint for the Wandr agent app."""

from ai.agents.orchestrator import orchestrator_agent

# ADK web looks for `root_agent` under `agents.agent` first.
root_agent = orchestrator_agent
