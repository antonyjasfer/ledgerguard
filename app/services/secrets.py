"""AWS Secrets Manager integration for LedgerGuard.

Safely retrieves application-level secrets (such as third-party model provider API keys).
Does NOT store or manage AWS credentials, which remain managed exclusively via the
standard AWS credential chain.
"""

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.services.interfaces import SecretProvider


class SecretsManagerProvider(SecretProvider):
    """Secret provider backed by AWS Secrets Manager."""

    def __init__(
        self,
        region_name: str | None = None,
        profile_name: str | None = None,
        sm_client: Any = None,
        settings: Settings | None = None,
    ):
        resolved_settings = settings or get_settings()
        self.region_name = region_name or resolved_settings.AWS_REGION
        self.profile_name = profile_name if profile_name is not None else resolved_settings.AWS_PROFILE

        if sm_client is not None:
            self._client = sm_client
        else:
            session_kwargs: dict[str, Any] = {"region_name": self.region_name}
            if self.profile_name:
                session_kwargs["profile_name"] = self.profile_name
            session = boto3.Session(**session_kwargs)
            self._client = session.client("secretsmanager")

    def get_secret(self, secret_name: str) -> str:
        """Retrieve secret string from Secrets Manager without exposing it in logs."""
        try:
            response = self._client.get_secret_value(SecretId=secret_name)
            if "SecretString" in response:
                secret_str = response["SecretString"]
                # If secret is stored as JSON with an api_key field, extract it
                try:
                    parsed = json.loads(secret_str)
                    if isinstance(parsed, dict) and "api_key" in parsed:
                        return str(parsed["api_key"])
                except (json.JSONDecodeError, TypeError):
                    pass
                return secret_str
            raise ValueError(f"Secret '{secret_name}' does not contain a valid SecretString.")
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("ResourceNotFoundException", "NoSuchSecret"):
                raise KeyError(f"Secret '{secret_name}' was not found in Secrets Manager.") from exc
            raise

    def get_openrouter_api_key(self, settings: Settings | None = None) -> str | None:
        """Provider-aware OpenRouter key retrieval.

        Only queries Secrets Manager if the active model provider is 'openrouter'.
        Never issues a network request if using Bedrock Mantle or traditional Bedrock.
        """
        resolved_settings = settings or get_settings()
        provider = resolved_settings.LEDGERGUARD_MODEL_PROVIDER

        if provider != "openrouter":
            return None

        # Check if already present in environment settings
        if resolved_settings.OPENROUTER_API_KEY:
            return resolved_settings.OPENROUTER_API_KEY.get_secret_value()

        secret_name = resolved_settings.OPENROUTER_SECRET_NAME
        return self.get_secret(secret_name)
