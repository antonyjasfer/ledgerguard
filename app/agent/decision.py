"""Deterministic decision synthesis and evidence collection for LedgerGuard.

Translates deterministic tool outputs, policy evaluations, approval routing,
and vendor context into a final structured VerificationDecision.
Enforces strict precedence rules. Zero LLM reliance for decision logic.
"""

from app.models.decision import AgentDecision, EvidenceItem, VerificationDecision
from app.models.policy import ApprovalMatrixResult
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    RiskLevel,
    RiskResult,
    VendorContextResult,
    VendorHistoryResult,
    VerificationStatus,
)


def build_evidence(
    arithmetic: ArithmeticVerificationResult | None = None,
    duplicate: DuplicateCheckResult | None = None,
    vendor: VendorHistoryResult | None = None,
    policy: PolicyVerificationResult | None = None,
    risk: RiskResult | None = None,
    vendor_context: VendorContextResult | None = None,
    approval_routing: ApprovalMatrixResult | None = None,
) -> list[EvidenceItem]:
    """Collect tool results into a structured list of EvidenceItem objects."""
    evidence: list[EvidenceItem] = []

    if arithmetic is not None:
        evidence.append(
            EvidenceItem(
                source="calculate_invoice_arithmetic",
                finding=arithmetic.status.value,
                details={
                    "passed": arithmetic.passed,
                    "expected_subtotal": str(arithmetic.expected_subtotal) if arithmetic.expected_subtotal is not None else None,
                    "actual_subtotal": str(arithmetic.actual_subtotal) if arithmetic.actual_subtotal is not None else None,
                    "expected_tax": str(arithmetic.expected_tax) if arithmetic.expected_tax is not None else None,
                    "actual_tax": str(arithmetic.actual_tax) if arithmetic.actual_tax is not None else None,
                    "expected_discount": str(arithmetic.expected_discount) if arithmetic.expected_discount is not None else None,
                    "actual_discount": str(arithmetic.actual_discount) if arithmetic.actual_discount is not None else None,
                    "expected_shipping": str(arithmetic.expected_shipping) if arithmetic.expected_shipping is not None else None,
                    "actual_shipping": str(arithmetic.actual_shipping) if arithmetic.actual_shipping is not None else None,
                    "expected_total": str(arithmetic.expected_total) if arithmetic.expected_total is not None else None,
                    "actual_total": str(arithmetic.actual_total) if arithmetic.actual_total is not None else None,
                    "difference": str(arithmetic.difference) if arithmetic.difference is not None else None,
                    "details": arithmetic.details,
                },
            )
        )

    if duplicate is not None:
        evidence.append(
            EvidenceItem(
                source="check_duplicate_invoice",
                finding=duplicate.status.value,
                details={
                    "matched_invoice_ids": duplicate.matched_invoice_ids,
                    "match_reasons": duplicate.match_reasons,
                },
            )
        )

    if vendor is not None:
        evidence.append(
            EvidenceItem(
                source="get_vendor_history",
                finding="NEW_VENDOR" if vendor.new_vendor else "ESTABLISHED_VENDOR",
                details={
                    "invoice_count": vendor.invoice_count,
                    "new_vendor": vendor.new_vendor,
                },
            )
        )

    if vendor_context is not None:
        evidence.append(
            EvidenceItem(
                source="get_vendor_context",
                finding="MASTER_MATCH" if vendor_context.vendor_exists else "UNREGISTERED_VENDOR",
                details={
                    "vendor_id": vendor_context.vendor_id,
                    "vendor_name": vendor_context.vendor_name,
                    "status": vendor_context.status,
                    "onboarding_status": vendor_context.onboarding_status,
                    "bank_verification_status": vendor_context.bank_verification_status,
                    "po_required": vendor_context.po_required,
                    "missing_po": vendor_context.missing_po,
                    "currency_supported": vendor_context.currency_supported,
                    "historical_invoice_count": vendor_context.historical_invoice_count,
                    "historical_average": str(vendor_context.historical_average) if vendor_context.historical_average is not None else None,
                    "historical_largest": str(vendor_context.historical_largest) if vendor_context.historical_largest is not None else None,
                    "normal_range_min": str(vendor_context.normal_range_min) if vendor_context.normal_range_min is not None else None,
                    "normal_range_max": str(vendor_context.normal_range_max) if vendor_context.normal_range_max is not None else None,
                    "deviation_factor": str(vendor_context.deviation_factor) if vendor_context.deviation_factor is not None else None,
                    "is_above_normal_range": vendor_context.is_above_normal_range,
                    "details": vendor_context.details,
                },
            )
        )

    if policy is not None:
        violations = [v.rule for v in policy.violations]
        evidence.append(
            EvidenceItem(
                source="evaluate_invoice_policy",
                finding="BLOCK" if policy.should_block else ("REVIEW" if policy.requires_review else "PASS"),
                details={
                    "passed": policy.passed,
                    "should_block": policy.should_block,
                    "requires_review": policy.requires_review,
                    "violations": violations,
                    "rules_evaluated": policy.rules_evaluated,
                },
            )
        )

    if approval_routing is not None:
        evidence.append(
            EvidenceItem(
                source="evaluate_approval_matrix",
                finding=approval_routing.tier.value,
                details={
                    "tier": approval_routing.tier.value,
                    "reason": approval_routing.reason,
                    "threshold_applied": str(approval_routing.threshold_applied) if approval_routing.threshold_applied is not None else None,
                },
            )
        )

    if risk is not None:
        evidence.append(
            EvidenceItem(
                source="calculate_invoice_risk",
                finding=risk.risk_level.value,
                details={
                    "risk_score": risk.risk_score,
                    "risk_level": risk.risk_level.value,
                    "risk_factors": risk.risk_factors,
                    "recommended_action": risk.recommended_action.value,
                },
            )
        )

    return evidence


def synthesize_decision(
    arithmetic: ArithmeticVerificationResult | None = None,
    duplicate: DuplicateCheckResult | None = None,
    vendor: VendorHistoryResult | None = None,
    policy: PolicyVerificationResult | None = None,
    risk: RiskResult | None = None,
    tools_called: list[str] | None = None,
    agent_summary: str = "",
    vendor_context: VendorContextResult | None = None,
    approval_routing: ApprovalMatrixResult | None = None,
) -> VerificationDecision:
    """Produce the final VerificationDecision applying strict precedence rules.

    Decision Precedence (highest to lowest):
    1. CONFIRMED_DUPLICATE -> BLOCK
    2. Policy block -> BLOCK
    3. CRITICAL risk -> BLOCK
    4. Arithmetic mismatch (if policy dictates BLOCK) -> BLOCK
    5. HIGH risk -> MANUAL_REVIEW
    6. Policy requires review -> MANUAL_REVIEW
    7. MEDIUM risk -> MANUAL_REVIEW
    8. Insufficient evidence -> MANUAL_REVIEW
    9. LOW risk + all checks passed -> AUTO_APPROVE
    """
    evidence = build_evidence(
        arithmetic=arithmetic,
        duplicate=duplicate,
        vendor=vendor,
        policy=policy,
        risk=risk,
        vendor_context=vendor_context,
        approval_routing=approval_routing,
    )
    called = tools_called or []

    # 1. CONFIRMED_DUPLICATE -> BLOCK
    if duplicate is not None and duplicate.status == DuplicateStatus.CONFIRMED_DUPLICATE:
        return VerificationDecision(
            decision=AgentDecision.BLOCK,
            confidence="EVIDENCE_BASED",
            summary=agent_summary or "Confirmed duplicate invoice detected. Payment blocked.",
            evidence=evidence,
            risk_level=RiskLevel.CRITICAL if risk is None else risk.risk_level,
            risk_score=100 if risk is None else risk.risk_score,
            tools_called=called,
            requires_human=True,
            human_review_reason="Confirmed duplicate invoice requires investigation before resubmission.",
        )

    # 2. Policy block -> BLOCK
    if policy is not None and policy.should_block:
        return VerificationDecision(
            decision=AgentDecision.BLOCK,
            confidence="EVIDENCE_BASED",
            summary=agent_summary or "Invoice blocked by corporate AP policy.",
            evidence=evidence,
            risk_level=risk.risk_level if risk else None,
            risk_score=risk.risk_score if risk else None,
            tools_called=called,
            requires_human=True,
            human_review_reason="Policy-mandated block. " + "; ".join(v.rule for v in policy.violations),
        )

    # 3. CRITICAL risk -> BLOCK
    if risk is not None and risk.risk_level == RiskLevel.CRITICAL:
        return VerificationDecision(
            decision=AgentDecision.BLOCK,
            confidence="EVIDENCE_BASED",
            summary=agent_summary or "Critical risk level detected. Payment blocked.",
            evidence=evidence,
            risk_level=risk.risk_level,
            risk_score=risk.risk_score,
            tools_called=called,
            requires_human=True,
            human_review_reason="Critical risk score requires human investigation.",
        )

    # 4-7. HIGH / MEDIUM risk or policy review or arithmetic fail -> MANUAL_REVIEW
    needs_review = False
    review_reasons: list[str] = []

    if risk is not None and risk.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
        needs_review = True
        review_reasons.append(f"Risk level: {risk.risk_level.value} (Score: {risk.risk_score})")

    if policy is not None and policy.requires_review:
        needs_review = True
        review_reasons.extend(v.rule for v in policy.violations)

    if arithmetic is not None and not arithmetic.passed:
        needs_review = True
        review_reasons.append("Arithmetic verification failed")

    # 8. Insufficient evidence -> MANUAL_REVIEW
    if arithmetic is None and duplicate is None:
        needs_review = True
        review_reasons.append("Insufficient verification evidence")

    if needs_review:
        return VerificationDecision(
            decision=AgentDecision.MANUAL_REVIEW,
            confidence="PARTIAL_EVIDENCE" if (arithmetic is None or duplicate is None) else "EVIDENCE_BASED",
            summary=agent_summary or "Invoice requires manual human review.",
            evidence=evidence,
            risk_level=risk.risk_level if risk else None,
            risk_score=risk.risk_score if risk else None,
            tools_called=called,
            requires_human=True,
            human_review_reason="; ".join(review_reasons),
        )

    # 9. LOW risk + all checks passed -> AUTO_APPROVE
    return VerificationDecision(
        decision=AgentDecision.AUTO_APPROVE,
        confidence="EVIDENCE_BASED",
        summary=agent_summary or "All verification checks passed. Invoice approved for payment.",
        evidence=evidence,
        risk_level=risk.risk_level if risk else RiskLevel.LOW,
        risk_score=risk.risk_score if risk else 0,
        tools_called=called,
        requires_human=False,
        human_review_reason=None,
    )
