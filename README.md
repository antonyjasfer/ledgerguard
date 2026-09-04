# LedgerGuard

LedgerGuard is an autonomous Accounts Payable (AP) invoice verification agent built with the **Strands Agents SDK**.

Core concept:
> "Let AI handle high-volume, repetitive invoice verification in the background, alerting humans only when genuine judgement is required."

## Architecture

LedgerGuard decouples the core verification agent from the underlying LLM provider through a Model Provider Abstraction layer:

```text
               +-----------------------+
               |   LedgerGuard Agent   |
               |     (Strands SDK)     |
               +-----------------------+
                           |
                           v
               +-----------------------+
               |     Model Factory     |
               +-----------------------+
                           |
                           v
               +-----------------------+
               |  Provider Abstraction |
               +-----------------------+
                    /             \
                   v               v
        +-------------------+    +--------------------+
        |    OpenRouter     |    |   Amazon Bedrock   |
        |   (Development)   |    |  (Future AWS Prod) |
        +-------------------+    +--------------------+
```

- **LedgerGuard Agent**: Accounts-payable verification agent using Strands.
- **Model Factory**: Resolves the model provider from configuration without modifying agent code.
- **OpenRouterProvider**: OpenAI-compatible adapter for OpenRouter during development.
- **BedrockProvider**: Native Amazon Bedrock provider prepared for AWS production deployment.

## AWS Bedrock Status

> [!NOTE]
> Amazon Bedrock integration is structurally implemented and prepared in the provider abstraction. However, the current AWS account is awaiting AWS Support resolution for Bedrock Runtime access (`authorizationStatus = NOT_AUTHORIZED`, Support Case 178842133900178).
>
> During Phase 1, Bedrock provider construction executes zero network calls and zero model inference. OpenRouter serves as the active verified development provider.

## Local Development Setup

### Prerequisites
- Python 3.11+
- Virtual environment (`.venv`)

### Setup Instructions

1. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Configure environment variables:
   Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
   Edit `.env` to supply your configuration:
   ```env
   LEDGERGUARD_MODEL_PROVIDER=openrouter
   OPENROUTER_API_KEY=<your-key>
   OPENROUTER_MODEL_ID=openai/gpt-4o-mini
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   AWS_REGION=us-east-1
   BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
   BEDROCK_PROFILE_NAME=ledgerguard
   ```

3. Run Unit Tests:
   Unit tests do not require an active API key or external network access:
   ```powershell
   pytest tests -v
   ```

## Run Smoke Test

The real-model smoke test verifies end-to-end integration across Strands, the provider abstraction, and the live model:

```powershell
python scripts/smoke_test.py
```

Expected output on successful verification:
```text
================================
LEDGERGUARD PHASE 1 SMOKE TEST
================================
Provider: OpenRouter
Strands: PASS
Model invocation: PASS
Real response: PASS

Response:
LedgerGuard Phase 1 agent verification passed.

================================
PHASE 1 FOUNDATION: PASS
================================
```

If `OPENROUTER_API_KEY` is not set:
```text
OPENROUTER_API_KEY is not configured. Smoke test cannot run.
```

## Security

- Secrets and credentials must only be provided via environment variables or `.env`.
- `.env` and credential files are excluded in `.gitignore` and must never be committed.
- Sensitive values (e.g., API keys) are managed via Pydantic `SecretStr` to prevent accidental logging or exposure.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
