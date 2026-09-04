"""Unit tests for LedgerGuard Agent construction."""

from unittest.mock import MagicMock

from pydantic import SecretStr
from strands import Agent
from strands.models.model import Model

from app.agent.agent import create_ledgerguard_agent
from app.agent.prompts import LEDGERGUARD_SYSTEM_PROMPT
from app.config import Settings


def test_create_agent_with_explicit_model():
    """Verify Agent creation with an explicitly injected model."""
    mock_model = MagicMock(spec=Model)
    agent = create_ledgerguard_agent(model=mock_model)

    assert isinstance(agent, Agent)
    assert agent.name == "LedgerGuard"
    assert agent.model is mock_model
    assert agent.system_prompt == LEDGERGUARD_SYSTEM_PROMPT


def test_create_agent_with_custom_prompt():
    """Verify Agent creation with a custom system prompt."""
    mock_model = MagicMock(spec=Model)
    custom_prompt = "Custom verification prompt for test."
    agent = create_ledgerguard_agent(model=mock_model, system_prompt=custom_prompt)

    assert isinstance(agent, Agent)
    assert agent.system_prompt == custom_prompt


def test_create_agent_with_settings():
    """Verify Agent creation resolves model from settings."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=SecretStr("dummy-key"),
    )
    agent = create_ledgerguard_agent(settings=settings)

    assert isinstance(agent, Agent)
    assert agent.name == "LedgerGuard"
    assert agent.model is not None
