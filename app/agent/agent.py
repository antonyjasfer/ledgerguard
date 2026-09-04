"""Agent creation and configuration for LedgerGuard."""

from strands import Agent
from strands.models.model import Model

from app.agent.model_factory import get_model
from app.agent.prompts import LEDGERGUARD_SYSTEM_PROMPT
from app.config import Settings


def create_ledgerguard_agent(
    model: Model | None = None,
    settings: Settings | None = None,
    system_prompt: str | None = None,
) -> Agent:
    """Create and return a configured LedgerGuard Strands Agent.

    Args:
        model: Optional pre-configured Strands Model instance. If not provided,
            the model will be resolved using get_model(settings).
        settings: Optional application settings to resolve the model.
        system_prompt: Optional custom system prompt. Defaults to LEDGERGUARD_SYSTEM_PROMPT.

    Returns:
        A configured Strands Agent instance.
    """
    resolved_model = model if model is not None else get_model(settings=settings)
    prompt = system_prompt if system_prompt is not None else LEDGERGUARD_SYSTEM_PROMPT

    return Agent(
        model=resolved_model,
        system_prompt=prompt,
        name="LedgerGuard",
        description="Accounts-payable invoice verification agent",
    )
