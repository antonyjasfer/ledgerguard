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
from app.models.policy import ApprovalRoutingTier, PolicyConfig, evaluate_approval_matrix
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    RiskLevel,
    RiskResult,
    VendorContextResult,
    VendorHistoryResult,
)
from app.services.vendor_context import vendor_context_service
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
    """Execute the end-to-end verification pipeline with Decision Guard protection."""
    resolved_settings = settings or get_settings()
    resolved_policy = policy_config or PolicyConfig()
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

    # 4. Vendor Context Service lookup (deterministic enterprise layer)
    vendor_context = vendor_context_service.evaluate_vendor_context(invoice, history_result=vendor_result)

    # 5. Policy evaluation
    policy_result: PolicyVerificationResult | None = None
    if vendor_result is not None and dup_result is not None:
        policy_result = evaluate_invoice_policy(
            invoice=invoice,
            vendor_history=vendor_result,
            duplicate_result=dup_result,
            config=resolved_policy,
            vendor_context=vendor_context,
            arithmetic_result=arith_result,
        )
        tools_called.append("evaluate_invoice_policy")

    # 6. Approval Matrix Evaluation
    is_dup_confirmed = (dup_result.status == DuplicateStatus.CONFIRMED_DUPLICATE)
    has_arith_fail = (arith_result is not None and not arith_result.passed)
    approval_routing = evaluate_approval_matrix(
        invoice_total=invoice.total,
        config=resolved_policy,
        is_new_vendor=vendor_context.is_new_vendor,
        is_duplicate=is_dup_confirmed,
        has_arithmetic_mismatch=has_arith_fail,
    )

    # 7. Risk calculation
    risk_result: RiskResult | None = None
    if (
        arith_result is not None
        and dup_result is not None
        and vendor_result is not None
        and policy_result is not None
    ):
        risk_result = calculate_invoice_risk(
            arithmetic=arith_result,
            duplicate=dup_result,
            vendor_history=vendor_result,
            policy=policy_result,
            invoice=invoice,
            high_value_threshold=resolved_policy.high_value_threshold,
            vendor_context=vendor_context,
        )
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
        vendor_context=vendor_context,
        approval_routing=approval_routing,
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
