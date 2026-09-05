"""Decision engine for LedgerGuard.

Integrates all verification results into a single structured VerificationDecision.
This module aggregates evidence but does NOT re-compute risk; it reads the risk
engine output and applies decision precedence rules.
"""

from app.models.decision import AgentDecision, EvidenceItem, VerificationDecision
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    RecommendedAction,
    RiskLevel,
    RiskResult,
    VendorHistoryResult,
    VerificationStatus,
)


def build_evidence(
    arithmetic: ArithmeticVerificationResult | None = None,
    duplicate: DuplicateCheckResult | None = None,
    vendor: VendorHistoryResult | None = None,
    policy: PolicyVerificationResult | None = None,
    risk: RiskResult | None = None,
) -> list[EvidenceItem]:
    """Compile evidence items from available verification tool results."""
    evidence: list[EvidenceItem] = []

    if arithmetic is not None:
        evidence.append(EvidenceItem(
            source="calculate_invoice_arithmetic",
            finding=arithmetic.status.value,
            details={
                "passed": arithmetic.passed,
                "expected_total": str(arithmetic.expected_total) if arithmetic.expected_total is not None else None,
                "actual_total": str(arithmetic.actual_total) if arithmetic.actual_total is not None else None,
                "difference": str(arithmetic.difference) if arithmetic.difference is not None else None,
            },
        ))

    if duplicate is not None:
        evidence.append(EvidenceItem(
            source="check_duplicate_invoice",
            finding=duplicate.status.value,
            details={
                "matched_invoice_ids": duplicate.matched_invoice_ids,
                "match_reasons": duplicate.match_reasons,
            },
        ))

    if vendor is not None:
        evidence.append(EvidenceItem(
            source="get_vendor_history",
            finding="NEW_VENDOR" if vendor.new_vendor else "ESTABLISHED_VENDOR",
            details={
                "invoice_count": vendor.invoice_count,
                "new_vendor": vendor.new_vendor,
            },
        ))

    if policy is not None:
        violations = [v.rule for v in policy.violations]
        evidence.append(EvidenceItem(
            source="evaluate_invoice_policy",
            finding="BLOCK" if policy.should_block else ("REVIEW" if policy.requires_review else "PASS"),
            details={
                "passed": policy.passed,
                "should_block": policy.should_block,
                "requires_review": policy.requires_review,
                "violations": violations,
            },
        ))

    if risk is not None:
        evidence.append(EvidenceItem(
            source="calculate_invoice_risk",
            finding=risk.risk_level.value,
            details={
                "risk_score": risk.risk_score,
                "risk_level": risk.risk_level.value,
                "risk_factors": risk.risk_factors,
                "recommended_action": risk.recommended_action.value,
            },
        ))

    return evidence


def synthesize_decision(
    arithmetic: ArithmeticVerificationResult | None = None,
    duplicate: DuplicateCheckResult | None = None,
    vendor: VendorHistoryResult | None = None,
    policy: PolicyVerificationResult | None = None,
    risk: RiskResult | None = None,
    tools_called: list[str] | None = None,
    agent_summary: str = "",
) -> VerificationDecision:
    """Produce the final VerificationDecision applying strict precedence rules.

    Decision Precedence (highest to lowest):
    1. CONFIRMED_DUPLICATE -> BLOCK
    2. Policy block -> BLOCK
    3. CRITICAL risk -> BLOCK
    4. HIGH risk -> MANUAL_REVIEW
    5. Policy requires review -> MANUAL_REVIEW
    6. MEDIUM risk -> MANUAL_REVIEW
    7. Insufficient evidence -> MANUAL_REVIEW
    8. LOW risk + all checks passed -> AUTO_APPROVE
    """
    evidence = build_evidence(arithmetic, duplicate, vendor, policy, risk)
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

    # 4-6. HIGH / MEDIUM risk or policy review -> MANUAL_REVIEW
    needs_review = False
    review_reasons: list[str] = []

    if risk is not None and risk.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
        needs_review = True
        review_reasons.append(f"Risk level: {risk.risk_level.value}")

    if policy is not None and policy.requires_review:
        needs_review = True
        review_reasons.extend(v.rule for v in policy.violations)

    if arithmetic is not None and not arithmetic.passed:
        needs_review = True
        review_reasons.append("Arithmetic verification failed")

    # 7. Insufficient evidence -> MANUAL_REVIEW
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

    # 8. LOW risk + all checks passed -> AUTO_APPROVE
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
