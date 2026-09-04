"""Real model smoke test for LedgerGuard Phase 1 using Strands and OpenRouter."""

import os
import sys

# Ensure the project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.agent import create_ledgerguard_agent
from app.config import get_settings


def run_smoke_test() -> int:
    """Execute the Phase 1 live model smoke test via OpenRouter."""
    settings = get_settings()

    # Step 1: Verify Provider Configuration
    if settings.LEDGERGUARD_MODEL_PROVIDER != "openrouter":
        print(f"Configured provider is '{settings.LEDGERGUARD_MODEL_PROVIDER}', not 'openrouter'.")
        print("Smoke test requires LEDGERGUARD_MODEL_PROVIDER=openrouter.")
        return 1

    # Step 2: Verify API Key Existence
    api_key = settings.OPENROUTER_API_KEY
    if api_key is None or not api_key.get_secret_value().strip():
        print("OPENROUTER_API_KEY is not configured. Smoke test cannot run.")
        return 1

    # Step 3: Initialize Strands Agent with OpenRouter Model
    try:
        agent = create_ledgerguard_agent(settings=settings)
    except Exception as exc:
        print(f"Failed to initialize LedgerGuard agent: {exc}")
        return 1

    # Step 4: Send Single Verification Prompt
    prompt = "Respond with exactly:\nLedgerGuard Phase 1 agent verification passed."
    try:
        result = agent(prompt)
    except Exception as exc:
        print(f"Model invocation failed: {exc}")
        return 1

    # Step 5: Extract and Validate Response
    raw_response = str(result).strip()
    if not raw_response:
        print("Model invocation returned an empty response.")
        return 1

    # Step 6: Print Official Phase 1 Verification Output
    print("================================")
    print("LEDGERGUARD PHASE 1 SMOKE TEST")
    print("================================")
    print("Provider: OpenRouter")
    print("Strands: PASS")
    print("Model invocation: PASS")
    print("Real response: PASS")
    print("")
    print("Response:")
    print(raw_response)
    print("")
    print("================================")
    print("PHASE 1 FOUNDATION: PASS")
    print("================================")

    return 0


if __name__ == "__main__":
    sys.exit(run_smoke_test())
