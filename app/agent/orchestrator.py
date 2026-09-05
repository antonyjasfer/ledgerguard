"""Orchestration and execution observability for LedgerGuard verification agent.

Provides structured execution tracking, safe metadata logging, and end-to-end
verification workflows that integrate deterministic tools, reasoning, and the Decision Guard.
"""

import uuid
from typing import Sequence

from pydantic import BaseModel, Field

from app.agent.decision import synthesize_decision
from app.agent.decision_guard import DecisionGuardResult, validate_agent_decision
from app.config import Settings, get_settings
from app.models.decision import AgentDecision, VerificationDecision
from app.models.invoice import Invoice
from app.models.policy import PolicyConfig
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    PolicyVerificationResult,
    RiskLevel,
    RiskResult,
    VendorHistoryResult,
)
from app.tools.arithmetic import calculate_invoice_arithmetic
from app.tools.duplicates import check_duplicate_invoice
from app.tools.policy import evaluate_invoice_policy
from app.tools.risk import calculate_invoice_risk
from app.tools.vendor_history import get_vendor_history


class ExecutionMetadata(BaseModel):
    """Safe execution metadata for observability and audit trails.

    Explicitly excludes secrets, credentials, tokens, and raw document contents.
    """
    agent_run_id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    provider: str = Field(..., description="Model provider identifier")
    model: str = Field(..., description="Model identifier")
    tools_called: list[str] = Field(default_factory=list, description="Ordered list of tools invoked")
    decision: AgentDecision = Field(..., description="Final verified decision")
    risk_level: RiskLevel | None = Field(default=None, description="Risk level evaluated")
    was_overridden: bool = Field(default=False, description="Whether Decision Guard overrode the decision")
    override_reason: str | None = Field(default=None, description="Reason for Decision Guard override")


def run_verification_workflow(
    invoice: Invoice,
    history: Sequence[Invoice] = (),
    policy_config: PolicyConfig | None = None,
    settings: Settings | None = None,
    agent_proposed_decision: AgentDecision | None = None,
    agent_summary: str = "",
) -> tuple[VerificationDecision, ExecutionMetadata]:
    """Execute the end-to-end verification pipeline with Decision Guard protection.

    1. Executes deterministic verification tools as needed based on available data.
    2. Collects structured findings and tool trace.
    3. Synthesizes a structured decision.
    4. Applies Decision Guard to validate/override the decision against deterministic safety rules.
    5. Emits safe execution metadata without exposing credentials.

    Args:
        invoice: The candidate invoice under verification.
        history: Prior historical invoices for vendor history and duplicate checks.
        policy_config: Optional custom corporate policy thresholds.
        settings: Optional application settings to resolve provider/model names.
        agent_proposed_decision: Optional proposed decision from LLM (to test guard overrides).
        agent_summary: Optional LLM rationale/summary.

    Returns:
        Tuple of (Final VerificationDecision, ExecutionMetadata).
    """
    resolved_settings = settings or get_settings()
    tools_called: list[str] = []

    # 1. Arithmetic verification
    arith_result: ArithmeticVerificationResult | None = None
    if invoice.line_items or invoice.subtotal is not None or invoice.total is not None:
        arith_result = calculate_invoice_arithmetic(invoice)
        tools_called.append("calculate_invoice_arithmetic")

    # 2. Duplicate detection
    dup_result: DuplicateCheckResult = check_duplicate_invoice(invoice, history)
    tools_called.append("check_duplicate_invoice")

    # 3. Vendor history
    vendor_result: VendorHistoryResult | None = None
    if invoice.vendor_id:
        vendor_result = get_vendor_history(invoice.vendor_id, history)
        tools_called.append("get_vendor_history")

    # 4. Policy evaluation
    policy_result: PolicyVerificationResult | None = None
    if vendor_result is not None and dup_result is not None:
        policy_result = evaluate_invoice_policy(invoice, vendor_result, dup_result, policy_config)
        tools_called.append("evaluate_invoice_policy")

    # 5. Risk calculation
    risk_result: RiskResult | None = None
    if (
        arith_result is not None
        and dup_result is not None
        and vendor_result is not None
        and policy_result is not None
    ):
        risk_result = calculate_invoice_risk(arith_result, dup_result, vendor_result, policy_result, invoice)
        tools_called.append("calculate_invoice_risk")

    # Synthesize evidence-based decision
    synthesized = synthesize_decision(
        arithmetic=arith_result,
        duplicate=dup_result,
        vendor=vendor_result,
        policy=policy_result,
        risk=risk_result,
        tools_called=tools_called,
        agent_summary=agent_summary,
    )

    # If an external agent proposed a different decision, validate it through the Guard
    proposed = agent_proposed_decision or synthesized.decision
    guard_result: DecisionGuardResult = validate_agent_decision(
        agent_decision=proposed,
        arithmetic=arith_result,
        duplicate=dup_result,
        policy=policy_result,
        risk=risk_result,
    )

    # Final decision reflects guard enforcement
    final_decision_val = guard_result.final_decision
    final_summary = synthesized.summary
    if guard_result.was_overridden:
        final_summary = f"[GUARD OVERRIDE] {guard_result.override_reason}. Original: {proposed.value}"

    final_verification_decision = VerificationDecision(
        decision=final_decision_val,
        confidence=synthesized.confidence,
        summary=final_summary,
        evidence=synthesized.evidence,
        risk_level=synthesized.risk_level,
        risk_score=synthesized.risk_score,
        tools_called=tools_called,
        requires_human=(final_decision_val in (AgentDecision.MANUAL_REVIEW, AgentDecision.BLOCK, AgentDecision.ESCALATE)),
        human_review_reason=guard_result.override_reason or synthesized.human_review_reason,
    )

    # Safe execution metadata
    provider_name = resolved_settings.LEDGERGUARD_MODEL_PROVIDER
    model_name = (
        resolved_settings.BEDROCK_MANTLE_MODEL_ID
        if provider_name == "bedrock_mantle"
        else resolved_settings.OPENROUTER_MODEL_ID
    )

    metadata = ExecutionMetadata(
        provider=provider_name,
        model=model_name,
        tools_called=tools_called,
        decision=final_decision_val,
        risk_level=synthesized.risk_level,
        was_overridden=guard_result.was_overridden,
        override_reason=guard_result.override_reason,
    )

    return final_verification_decision, metadata
