"""Unit tests for LedgerGuard model provider abstraction."""

import pytest
from pydantic import SecretStr
from strands.models.bedrock import BedrockModel
from strands.models.openai import OpenAIModel

from app.agent.model_factory import (
    BedrockProvider,
    OpenRouterProvider,
    get_model,
    get_model_provider,
)
from app.config import Settings


def test_openrouter_provider_missing_key():
    """Verify that OpenRouterProvider raises ValueError when API key is missing."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=None,
    )
    provider = OpenRouterProvider(settings)
    with pytest.raises(ValueError) as exc_info:
        provider.get_model()
    assert "OPENROUTER_API_KEY is not configured" in str(exc_info.value)


def test_openrouter_provider_empty_key():
    """Verify that OpenRouterProvider raises ValueError when API key is empty whitespace."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=SecretStr("   "),
    )
    provider = OpenRouterProvider(settings)
    with pytest.raises(ValueError) as exc_info:
        provider.get_model()
    assert "OPENROUTER_API_KEY is not configured" in str(exc_info.value)


def test_openrouter_provider_construction():
    """Verify that OpenRouterProvider correctly constructs an OpenAIModel instance."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=SecretStr("sk-dummy-test-key"),
        OPENROUTER_MODEL_ID="openai/gpt-4o-mini",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
    )
    provider = OpenRouterProvider(settings)
    model = provider.get_model()
    assert isinstance(model, OpenAIModel)
    assert model.config.get("model_id") == "openai/gpt-4o-mini"


def test_bedrock_provider_construction():
    """Verify that BedrockProvider constructs a BedrockModel without network access."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="bedrock",
        AWS_REGION="us-east-1",
        BEDROCK_MODEL_ID="amazon.nova-lite-v1:0",
        BEDROCK_PROFILE_NAME="ledgerguard",
    )
    provider = BedrockProvider(settings)
    model = provider.get_model()
    assert isinstance(model, BedrockModel)
    assert model.config.get("model_id") == "amazon.nova-lite-v1:0"


def test_get_model_provider_selection():
    """Verify provider factory selects correct provider class based on settings."""
    s_openrouter = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=SecretStr("dummy"),
    )
    p_openrouter = get_model_provider(s_openrouter)
    assert isinstance(p_openrouter, OpenRouterProvider)

    s_bedrock = Settings(
        LEDGERGUARD_MODEL_PROVIDER="bedrock",
        BEDROCK_PROFILE_NAME="ledgerguard",
    )
    p_bedrock = get_model_provider(s_bedrock)
    assert isinstance(p_bedrock, BedrockProvider)


def test_get_model_convenience_function():
    """Verify get_model constructs the configured model."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=SecretStr("dummy"),
    )
    model = get_model(settings)
    assert isinstance(model, OpenAIModel)
