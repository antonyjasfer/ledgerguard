---
name: ledgerguard
description: Autonomous Accounts Payable invoice verification and cryptographic audit sealing skill for Alexa+ and Bedrock agents.
version: 1.0.0
mcp_endpoint: http://127.0.0.1:8000/mcp
protocol_version: 2025-11-25
---

# LedgerGuard Alexa+ Agent Skill

LedgerGuard is an enterprise Accounts Payable (AP) fraud prevention and invoice verification agent built for **Amazon Alexa+** and **AWS Bedrock**. It provides autonomous verification of invoice math, vendor legitimacy, corporate policy thresholds, duplicate prevention, and cryptographically seals every transaction in an Argon2id tamper-evident vault.

## MCP Server Integration

This skill connects to the LedgerGuard Alexa+ MCP server using the **Model Context Protocol (MCP)** over Streamable HTTP:

- **Endpoint URL**: `http://127.0.0.1:8000/mcp`
- **MCP Protocol Version**: `2025-11-25`
- **Supported Transports**: Streamable HTTP (`application/json` & `text/event-stream` SSE)

### Connected MCP Server Configuration (`.antigravity/mcp_config.json` & `.mcp.json`)

```json
{
  "mcpServers": {
    "amazon-devices-buildertools": {
      "command": "npx",
      "args": ["-y", "@amazon-devices/amazon-devices-buildertools-mcp"]
    },
    "ledgerguard-alexa-plus-mcp": {
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "streamable-http"
    }
  }
}
```

---

## Tool Catalogue

The LedgerGuard Alexa+ Skill exposes 8 specialized verification and cryptographic tools:

### 1. `calculate_invoice_arithmetic`
Validates arithmetic consistency of monetary fields using exact `Decimal` mathematics.
- Checks line item subtotals (`quantity * unit_price`).
- Sums line item totals to subtotal.
- Evaluates tax, discounts, and shipping additions.
- Confirms grand total matches.
- Returns `PASS`, `FAIL`, or `INSUFFICIENT_DATA`.

### 2. `check_duplicate_invoice`
Checks candidate invoice against all historical vendor records to prevent duplicate disbursements.
- Returns `CONFIRMED_DUPLICATE`: Identical vendor ID and invoice number.
- Returns `POSSIBLE_DUPLICATE`: Matching vendor ID and total amount within 7 calendar days.
- Returns `NO_DUPLICATE`: Unique invoice.

### 3. `get_vendor_history`
Retrieves vendor trustworthiness profile, master vendor registry status, dispute frequency, and payment risk tier (`LOW`, `MODERATE`, `HIGH`, `RESTRICTED`).

### 4. `evaluate_invoice_policy`
Evaluates invoice details against enterprise policies:
- Single-invoice spend approval thresholds (e.g. $10,000 auto-approval ceiling).
- Vendor authorization status (unregistered/new vendors require manual controller signoff).
- Line-item description compliance and currency restrictions.

### 5. `calculate_invoice_risk`
Synthesizes the deterministic tool outputs into a composite risk assessment:
- **Risk Score**: 0 to 100.
- **Risk Level**: `LOW`, `MEDIUM`, or `HIGH`.
- **Action Recommendation**: `AUTO_APPROVE`, `MANUAL_REVIEW`, or `REJECT`.

### 6. `seal_ledger_audit_record`
Generates a tamper-evident cryptographic seal for an audit event using:
- **Algorithm**: `Argon2id` (memory_cost = 64MB, time_cost = 2, parallelism = 2)
- **Pre-digest**: `SHA-256`
- **Payload format**: `prev_hash|tx_id|action|timestamp`

### 7. `verify_ledger_audit_seal`
Verifies an existing Argon2id seal to prove that the ledger entry has not been altered or tampered with since creation.

### 8. `verify_invoice_autonomous`
Executes full verification workflow (tools 1-5), synthesizes the verdict via the resilient agent router, and produces a sealed Argon2id vault record in a single autonomous operation.

---

## Alexa+ Voice Interaction Patterns

Users can interact with LedgerGuard naturally through Alexa+ voice commands:

### Invoice Ingestion & Verification
- *"Alexa, ask LedgerGuard to verify invoice INV-2026-001 from Acme Corp."*
- *"Alexa, check if the math on invoice 4092 is correct."*
- *"Alexa, are there any duplicate invoices submitted this week?"*

### Risk & Policy Assessment
- *"Alexa, what is the risk score for invoice INV-2026-001?"*
- *"Alexa, why was the payment to Global Supplies flagged for manual review?"*

### Cryptographic Audit & Vault Verification
- *"Alexa, seal this invoice verification in the tamper-evident ledger."*
- *"Alexa, verify the cryptographic seal for transaction TX-9921."*
- *"Alexa, run a tamper-evidence audit on the batch ledger."*

---

## Multi-Tier Resilience & Fallback Architecture

To ensure 100% demo reliability and production fault-tolerance:

1. **Tier 1 (Amazon Bedrock Runtime)**: Uses `amazon.nova-lite-v1:0` via Strands `BedrockModel`.
2. **Tier 2 (Resilient Deterministic Router)**: If Bedrock returns `NOT_AUTHORIZED` (e.g. pending Amazon Action on Support Case 178842133900178) or throws `ValidationException: Operation not allowed`, the connector seamlessly executes the local deterministic verification tool pipeline.
3. **Cryptographic Sealing**: All audit records are sealed using Argon2id with 64MB memory hardness, ensuring irreversible tamper protection even if offline.
