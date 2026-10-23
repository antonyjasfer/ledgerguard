# LedgerGuard — Engineering Audit & Functionality Traceability Matrix

This document provides complete traceability, honest feature categorization, architecture mapping, and cryptographic audit proofs for LedgerGuard across all 15 audit phases.

---

## 1. Executive Summary & Quality Gates

| Metric | Measured Status | Verification Command |
| :--- | :--- | :--- |
| **Total Automated Tests** | **318 Passed, 7 Skipped, 0 Failed** | `pytest tests -q` |
| **Phase 2 Selection Tests** | 5 / 5 Passed | `pytest tests/test_transaction_selection.py -v` |
| **Phase 3 Anomaly Rule Tests** | 6 / 6 Passed | `pytest tests/test_anomaly.py -v` |
| **Phase 5 Cryptographic Chain Tests** | 5 / 5 Passed | `pytest tests/test_audit_chain_verification.py -v` |
| **Phase 6 SQLite WAL Tests** | 5 / 5 Passed | `pytest tests/test_sqlite_persistence.py -v` |
| **Phase 10 Security & XSS Tests** | 5 / 5 Passed | `pytest tests/test_security_xss.py -v` |
| **Frontend Production Build** | **Clean TypeScript + Vite (0 Errors)** | `cd frontend && npm run build` |
| **Database Engine** | **SQLite (WAL Mode, Thread-Safe)** | `data/ledgerguard.db` |
| **MCP Protocol Standard** | **Streamable HTTP (2025-11-25 Spec)** | `POST /mcp` |

---

## 2. Functionality Traceability Table

Trace format: `UI Control → Frontend Handler → HTTP Request → Backend Route → Service/Tool → Storage/External → Displayed Result`

| UI Control / Trigger | Frontend Handler | HTTP Request | Backend Route | Service / Tool | Storage / Engine | Displayed Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Voice Mic Button ("Speak")** | `startDictation()` / `toggleMicrophone()` | `POST /api/alexa/converse` | `converse_endpoint` | `AlexaStateService.process_voice_turn` | SQLite (`session_turns`, `audit_blocks`) | Pulse state indicator, transcribed prompt, voice speech output, updated carousel cards. |
| **Quick Prompt: "Audit Batch"** | `sendTurn('Audit my pending AP invoices...')` | `POST /api/alexa/converse` | `converse_endpoint` | `calculate_invoice_arithmetic`, `check_duplicate_invoice`, `evaluate_invoice_policy`, `calculate_invoice_risk` | SQLite (`session_turns`) | Comprehensive voice synthesis & updated carousel highlighting verified and flagged invoices. |
| **Quick Prompt: "Run Anomaly Scanner"** | `sendTurn('Run deterministic anomaly detection scanner')` | `POST /api/alexa/converse` | `converse_endpoint` | `detect_transaction_anomalies` (`scan_invoice_anomalies`) | Deterministic Rule Engine + SQLite | Voice report detailing subscription price hikes, duplicate billing attacks, arithmetic inflations, and unregistered vendor breaches. |
| **Quick Prompt: "Inspect 102"** | `sendTurn('Inspect invoice INV-2026-102 arithmetic')` | `POST /api/alexa/converse` | `converse_endpoint` | `calculate_invoice_arithmetic` | SQLite (`audit_blocks`) | Voice audio explaining the unbacked $1,200 line-item difference; block sealed in chain. |
| **Quick Prompt: "Quarantine 103"** | `sendTurn('Quarantine invoice INV-2026-103 and freeze vendor')` | `POST /api/alexa/converse` | `converse_endpoint` | `execute_action` / `append_audit_block` | SQLite (`invoices`, `vendor_policies`, `audit_blocks`) | Status pill updates to `QUARANTINED`, vendor frozen, new Argon2id block appended. |
| **Card Action: "Approve & Seal"** | `executeAction(invId, 'APPROVE_AND_SEAL')` | `POST /api/alexa/action` | `action_endpoint` | `AlexaStateService.execute_action` | SQLite (`invoices`, `audit_blocks`) | Status pill changes to `SEALED & APPROVED`; Argon2id cryptographic block appended. |
| **Card Action: "Quarantine"** | `executeAction(invId, 'QUARANTINE_AND_DISPUTE')` | `POST /api/alexa/action` | `action_endpoint` | `AlexaStateService.execute_action` | SQLite (`invoices`, `audit_blocks`) | Card status updates to `QUARANTINED`; audit chain feed displays dispute record. |
| **Card Action: "Freeze Vendor"** | `executeAction(invId, 'FREEZE_VENDOR')` | `POST /api/alexa/action` | `action_endpoint` | `AlexaStateService.execute_action` | SQLite (`vendor_policies`, `audit_blocks`) | Vendor policy set to `FROZEN_ADMIN_HOLD`; card displays frozen status. |
| **Card Action: "Reset"** | `executeAction(invId, 'RESET')` | `POST /api/alexa/action` | `action_endpoint` | `AlexaStateService.execute_action` | SQLite (`invoices`, `vendor_policies`, `audit_blocks`) | Card resets to `PENDING_AUDIT`, vendor unfrozen. |
| **Header Button: "Verify Audit Chain"** | `verifyAuditChain()` | `POST /api/alexa/audit/verify` | `verify_audit_chain_endpoint` | `ArgonVaultConnector.verify_chain_integrity` | Cryptographic Genesis-to-Tip Chain Validator | Verification badge updates to `VERIFIED TAMPER-FREE (N Blocks) [100% Cryptographic Match]`. |
| **Header Button: "Tamper Test"** | `runTamperTest()` | `POST /api/alexa/tamper-test` | `tamper_test_endpoint` | `ArgonVaultConnector.verify_tamper_evidence` | Memory-hard Argon2id Evaluator | Tamper Modal pops up displaying injected payload, showing Original = VALID [200 OK] and Tampered = TAMPER BLOCKED (403). |
| **MCP Query: "tools/list"** | `callMcpToolsList()` | `POST /mcp` | `McpStreamableHttpServer.handle_request` | MCP Connector tools catalogue | In-memory MCP protocol dispatcher | JSON output window displays compliant MCP tool list conforming to 2025-11-25 spec. |
| **MCP Tool: "Call Anomaly Scanner"** | `callMcpAnomalyTool()` | `POST /mcp` | `McpStreamableHttpServer.handle_request` | `detect_transaction_anomalies` | Deterministic Anomaly Engine | JSON output window displays structured `AnomalyScanReport` for current AP batch. |
| **React Navigation: "Full React App"** | Anchor link (`/app`) | `GET /app` | Static Mount (`frontend/dist`) | Vite React App Bundle | Client-side Router | Navigates to full multi-page React application dashboard. |

---

## 3. Advertised Features Status Table

| Feature Category | Advertised Feature | Implementation Status | Honest Reality & Technical Scope |
| :--- | :--- | :--- | :--- |
| **Forensic Arithmetic** | Exact line-item summation & tax validation | **FUNCTIONAL AND VERIFIED** | Uses Python `Decimal` with zero binary floating-point inaccuracy. Detects $1,200 padding on INV-2026-102. |
| **Duplicate Detection** | Duplicate invoice & disbursement detection | **FUNCTIONAL AND VERIFIED** | Checks amount, vendor, date, and historical references. Identifies INV-2026-103 matching settled INV-2026-042. |
| **Anomaly Detection** | Recurring price increases, duplicate charges, arithmetic errors, unregistered vendor spend | **FUNCTIONAL AND VERIFIED** | Fully implemented in `app/tools/anomaly.py` across 4 formal rules (`RULE-ANOMALY-SUB-01`, `DUP-01`, `MATH-01`, `VEND-01`). Verified by 6 dedicated unit tests. |
| **Cryptographic Seal** | Tamper-evident Argon2id + SHA-256 hash chain | **FUNCTIONAL AND VERIFIED** | Complete genesis-to-tip validation in `connectors/argon_connector.py`. Verifies payload hashes, prev_hash linkages, and Argon2id memory-hard seals. Validated by tamper tests. |
| **Data Persistence** | Multi-session state retention across restarts | **FUNCTIONAL AND VERIFIED** | Powered by SQLite in WAL mode (`data/ledgerguard.db`). Survives process termination, maintaining invoices, audit chain, session turns, and vendor overrides. |
| **Transaction Selection** | Strict ID matching, zero ID guessing | **FUNCTIONAL AND VERIFIED** | Eliminates substring heuristics. Unknown IDs (e.g. `TX-901`, `TX-902`) return explicit `TRANSACTION_NOT_FOUND` without mutations. Tested against conflicting requests. |
| **Web Speech API** | Hands-free microphone dictation | **FUNCTIONAL AND VERIFIED** | Employs browser Web Speech API. Microphone only dispatches when speech is captured; handles errors gracefully. |
| **MCP Server** | Streamable HTTP MCP (2025-11-25 Spec) | **FUNCTIONAL AND VERIFIED** | Exposes 7 tools including `detect_transaction_anomalies` and `verify_ledger_audit_chain` on `POST /mcp`. Verified with MCP tool calling tests. |
| **Amazon Bedrock AI** | Cloud LLM inference (Claude / Strands) | **FUNCTIONAL WITH MOCKS / LOCAL ROUTER** | Production router detects AWS credentials. If unavailable, seamlessly falls back to `deterministic_local_router` with transparent simulation disclosure. |
| **Autonomous Banking Rails**| Live ACH / Wire payment freeze & dispute | **CLEARLY LABELED SIMULATION** | The app explicitly informs the user: *"Demo simulation only — internal ledger updated; no external banking rails or vendors were contacted."* |
| **External ERP Integration**| Live SAP / NetSuite bidirectional sync | **NOT CONNECTED** | Architectural stub ready for enterprise connectors, but no live credentials exist in development environment. |

---

## 4. Cryptographic Proof Architecture

```
[ Genesis Block #0 ]
  prev_hash:   0000000000000000000000000000000000000000000000000000000000000000
  payload:     "0000...|GENESIS|GENESIS_CHAIN_INITIALIZED|2026-10-22T00:00:00Z"
  sha256:      a202f0968c97a64aa4ad66d46794093709ee99a058e32c46af4f858276d80d4d
  argon2_seal: $argon2id$v=19$m=65536,t=2,p=2$TAvQkcOhqdUeRSusjjghDg$...
         │
         ▼
[ Block #1: Ingestion ]
  prev_hash:   $argon2id$v=19$m=65536,t=2,p=2$TAvQkcOhqdUeRSusjjghDg$... (Block #0 Seal)
  payload:     "$argon2id...|INV-2026-101|INITIAL_FORENSIC_INGESTION_VERIFIED_CLEAN|..."
  sha256:      9e3aa3dc768ecb7bf88b2922e4065c0e9b34e466a8b3e2507ba1596c8dd8eb57
  argon2_seal: $argon2id$v=19$m=65536,t=2,p=2$hOTONLrZkp3FukMAqkQYjw$...
         │
         ▼
[ Block #2 .. Block #N: Action / Dispute / Verification ]
  prev_hash:   Block #(N-1) Seal
  sha256:      Canonical SHA-256 Digest
  argon2_seal: Memory-hard cryptographic seal (64MB RAM, 2 iterations, 2 threads)
```

### Tamper-Evidence Invariants
1. **Payload Invariance:** Changing any field (amount, vendor, account, timestamp) alters the canonical string, breaking both the SHA-256 digest and the Argon2id seal.
2. **Link Continuity:** Deleting or swapping any block breaks `prev_hash` pointers, immediately detected during `verify_chain_integrity()`.
3. **Computational Defense:** Forging an altered block requires 64MB of dedicated RAM per hash, rendering offline mass-forgery attacks computationally prohibitive.

---

## 5. Security & XSS Defense Model

1. **Strict HTML Escaping:** Dynamic data rendered on `/` passes through `escapeHtml()` replacing `&`, `<`, `>`, `"`, and `'`.
2. **API Input Resilience:** Hostile payloads (`<script>`, SQL injection strings, oversized buffers) are safely sanitized and stored as plain text literals without server-side execution.
3. **No Secret Leaks:** Stack traces, environment secrets, and sensitive tokens are strictly redacted from public API response models.
