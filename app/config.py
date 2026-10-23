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

    # Provider selection: 'bedrock_mantle' (primary development),
    # 'openrouter' (explicit alternative), or 'bedrock_runtime' (traditional Bedrock Runtime).
    # 'bedrock' is maintained as a legacy alias for 'bedrock_runtime'.
    LEDGERGUARD_MODEL_PROVIDER: Literal[
        "bedrock_mantle", "openrouter", "bedrock_runtime", "bedrock"
    ] = Field(
        default="bedrock_mantle",
        description="Active model provider for LedgerGuard agent.",
    )

    # Bedrock Mantle settings (primary development provider)
    BEDROCK_MANTLE_MODEL_ID: str = Field(
        default="google.gemma-3-27b-it",
        description="Model identifier for Amazon Bedrock Mantle.",
    )

    # OpenRouter settings (explicit alternative development provider)
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

    # AWS settings (shared & traditional Bedrock Runtime provider)
    AWS_REGION: str = Field(
        default="us-east-1",
        description="AWS Region for Amazon Bedrock services.",
    )
    AWS_PROFILE: str | None = Field(
        default=None,
        description="AWS credential profile name for local development.",
    )
    BEDROCK_MODEL_ID: str = Field(
        default="amazon.nova-lite-v1:0",
        description="Model identifier for Amazon Bedrock Runtime.",
    )
    BEDROCK_PROFILE_NAME: str | None = Field(
        default=None,
        description="AWS credential profile name for Bedrock runtime.",
    )

    # Phase 9: Enterprise Scale & Concurrency Controls
    MAX_WORKER_CONCURRENCY: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Maximum concurrent worker tasks",
    )
    MAX_EXTRACTION_CONCURRENCY: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Maximum concurrent extraction/OCR operations",
    )
    MAX_GEMMA_CONCURRENCY: int = Field(
        default=3,
        ge=1,
        le=16,
        description="Maximum concurrent Bedrock Mantle / Gemma operations",
    )
    BATCH_PREFETCH_SIZE: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum SQS messages to prefetch per polling cycle",
    )

    # Phase 4 AWS Data Layer settings
    LEDGERGUARD_S3_BUCKET: str | None = Field(
        default=None,
        description="S3 bucket name for invoice document storage.",
    )
    LEDGERGUARD_DYNAMODB_TABLE: str = Field(
        default="ledgerguard-invoices",
        description="DynamoDB table name for invoice records and audit trail.",
    )
    LEDGERGUARD_SQS_QUEUE_URL: str | None = Field(
        default=None,
        description="SQS queue URL for background invoice processing jobs.",
    )
    OPENROUTER_SECRET_NAME: str = Field(
        default="ledgerguard/openrouter-key",
        description="AWS Secrets Manager secret name for OpenRouter API key.",
    )
    SQS_VISIBILITY_TIMEOUT: int = Field(
        default=300,
        ge=1,
        le=43200,
        description="SQS message visibility timeout in seconds.",
    )
    SQS_MAX_ATTEMPTS: int = Field(
        default=3,
        ge=1,
        description="Maximum processing attempts before marking job as failed.",
    )
    LEDGERGUARD_STORAGE_MODE: Literal["aws", "local"] = Field(
        default="aws",
        description="Storage execution mode: 'aws' or 'local'.",
    )

    # Phase 5 API & Document settings
    LEDGERGUARD_API_KEY: SecretStr | None = Field(
        default=None,
        description="API key for securing LedgerGuard REST API endpoints.",
    )
    MAX_DOCUMENT_SIZE_BYTES: int = Field(
        default=10 * 1024 * 1024,
        description="Maximum allowed document upload size in bytes (default: 10MB).",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance loaded from environment / .env file."""
    return Settings()
