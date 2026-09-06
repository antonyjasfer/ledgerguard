"""Opt-in live Secrets Manager integration test for LedgerGuard.

Requires LEDGERGUARD_RUN_AWS_INTEGRATION=true.
"""

import os
import pytest

from app.config import get_settings
from app.services.secrets import SecretsManagerProvider


@pytest.mark.integration
def test_secrets_manager_live():
    settings = get_settings()
    provider = SecretsManagerProvider(settings=settings)

    # In dev without OpenRouter, bedrock_mantle should not query secrets manager
    key = provider.get_openrouter_api_key(settings=settings)
    assert key is None
