"""Unit tests for LedgerGuard configuration system."""

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings


def test_default_settings():
    """Verify default settings values for local development."""
    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=None,
    )
    assert settings.LEDGERGUARD_MODEL_PROVIDER == "openrouter"
    assert settings.OPENROUTER_MODEL_ID == "openai/gpt-4o-mini"
    assert settings.OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"
    assert settings.AWS_REGION == "us-east-1"
    assert settings.BEDROCK_MODEL_ID == "amazon.nova-lite-v1:0"
    assert settings.BEDROCK_PROFILE_NAME == "ledgerguard"


def test_provider_validation():
    """Verify that invalid provider names raise validation errors."""
    with pytest.raises(ValidationError):
        Settings(LEDGERGUARD_MODEL_PROVIDER="invalid_provider")  # type: ignore


def test_secret_masking():
    """Verify that sensitive API keys are never exposed in string representations."""
    raw_secret = "sk-or-v1-supersecretkey999"
    settings = Settings(
        OPENROUTER_API_KEY=SecretStr(raw_secret),
    )
    assert raw_secret not in str(settings.OPENROUTER_API_KEY)
    assert raw_secret not in repr(settings.OPENROUTER_API_KEY)
    assert raw_secret not in repr(settings)
    assert settings.OPENROUTER_API_KEY.get_secret_value() == raw_secret
