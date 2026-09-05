"""Agent creation and configuration for LedgerGuard.

Provides factory functions for creating configured Strands Agents with
deterministic verification tools and the decision guard safety layer.
"""

from strands import Agent
from strands.models.model import Model

from app.agent.model_factory import get_model
from app.agent.prompts import LEDGERGUARD_SYSTEM_PROMPT
from app.agent.tools import LEDGERGUARD_TOOLS
from app.config import Settings


def create_ledgerguard_agent(
    model: Model | None = None,
    settings: Settings | None = None,
    system_prompt: str | None = None,
    include_tools: bool = True,
) -> Agent:
    """Create and return a configured LedgerGuard Strands Agent.

    Args:
        model: Optional pre-configured Strands Model instance. If not provided,
            the model will be resolved using get_model(settings).
        settings: Optional application settings to resolve the model.
        system_prompt: Optional custom system prompt. Defaults to LEDGERGUARD_SYSTEM_PROMPT.
        include_tools: Whether to register the 5 deterministic verification tools.
            Defaults to True. Set False for simple reasoning-only mode.

    Returns:
        A configured Strands Agent instance with verification tools registered.
    """
    resolved_model = model if model is not None else get_model(settings=settings)
    prompt = system_prompt if system_prompt is not None else LEDGERGUARD_SYSTEM_PROMPT
    tools = list(LEDGERGUARD_TOOLS) if include_tools else []

    return Agent(
        model=resolved_model,
        system_prompt=prompt,
        tools=tools,
        name="LedgerGuard",
        description="Accounts-payable invoice verification agent",
    )
