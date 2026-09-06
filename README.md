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
                 /         |                         /          |                         v           v           v
       +-------------+ +-------------+ +--------------------+
       |   Bedrock   | | OpenRouter  | |   Amazon Bedrock   |
       |   Mantle    | |(Development | |      Runtime       |
       |  (PRIMARY)  | | Alternative)| |(Auth Pending / AWS)|
       +-------------+ +-------------+ +--------------------+
```

- **LedgerGuard Agent**: Accounts-payable verification agent using Strands.
- **Model Factory**: Resolves the model provider from configuration without modifying agent code.
- **BedrockMantleProvider** (*Primary Development Provider*): Connects to Amazon Bedrock Mantle in `us-east-1` running Google Gemma 3 27B IT (`google.gemma-3-27b-it`) with dynamic SigV4-derived bearer tokens minted through AWS IAM credentials.
- **OpenRouterProvider** (*Explicit Alternative Provider*): OpenAI-compatible adapter for OpenRouter (`openai/gpt-4o-mini`) during development.
- **BedrockRuntimeProvider** (*Architectural Provider*): Traditional Amazon Bedrock provider prepared for AWS production deployment.

## Phase 2 ? Deterministic Invoice Verification Engine

**Core Principle**:
> *The LLM reasons over evidence, while deterministic tools verify financial facts.*

In AP invoice verification, AI models reason over unstructured document context and semantics, while all financial arithmetic, policy boundaries, duplicate checks, and risk metrics are verified by deterministic, side-effect-free tools.

### Key Architectural Characteristics
- **Strict Decimal Precision**: All monetary computations are performed using Python's `Decimal` quantized to `Decimal("0.01")` with `ROUND_HALF_UP`. Floating-point representations are strictly forbidden in data models and tools.
- **Multi-Currency Safety**: Monetary amounts are segregated by currency. The system explicitly prevents summing or aggregating across different currency codes without exchange rates.
- **Offline & Autonomous**: Phase 2 tools execute entirely offline without network access, LLM inference, or AWS/cloud dependencies.
- **Tolerant Extraction Modeling**: Incomplete invoices (e.g., partial OCR extraction with `subtotal=None` or `total=None`) are supported without validation errors, returning structured `INSUFFICIENT_DATA` verification statuses.

### Tools & Engines
1. **Invoice Domain Models** (`app/models/invoice.py`): Type-safe Pydantic models for `Invoice` and `LineItem` enforcing Decimal monetary quantities and half-up rounding.
2. **Verification Schemas** (`app/models/verification.py`): Structured enums (`VerificationStatus`, `DuplicateStatus`, `RiskLevel`, `RecommendedAction`) and output models for all verification tools.
3. **Arithmetic Verification Tool** (`app/tools/arithmetic.py`): Evaluates `quantity * unit_price` per line item, subtotal sum accuracy, tax, discount, and expected grand total. Flags `INSUFFICIENT_DATA` if required fields are missing.
4. **Duplicate Detection Tool** (`app/tools/duplicates.py`): Evaluates historical invoices for `CONFIRMED_DUPLICATE` (same vendor and invoice number) and `POSSIBLE_DUPLICATE` (same vendor and total within a 7-day window).
5. **Vendor History Tool** (`app/tools/vendor_history.py`): Computes historical invoice volume, average and maximum spend per currency, date horizons, and recent invoice density without external database dependencies.
6. **Policy Engine** (`app/tools/policy.py`, `app/models/policy.py`): Centralizes corporate AP policy rules (auto-approval limit <= $1,000, high-value ceiling >= $5,000, new vendor review, duplicate payment blocks). Preserves all triggered violations.
7. **Risk Engine** (`app/tools/risk.py`): Computes composite risk score (0?100) from active risk factors, assigns severity levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), enforces a mandatory critical override for confirmed duplicates, and outputs recommended workflow actions (`AUTO_APPROVE`, `MANUAL_REVIEW`, `BLOCK`).

## Phase 3 — Autonomous Verification Agent

**Core Principle**:
> *The LLM reasons over evidence, while deterministic tools verify financial facts.*

In Phase 3, LedgerGuard connects the 5 deterministic verification tools from Phase 2 into an autonomous Strands Agent architecture with strict decision precedence, safe execution tracking, and a deterministic Decision Guard layer.

### Architectural Principles
- **No Financial Hallucination**: The LLM does not calculate financial truth. Deterministic tools establish financial facts.
- **Autonomous Tool Selection**: The agent inspects candidate invoice data, determines necessary checks, and invokes deterministic tools dynamically.
- **Evidence-Based Reasoning**: Decisions are synthesized from structured tool outputs. The agent cannot override or fabricate verification evidence.
- **Deterministic Decision Guard**: A final safety enforcement layer validates the agent's proposed verdict against hard business rules. Even if the LLM hallucinates an auto-approval, the guard intercepts and enforces safety rules (e.g., confirmed duplicates and critical risk always force a `BLOCK`).

### Architecture Diagram

```mermaid
flowchart TB
    subgraph Input["Invoice Verification Request"]
        Inv["Candidate Invoice"]
        Hist["Historical Invoices"]
        Pol["AP Policy Config"]
    end

    subgraph Agent["Strands Agent (LLM Reasoning)"]
        SP["System Prompt
Precedence Rules"]
        LLM["Bedrock Mantle
Google Gemma 3 27B IT"]
    end

    subgraph Tools["Deterministic Strands @tool Wrappers"]
        T1["calculate_invoice_arithmetic"]
        T2["check_duplicate_invoice"]
        T3["get_vendor_history"]
        T4["evaluate_invoice_policy"]
        T5["calculate_invoice_risk"]
    end

    subgraph Decision["Decision & Safety Layer"]
        DE["Decision Engine
synthesize_decision()"]
        DG["Decision Guard
validate_agent_decision()"]
    end

    Input --> Agent
    Agent -->|"Autonomous Tool Use"| Tools
    Tools -->|"Structured JSON Evidence"| Agent
    Agent -->|"Proposed Recommendation"| DE
    DE -->|"Synthesized Verdict"| DG
    DG -->|"Final Safe Decision"| Output["VerificationDecision
AUTO_APPROVE / MANUAL_REVIEW / BLOCK / ESCALATE"]
```

### Registered Verification Tools
1. **`calculate_invoice_arithmetic`**: Validates line-item math (`quantity * unit_price`), subtotal accumulation, tax, discount, and grand total consistency.
2. **`check_duplicate_invoice`**: Identifies `CONFIRMED_DUPLICATE` (same vendor + invoice number) and `POSSIBLE_DUPLICATE` (same vendor + total within 7 days).
3. **`get_vendor_history`**: Aggregates vendor spend volume, historical transaction counts, and identifies new vendors.
4. **`evaluate_invoice_policy`**: Evaluates corporate limits (auto-approval ceiling <= $1,000, high-value ceiling >= $5,000, new vendor review, duplicate payment block).
5. **`calculate_invoice_risk`**: Computes composite 0-100 risk score, factor weights, risk levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and recommended actions.

### Decision Precedence Rules
1. **CONFIRMED_DUPLICATE** -> **`BLOCK`**
2. **Policy Block** -> **`BLOCK`**
3. **CRITICAL Risk** -> **`BLOCK`**
4. **HIGH Risk** -> **`MANUAL_REVIEW`**
5. **Policy Requires Review** -> **`MANUAL_REVIEW`**
6. **MEDIUM Risk** -> **`MANUAL_REVIEW`**
7. **Insufficient Evidence** -> **`MANUAL_REVIEW`**
8. **LOW Risk + All Checks Passed** -> **`AUTO_APPROVE`**

### Decision Guard Enforcement
The Decision Guard acts as a circuit-breaker against model hallucinations. It **never downgrades safety**:
- Confirmed duplicate + Agent proposes `AUTO_APPROVE` -> **Overridden to `BLOCK`**
- Policy block + Agent proposes `MANUAL_REVIEW` -> **Overridden to `BLOCK`**
- Critical risk + Agent proposes `AUTO_APPROVE` -> **Overridden to `BLOCK`**
- Arithmetic `FAIL` + Agent proposes `AUTO_APPROVE` -> **Overridden to `MANUAL_REVIEW`**
- `INSUFFICIENT_DATA` + Agent proposes `AUTO_APPROVE` -> **Overridden to `MANUAL_REVIEW`**

### Observability & Audit Trail
Every verification workflow run records safe execution metadata (`ExecutionMetadata`):
- `agent_run_id`: Unique trace identifier
- `provider`: Model provider (e.g., `bedrock_mantle`)
- `model`: Model identifier (`google.gemma-3-27b-it`)
- `tools_called`: Ordered list of tools actually invoked
- `decision`: Final verified decision
- `risk_level`: Final assessed risk level
- `was_overridden` & `override_reason`: Audit trail of any guard interventions
- *Security*: Excludes all secrets, API keys, credentials, bearer tokens, and sensitive document payloads.


## Phase 4 ? AWS Data Layer + Background Processing

In Phase 4, LedgerGuard is upgraded from a local verification agent to an **AWS-backed background processing system**. Source invoice documents are stored in Amazon S3, processing jobs are queued via Amazon SQS, and verification results along with immutable audit trails are persisted in Amazon DynamoDB.

### Core Principle
> **THE MODEL REASONS. THE TOOLS VERIFY. AWS PROVIDES DURABLE STORAGE AND BACKGROUND EXECUTION.**

The Strands Agent and deterministic tools never manage AWS infrastructure directly; they operate through clean service abstractions.

### Architecture Diagram

```mermaid
flowchart TD
    Client["AP Client / Upstream Ingestion"]
    S3[("Amazon S3
invoices/{id}/{filename}")]
    SQS["Amazon SQS
Processing Queue"]
    Worker["LedgerGuard Worker
InvoiceProcessor"]
    Agent["Strands Agent
Autonomous Reasoning"]
    Tools["Deterministic Tools
Arithmetic / Duplicates / Policy / Risk"]
    Guard["Decision Guard
Circuit Breaker"]
    DDB[("Amazon DynamoDB
PK: INVOICE#{id}
SK: METADATA | EVENT#{ts}")]
    SM["AWS Secrets Manager
(App Secrets)"]

    Client -->|"1. Upload Document"| S3
    Client -->|"2. Enqueue Job"| SQS
    SQS -->|"3. Poll Message"| Worker
    Worker -->|"4. Verify Existence"| S3
    Worker -->|"5. Reason & Select Tools"| Agent
    Agent -->|"6. Compute Evidence"| Tools
    Tools -->|"7. Return Results"| Agent
    Agent -->|"8. Propose Decision"| Guard
    Guard -->|"9. Enforce Hard Safety"| Worker
    Worker -->|"10. Persist State & Audit"| DDB
    Worker -->|"11. Ack / Delete Message"| SQS
    SM -.->|"App Keys"| Worker
```

### Key Components

1. **Service Interfaces (`app/services/interfaces.py`)**:
   - `DocumentStore`: Document storage contract (upload, download, exists, delete).
   - `InvoiceRepository`: Persistent records, lifecycle states, and chronological audit event logging.
   - `JobQueue`: Asynchronous message publishing, polling with visibility timeout, and acknowledgment.
   - `SecretProvider`: Application secret management.

2. **Amazon S3 Integration (`app/services/s3.py`)**:
   - Stores raw invoice documents under sanitized, traversal-safe keys: `invoices/{invoice_id}/{filename}`.
   - Path traversal prevention (`..`, special characters stripped).

3. **Amazon DynamoDB Integration (`app/services/dynamodb.py`)**:
   - Single-table design:
     - `PK = INVOICE#{invoice_id}`, `SK = METADATA` for invoice entities and verification verdicts.
     - `PK = INVOICE#{invoice_id}`, `SK = EVENT#{timestamp}#{event_id}` for immutable audit trail events.
   - Strict serialization layer converting Decimals, Enums, dates, and Pydantic models safely without float precision loss.
   - Idempotent writes preventing state corruption on repeated execution.

4. **Amazon SQS Integration (`app/services/sqs.py`)**:
   - Job payloads contain only safe metadata (`job_id`, `invoice_id`, `s3_bucket`, `s3_key`). Raw documents and heavy JSON are excluded.
   - Strict transactional acknowledgment: messages are deleted from SQS **only after** DynamoDB persistence succeeds.

5. **AWS Secrets Manager Integration (`app/services/secrets.py`)**:
   - Provider-aware secret retrieval: only queries Secrets Manager when provider is explicitly `openrouter`.
   - Never queries Secrets Manager when using Bedrock Mantle.
   - AWS credentials remain managed exclusively via the standard AWS credential chain.

6. **Background Worker (`app/worker/processor.py` & `app/worker/main.py`)**:
   - `InvoiceProcessor` orchestrates message reception, document checks, verification, Decision Guard validation, durable state persistence, and SQS deletion.
   - Idempotency guard: jobs for invoices already in a terminal state (`AUTO_APPROVED`, `MANUAL_REVIEW`, `BLOCKED`) are safely deduplicated and acknowledged without re-running.
   - Safe logging: logs contain only safe operational metadata (`job_id`, `invoice_id`, status, decision, error category). Raw document bytes, base64 strings, and credentials are never logged.

### Processing Lifecycle States

Invoice processing progresses through the centralized state machine (`app/models/state.py`):
- `RECEIVED` -> Initial ingestion state
- `QUEUED` -> Job published to SQS
- `PROCESSING` -> Worker actively verifying invoice
- `VERIFIED` -> Tools and Decision Guard completed
- `AUTO_APPROVED` -> Clean low-risk invoice approved for payment (Terminal)
- `MANUAL_REVIEW` -> Policy violation, missing data, or medium/high risk requiring human AP review (Terminal)
- `BLOCKED` -> Confirmed duplicate or critical policy/risk violation (Terminal)
- `FAILED` -> System error, missing S3 artifact, or unhandled failure

### AWS Resource Creation Policy

> [!IMPORTANT]
> **Zero Automatic Infrastructure Creation**: The LedgerGuard application and worker will **NEVER** auto-create S3 buckets, DynamoDB tables, or SQS queues at startup. Infrastructure must be provisioned explicitly.

To provision development AWS resources:
```powershell
python scripts/provision_dev.py --confirm
```

Required AWS resources:
- S3 Bucket: `LEDGERGUARD_S3_BUCKET`
- DynamoDB Table: `LEDGERGUARD_DYNAMODB_TABLE` (default: `ledgerguard-invoices`, `PAY_PER_REQUEST` billing)
- SQS Queue: `LEDGERGUARD_SQS_QUEUE_URL` (default: `ledgerguard-invoice-jobs`)
- Secrets Manager Secret (Optional): `OPENROUTER_SECRET_NAME`

### Least-Privilege IAM Policy

For production deployments, the worker execution role requires only the following minimal permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3DocumentAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::your-ledgerguard-invoices-bucket/*"
    },
    {
      "Sid": "DynamoDBTableAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/ledgerguard-invoices"
    },
    {
      "Sid": "SQSJobQueueAccess",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:SendMessage",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "arn:aws:sqs:us-east-1:*:ledgerguard-invoice-jobs"
    },
    {
      "Sid": "SecretsManagerReadAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:ledgerguard/*"
    }
  ]
}
```

### Testing Strategy

- **Offline Unit Tests**: All unit tests run fully offline without requiring AWS credentials or network calls:
  ```powershell
  pytest tests -v
  ```
- **Opt-in Live Integration Tests**: Require configured AWS resources and are skipped by default:
  ```powershell
  $env:LEDGERGUARD_RUN_AWS_INTEGRATION = "true"
  pytest tests/integration -v
  ```
- **Live AWS End-to-End Pipeline Script**:
  ```powershell
  python scripts/aws_e2e_test.py
  ```

## Model Strategy & AWS Status

- **Primary Development Provider**: Amazon Bedrock Mantle
  - Model: Google Gemma 3 27B IT
  - Model ID: `google.gemma-3-27b-it`
  - Region: `us-east-1`
  - Endpoint Family: `bedrock-mantle`
  - Auth: AWS IAM credentials via standard credential chain (`ledgerguard` profile / `ledgerguard-dev` IAM identity)
- **Alternative Provider**: OpenRouter (`openai/gpt-4o-mini`) via explicit configuration.
- **Future / Currently Restricted Provider**: Traditional Amazon Bedrock Runtime (`amazon.nova-lite-v1:0`).
  - *Status*: Awaiting AWS Support account authorization resolution (`authorizationStatus = NOT_AUTHORIZED`, Case 178842133900178).
  - Traditional Bedrock Runtime provider construction executes zero network calls and zero model inference during development.

> [!NOTE]
> Provider selection is strictly explicit via `LEDGERGUARD_MODEL_PROVIDER`. There is **no automatic fallback** between providers.

## Local Development Setup

### Prerequisites
- Python 3.11+
- Virtual environment (`.venv`)
- Configured AWS profile (`ledgerguard`) for Bedrock Mantle

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
   # Primary Development Provider: Amazon Bedrock Mantle
   LEDGERGUARD_MODEL_PROVIDER=bedrock_mantle
   BEDROCK_MANTLE_MODEL_ID=google.gemma-3-27b-it
   AWS_REGION=us-east-1
   AWS_PROFILE=ledgerguard

   # Explicit Alternative Provider: OpenRouter
   # LEDGERGUARD_MODEL_PROVIDER=openrouter
   # OPENROUTER_API_KEY=<your-key>
   # OPENROUTER_MODEL_ID=openai/gpt-4o-mini
   # OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

   # Blocked Traditional Bedrock Runtime (Awaiting Account Authorization)
   # LEDGERGUARD_MODEL_PROVIDER=bedrock_runtime
   # BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
   # BEDROCK_PROFILE_NAME=ledgerguard
   ```

3. Run Unit Tests:
   Unit tests execute offline without external network access or Bedrock token consumption:
   ```powershell
   pytest tests -v
   ```

## Run Smoke Test

The real-model smoke test verifies end-to-end integration across Strands, the provider abstraction, and the live Google Gemma 3 27B IT model on Amazon Bedrock Mantle:

```powershell
python scripts/mantle_smoke_test.py
```

Expected output on successful verification:
```text
========================================
LEDGERGUARD BEDROCK MANTLE SMOKE TEST
========================================

Provider: Bedrock Mantle
Model: google.gemma-3-27b-it
Region: us-east-1
AWS Identity: ledgerguard-dev

Strands initialization: PASS
AWS credential resolution: PASS
Bedrock Mantle initialization: PASS
Real model invocation: PASS
Real response: PASS

Response:
LedgerGuard Bedrock Mantle verification passed.

========================================
BEDROCK MANTLE: PASS
========================================
```

## Security

- Secrets and credentials must only be provided via environment variables or `.env`.
- `.env` and credential files are excluded in `.gitignore` and must never be committed.
- Sensitive values (e.g., API keys) are managed via Pydantic `SecretStr` to prevent accidental logging or exposure.
- AWS authentication uses the standard AWS credential chain without hardcoded keys.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
