"""Model provider abstraction and factory for LedgerGuard."""

from abc import ABC, abstractmethod
import os
from typing import Any

import boto3
from strands.models.bedrock import BedrockModel
from strands.models.model import Model
from strands.models.openai import OpenAIModel

from app.config import Settings, get_settings


class ModelProvider(ABC):
    """Abstract base class for LedgerGuard model providers."""

    @abstractmethod
    def get_model(self) -> Model:
        """Construct and return a configured Strands Model instance."""
        pass


class BedrockMantleProvider(ModelProvider):
    """Amazon Bedrock Mantle model provider for primary development.

    Uses Strands OpenAIModel connected to Amazon Bedrock Mantle
    via bedrock_mantle_config and AWS IAM credentials.
    Zero network calls are executed during initialization.
    """

    def __init__(self, settings: Settings, session: boto3.Session | None = None) -> None:
        self.settings = settings
        self._session = session

    def get_model(self) -> Model:
        """Instantiate an OpenAIModel configured for Bedrock Mantle."""
        profile = self.settings.AWS_PROFILE or self.settings.BEDROCK_PROFILE_NAME
        if profile and not os.environ.get("AWS_PROFILE"):
            os.environ["AWS_PROFILE"] = profile

        session = self._session
        if session is None and profile:
            session = boto3.Session(
                profile_name=profile,
                region_name=self.settings.AWS_REGION,
            )

        mantle_config: dict[str, Any] = {
            "region": self.settings.AWS_REGION,
        }
        if session is not None:
            mantle_config["boto_session"] = session

        return OpenAIModel(
            model_id=self.settings.BEDROCK_MANTLE_MODEL_ID,
            bedrock_mantle_config=mantle_config,
        )


class OpenRouterProvider(ModelProvider):
    """OpenRouter model provider for explicit development alternative."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_model(self) -> Model:
        """Instantiate an OpenAIModel pointing to the OpenRouter endpoint.

        Raises:
            ValueError: If OPENROUTER_API_KEY is not set or empty.
        """
        api_key = self.settings.OPENROUTER_API_KEY
        if api_key is None or not api_key.get_secret_value().strip():
            raise ValueError(
                "OPENROUTER_API_KEY is not configured. "
                "Set OPENROUTER_API_KEY in .env or environment to use the OpenRouter provider."
            )

        return OpenAIModel(
            model_id=self.settings.OPENROUTER_MODEL_ID,
            client_args={
                "base_url": self.settings.OPENROUTER_BASE_URL,
                "api_key": api_key.get_secret_value(),
            },
        )


class BedrockRuntimeProvider(ModelProvider):
    """Amazon Bedrock Runtime model provider for AWS production environments.

    Constructs a BedrockModel instance without executing network requests or live inference.
    """

    def __init__(self, settings: Settings, session: boto3.Session | None = None) -> None:
        self.settings = settings
        self._session = session

    def get_model(self) -> Model:
        """Instantiate a BedrockModel using configured AWS parameters."""
        session = self._session
        profile = self.settings.BEDROCK_PROFILE_NAME or self.settings.AWS_PROFILE
        if session is None:
            if profile:
                session = boto3.Session(
                    profile_name=profile,
                    region_name=self.settings.AWS_REGION,
                )
            else:
                session = boto3.Session(region_name=self.settings.AWS_REGION)

        return BedrockModel(
            boto_session=session,
            model_id=self.settings.BEDROCK_MODEL_ID,
        )


# Backward-compatibility alias for legacy code
BedrockProvider = BedrockRuntimeProvider


def get_model_provider(
    settings: Settings | None = None,
    boto_session: boto3.Session | None = None,
) -> ModelProvider:
    """Resolve and return the appropriate ModelProvider based on settings.

    Args:
        settings: Application settings. Defaults to cached get_settings().
        boto_session: Optional pre-configured boto3.Session for AWS providers.

    Returns:
        Configured ModelProvider instance.

    Raises:
        ValueError: If LEDGERGUARD_MODEL_PROVIDER is not recognized.
    """
    resolved_settings = settings or get_settings()
    provider_name = resolved_settings.LEDGERGUARD_MODEL_PROVIDER

    if provider_name == "bedrock_mantle":
        return BedrockMantleProvider(resolved_settings, session=boto_session)
    elif provider_name == "openrouter":
        return OpenRouterProvider(resolved_settings)
    elif provider_name in ("bedrock_runtime", "bedrock"):
        return BedrockRuntimeProvider(resolved_settings, session=boto_session)
    else:
        raise ValueError(
            f"Unsupported model provider: '{provider_name}'. "
            "Supported providers are 'bedrock_mantle', 'openrouter', and 'bedrock_runtime'."
        )


def get_model(
    settings: Settings | None = None,
    boto_session: boto3.Session | None = None,
) -> Model:
    """Convenience helper to obtain the configured Strands Model instance."""
    provider = get_model_provider(settings=settings, boto_session=boto_session)
    return provider.get_model()
