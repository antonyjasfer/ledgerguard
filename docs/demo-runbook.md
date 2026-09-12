# LedgerGuard Demo Runbook

## Overview

LedgerGuard is an autonomous Accounts Payable (AP) invoice verification agent built with the **Strands Agents SDK**, **Amazon Bedrock Mantle** (running google.gemma-3-27b-it), deterministic verification tools, and a deterministic **Decision Guard** layer.

### Core Philosophy
> *The AI model reasons over evidence, while deterministic tools verify financial facts and Decision Guard enforces safety boundaries.*

---

## Architecture

`	ext
Web Frontend (React / Vite)
        |
        v
FastAPI Backend (REST API / Auth / OpenAPI)
   |                |
   v                v
Amazon S3       Amazon SQS
(Documents)    (Processing Jobs)
                    |
                    v
            Background Worker
                    |
                    v
          Strands Verification Agent
          (google.gemma-3-27b-it on Bedrock Mantle)
                    |
                    v
          Deterministic Verification Tools
          (Arithmetic, Duplicate, Vendor History, Policy, Risk)
                    |
                    v
             Decision Guard
          (Safety Boundary & Hard Policy Enforcement)
                    |
                    v
             Amazon DynamoDB
          (Single-table Records & Immutable Audit Trail)
`

> **Document Storage Transparency Note**: Documents are stored in Amazon S3 for audit and manual inspection. OCR and PDF text extraction are not implemented.

---

## Prerequisites & Environment

1. **Python Environment**:
   - Python 3.11+ in .venv
   - Required packages: astapi, uvicorn, oto3, strands, pydantic, pytest
2. **Node Environment**:
   - Node.js v20+ / v24+
   - Frontend dependencies installed (cd frontend && npm install)
3. **AWS Configuration**:
   - AWS Profile: ledgerguard
   - AWS Region: us-east-1
   - Active resources: S3 bucket (ledgerguard-invoices-280769660832), DynamoDB table (ledgerguard-invoices), SQS queue (ledgerguard-invoice-jobs)
   - Active model provider: Amazon Bedrock Mantle (google.gemma-3-27b-it)
   - *Note: Traditional Bedrock Runtime account authorization is pending; Bedrock Mantle is the primary production provider.*

---

## Starting the System

### 1. Launch Backend Server
From the repository root:
`powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
`
Verify endpoints:
- Health: http://127.0.0.1:8000/health (200 OK)
- Docs: http://127.0.0.1:8000/docs (OpenAPI Swagger UI)

### 2. Launch Frontend Development Server
From the rontend directory:
`powershell
npm run dev
`
Open in browser: http://127.0.0.1:5173/

---

## Demo Data Management

The project includes an explicit synthetic demo manager (scripts/seed_demo.py) that strictly uses DEMO- and TEST- prefixes:

- **Seed Demo Invoices**:
  `powershell
  .\.venv\Scripts\python.exe scripts/seed_demo.py --seed
  `
- **Check Status**:
  `powershell
  .\.venv\Scripts\python.exe scripts/seed_demo.py --status
  `
- **Clean Demo Records**:
  `powershell
  .\.venv\Scripts\python.exe scripts/seed_demo.py --cleanup
  `

---

## Three Demonstration Scenarios

### Scenario 1: Routine Clean Invoice (Auto-Approved)
- **Invoice ID**: DEMO-INV-CLEAN-01
- **Vendor**: Apex Cloud Technologies LLC (.00 USD)
- **Profile**: Established vendor with historical billing, accurate line item math (.00 + .00 tax = .00), total under ,000 auto-approval threshold.
- **Verification Flow**:
  1. Arithmetic check validates math perfectly.
  2. Duplicate check confirms zero invoice number collisions.
  3. Vendor history verifies established vendor relationship.
  4. Policy engine confirms invoice is compliant.
  5. Composite risk score calculated as 0 (LOW).
  6. Decision Guard verifies no overrides required.
- **Outcome**: AUTO_APPROVED with zero human touch needed.

### Scenario 2: High-Value New Vendor Invoice (Manual Review & Human Review Flow)
- **Invoice ID**: DEMO-INV-RISKY-02
- **Vendor**: Nova Advisory Partners Inc (,500.00 USD)
- **Profile**: Unverified new vendor, total exceeds ,000 high-value threshold.
- **Verification Flow**:
  1. Arithmetic is valid (,000 subtotal + ,500 tax = ,500 total).
  2. Vendor history identifies new vendor with no past record.
  3. Policy engine triggers corporate review requirement.
  4. Risk engine computes elevated risk score (HIGH / 50+).
  5. Automated verdict routes invoice to MANUAL_REVIEW.
- **Human Review Flow**:
  1. An AP auditor clicks **"Perform Human Review"**.
  2. Reviewer enters identity (Auditor Alice), selects action (APPROVE), and provides audit rationale.
  3. Backend updates the record to APPROVED while preserving original automated findings.
  4. Audit trail records HUMAN_REVIEW_RECORDED event immutably.

### Scenario 3: Duplicate Invoice Submission (Decision Guard Safety Override -> Blocked)
- **Invoice ID**: DEMO-INV-BLOCK-03
- **Vendor**: Apex Cloud Technologies LLC (.00 USD)
- **Profile**: Re-submission of invoice number INV-2026-001 already settled in Scenario 1.
- **Verification Flow**:
  1. Agent evaluates the invoice structure.
  2. Duplicate detection tool detects exact collision with DEMO-INV-CLEAN-01.
  3. Decision Guard intercepts: even if an automated agent proposed approval, Decision Guard Rule 1 enforces a hard BLOCK.
- **Outcome**: BLOCKED with explicit visual override banner explaining the duplicate conflict.
