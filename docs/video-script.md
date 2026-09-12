# LedgerGuard Hackathon Demonstration Video Script

**Duration**: ~2:30 - 3:00 minutes  
**Target Audience**: AWS Hackathon Judges, FinTech Engineers, AP Finance Leaders  
**Topic**: Autonomous AP Invoice Verification with Strands Agents, Bedrock Mantle, and Decision Guard  

---

### [0:00 - 0:25] Introduction & The Problem
**Visual**: Presenter on camera or LedgerGuard Dashboard opening screen (http://127.0.0.1:5173/).
**Audio / Voiceover**:
> "Accounts Payable teams spend thousands of hours manually checking routine invoices. But traditional rule-based software is brittle, while generic LLMs hallucinate calculations and cannot be trusted with company funds.
>
> Introducing **LedgerGuard**: an autonomous Accounts Payable invoice verification agent built with the **Strands Agents SDK** and **Amazon Bedrock Mantle**.
>
> Our core philosophy is simple: **The AI agent reasons over evidence, while deterministic tools verify financial facts and Decision Guard enforces safety boundaries.**"

---

### [0:25 - 0:55] Architecture & Pipeline
**Visual**: Show Dashboard Architecture Diagram or high-level flow in the UI.
**Audio / Voiceover**:
> "When an invoice arrives via our FastAPI REST backend:
> 1. Raw documents are stored securely in **Amazon S3** for audit transparency.
> 2. Jobs are queued through **Amazon SQS**.
> 3. Our background worker invokes the **Strands Verification Agent**, powered by Google's Gemma 3 27B IT running on **Amazon Bedrock Mantle** in us-east-1.
> 4. The agent dynamically calls five side-effect-free deterministic verification tools: Arithmetic, Duplicate Detection, Vendor History, Policy Check, and Risk Scoring.
> 5. Finally, the **Decision Guard** layer evaluates the verdict against hard safety rules before persisting to **Amazon DynamoDB**."

---

### [0:55 - 1:25] Scenario 1: Autonomous Auto-Approval
**Visual**: Navigate to Invoices directory in browser, click on DEMO-INV-CLEAN-01.
**Audio / Voiceover**:
> "Let's see this in action with Scenario 1: A routine, clean invoice from established vendor Apex Cloud Technologies for .00.
> 
> Looking at the **Verification Evidence panel**:
> - Arithmetic check confirms line items and totals match down to the exact cent.
> - Duplicate check confirms zero invoice collisions.
> - Vendor history verifies prior good standing.
> - Policy check passes within auto-approval thresholds.
> - Composite risk score is calculated as zero.
>
> The invoice is **AUTO-APPROVED** immediately without human intervention, safely expediting routine payables."

---

### [1:25 - 2:05] Scenario 2: High-Value Exception & Human Review
**Visual**: Click into DEMO-INV-RISKY-02 (,500.00 from Nova Advisory Partners).
**Audio / Voiceover**:
> "Now Scenario 2: An unverified new vendor submits a ,500 consulting invoice.
> 
> The arithmetic is accurate, but our policy engine flags two violations: an unverified vendor profile and a total exceeding the auto-approval ceiling. The risk engine assigns a high risk score of 50+.
>
> Instead of blocking or guessing, LedgerGuard routes this exception to **MANUAL REVIEW**.
> 
> Watch the human audit workflow: An auditor opens the review dialog, selects **APPROVE**, and enters their audit justification.
> 
> The system updates the lifecycle state to Approved while immutably preserving the original automated evidence, recorded in the single-table DynamoDB audit trail."

---

### [2:05 - 2:35] Scenario 3: Duplicate Attack & Decision Guard Override
**Visual**: Click into DEMO-INV-BLOCK-03. Switch to the **Decision Guard** tab.
**Audio / Voiceover**:
> "What happens if someone submits a duplicate invoice? In Scenario 3, an invoice arrives with the same invoice number as our first approved bill.
> 
> Even if an AI model were tempted to approve this invoice based on its formatting, our **Decision Guard** intercepts.
>
> As you can see highlighted in red on our Decision Guard visualizer: **Decision Guard Safety Override Active!**
> The rule enforces a mandatory **BLOCK** on confirmed duplicate collisions. The LLM's recommendation is safely overridden, protecting the company from duplicate payment."

---

### [2:35 - 2:50] Summary & Conclusion
**Visual**: Return to Executive Dashboard showing aggregate statistics, live metrics, and audit timeline.
**Audio / Voiceover**:
> "LedgerGuard demonstrates how modern enterprise AI should be built:
> - Autonomous reasoning with **Strands SDK** and **Bedrock Mantle**
> - Deterministic verification where facts matter
> - Hard safety boundaries with **Decision Guard**
> - Complete enterprise auditability with **Amazon DynamoDB & S3**
>
> Thank you!"
