"""Configuration management for LedgerGuard."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Type-safe application settings for LedgerGuard."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider selection: 'openrouter' (development) or 'bedrock' (AWS production)
    LEDGERGUARD_MODEL_PROVIDER: Literal["openrouter", "bedrock"] = Field(
        default="openrouter",
        description="Active model provider for LedgerGuard agent.",
    )

    # OpenRouter settings (development provider)
    OPENROUTER_API_KEY: SecretStr | None = Field(
        default=None,
        description="API key for OpenRouter service.",
    )
    OPENROUTER_MODEL_ID: str = Field(
        default="openai/gpt-4o-mini",
        description="Model identifier to use on OpenRouter.",
    )
    OPENROUTER_BASE_URL: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenRouter API.",
    )

    # AWS Bedrock settings (future AWS production provider)
    AWS_REGION: str = Field(
        default="us-east-1",
        description="AWS Region for Amazon Bedrock runtime.",
    )
    BEDROCK_MODEL_ID: str = Field(
        default="amazon.nova-lite-v1:0",
        description="Model identifier for Amazon Bedrock.",
    )
    BEDROCK_PROFILE_NAME: str | None = Field(
        default="ledgerguard",
        description="AWS credential profile name for local development.",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance loaded from environment / .env file."""
    return Settings()
