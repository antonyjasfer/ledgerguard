"""Unit tests for Secrets Manager integration."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from pydantic import SecretStr

from app.config import Settings
from app.services.secrets import SecretsManagerProvider


def test_get_secret_plain_string():
    """Retrieves plain text secret value."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": "my-plain-secret-value"
    }
    provider = SecretsManagerProvider(sm_client=mock_client)

    val = provider.get_secret("test/secret")
    assert val == "my-plain-secret-value"
    mock_client.get_secret_value.assert_called_once_with(SecretId="test/secret")


def test_get_secret_json_string():
    """Extracts api_key field from JSON formatted secret strings."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"api_key": "sk-or-v1-secret-token"}'
    }
    provider = SecretsManagerProvider(sm_client=mock_client)

    val = provider.get_secret("test/json_secret")
    assert val == "sk-or-v1-secret-token"


def test_get_secret_not_found_raises_key_error():
    """ResourceNotFoundException raises KeyError."""
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}}
    mock_client.get_secret_value.side_effect = ClientError(error_response, "GetSecretValue")

    provider = SecretsManagerProvider(sm_client=mock_client)
    with pytest.raises(KeyError, match="not found in Secrets Manager"):
        provider.get_secret("nonexistent/secret")


def test_get_openrouter_api_key_when_provider_is_bedrock_mantle():
    """Does NOT call Secrets Manager when primary provider is bedrock_mantle."""
    mock_client = MagicMock()
    provider = SecretsManagerProvider(sm_client=mock_client)

    settings = Settings(LEDGERGUARD_MODEL_PROVIDER="bedrock_mantle")
    val = provider.get_openrouter_api_key(settings=settings)

    assert val is None
    mock_client.get_secret_value.assert_not_called()


def test_get_openrouter_api_key_when_provider_is_openrouter():
    """Queries Secrets Manager when provider is explicitly openrouter."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": "sk-or-v1-fetched-from-sm"
    }
    provider = SecretsManagerProvider(sm_client=mock_client)

    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_SECRET_NAME="custom/openrouter_key",
        OPENROUTER_API_KEY=None,
    )
    val = provider.get_openrouter_api_key(settings=settings)

    assert val == "sk-or-v1-fetched-from-sm"
    mock_client.get_secret_value.assert_called_once_with(SecretId="custom/openrouter_key")


def test_get_openrouter_api_key_when_already_in_settings():
    """Prefers existing environment setting over querying Secrets Manager."""
    mock_client = MagicMock()
    provider = SecretsManagerProvider(sm_client=mock_client)

    settings = Settings(
        LEDGERGUARD_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY=SecretStr("sk-or-v1-local-env-key"),
    )
    val = provider.get_openrouter_api_key(settings=settings)

    assert val == "sk-or-v1-local-env-key"
    mock_client.get_secret_value.assert_not_called()
