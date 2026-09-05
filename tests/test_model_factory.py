"""Unit tests for LedgerGuard model provider abstraction."""

import pytest
from pydantic import SecretStr
from strands.models.bedrock import BedrockModel
from strands.models.openai import OpenAIModel

from app.agent.model_factory import (
    BedrockMantleProvider,
    BedrockProvider,
    BedrockRuntimeProvider,
    OpenRouterProvider,
    get_model,
    get_model_provider,
)
from app.config import Settings


def test_bedrock_mantle_provider_construction():
    """Verify BedrockMantleProvider constructs OpenAIModel without network calls."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="bedrock_mantle",
        BEDROCK_MANTLE_MODEL_ID="google.gemma-3-27b-it",
        AWS_REGION="us-east-1",
        AWS_PROFILE="ledgerguard",
    )
    provider = BedrockMantleProvider(settings)
    model = provider.get_model()

    assert isinstance(model, OpenAIModel)
    assert model.config.get("model_id") == "google.gemma-3-27b-it"
    assert getattr(model, "_bedrock_mantle_config", {}).get("region") == "us-east-1"


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


def test_bedrock_runtime_provider_construction():
    """Verify BedrockRuntimeProvider constructs a BedrockModel without network access."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="bedrock_runtime",
        AWS_REGION="us-east-1",
        BEDROCK_MODEL_ID="amazon.nova-lite-v1:0",
        BEDROCK_PROFILE_NAME="ledgerguard",
    )
    provider = BedrockRuntimeProvider(settings)
    model = provider.get_model()
    assert isinstance(model, BedrockModel)
    assert model.config.get("model_id") == "amazon.nova-lite-v1:0"


def test_bedrock_provider_alias():
    """Verify BedrockProvider is an exact alias for BedrockRuntimeProvider."""
    assert BedrockProvider is BedrockRuntimeProvider


def test_get_model_provider_selection():
    """Verify provider factory selects correct provider class based on settings."""
    s_mantle = Settings(LEDGERGUARD_MODEL_PROVIDER="bedrock_mantle")
    p_mantle = get_model_provider(s_mantle)
    assert isinstance(p_mantle, BedrockMantleProvider)

    s_openrouter = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=SecretStr("dummy"),
    )
    p_openrouter = get_model_provider(s_openrouter)
    assert isinstance(p_openrouter, OpenRouterProvider)

    s_runtime = Settings(LEDGERGUARD_MODEL_PROVIDER="bedrock_runtime")
    p_runtime = get_model_provider(s_runtime)
    assert isinstance(p_runtime, BedrockRuntimeProvider)

    s_legacy = Settings(LEDGERGUARD_MODEL_PROVIDER="bedrock")
    p_legacy = get_model_provider(s_legacy)
    assert isinstance(p_legacy, BedrockRuntimeProvider)


def test_get_model_provider_invalid():
    """Verify unsupported provider raises ValueError without fallback."""
    settings = Settings()
    object.__setattr__(settings, "LEDGERGUARD_MODEL_PROVIDER", "nonexistent_provider")
    with pytest.raises(ValueError) as exc_info:
        get_model_provider(settings)
    assert "Unsupported model provider" in str(exc_info.value)


def test_get_model_convenience_function():
    """Verify get_model constructs the configured Bedrock Mantle model."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="bedrock_mantle",
        BEDROCK_MANTLE_MODEL_ID="google.gemma-3-27b-it",
    )
    model = get_model(settings)
    assert isinstance(model, OpenAIModel)
    assert model.config.get("model_id") == "google.gemma-3-27b-it"
