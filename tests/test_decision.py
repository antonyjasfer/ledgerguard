"""Unit tests for the LedgerGuard decision engine.

Validates that the synthesize_decision function applies the correct precedence rules
based on tool evidence.
"""

import pytest

from app.agent.decision import build_evidence, synthesize_decision
from app.models.decision import AgentDecision, EvidenceItem
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    PolicyViolation,
    RiskLevel,
    RiskResult,
    RecommendedAction,
    VendorHistoryResult,
    VerificationStatus,
)


def test_synthesize_all_clean_auto_approve():
    """All checks passed, low risk -> AUTO_APPROVE."""
    arith = ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS)
    dup = DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE)
    vendor = VendorHistoryResult(vendor_id="V1", invoice_count=10, new_vendor=False)
    policy = PolicyVerificationResult(passed=True, should_block=False, requires_review=False, violations=[])
    risk = RiskResult(risk_score=5, risk_level=RiskLevel.LOW, recommended_action=RecommendedAction.AUTO_APPROVE)

    decision = synthesize_decision(arith, dup, vendor, policy, risk)
    assert decision.decision == AgentDecision.AUTO_APPROVE
    assert decision.requires_human is False
    assert len(decision.evidence) == 5


def test_synthesize_confirmed_duplicate_block():
    """Confirmed duplicate -> BLOCK regardless of other results."""
    arith = ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS)
    dup = DuplicateCheckResult(status=DuplicateStatus.CONFIRMED_DUPLICATE, matched_invoice_ids=["H1"])
    policy = PolicyVerificationResult(passed=True, should_block=False, requires_review=False, violations=[])
    risk = RiskResult(risk_score=5, risk_level=RiskLevel.LOW, recommended_action=RecommendedAction.AUTO_APPROVE)

    decision = synthesize_decision(arith, dup, policy=policy, risk=risk)
    assert decision.decision == AgentDecision.BLOCK
    assert decision.requires_human is True


def test_synthesize_policy_block():
    """Policy block -> BLOCK."""
    arith = ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS)
    dup = DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE)
    policy = PolicyVerificationResult(
        passed=False, should_block=True, requires_review=True,
        violations=[PolicyViolation(rule="AMOUNT_OVER_LIMIT", observed_value="X", threshold="Y", action="BLOCK")]
    )

    decision = synthesize_decision(arith, dup, policy=policy)
    assert decision.decision == AgentDecision.BLOCK
    assert decision.requires_human is True


def test_synthesize_critical_risk_block():
    """Critical risk -> BLOCK."""
    arith = ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS)
    dup = DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE)
    policy = PolicyVerificationResult(passed=True, should_block=False, requires_review=False, violations=[])
    risk = RiskResult(risk_score=95, risk_level=RiskLevel.CRITICAL, recommended_action=RecommendedAction.BLOCK)

    decision = synthesize_decision(arith, dup, policy=policy, risk=risk)
    assert decision.decision == AgentDecision.BLOCK


def test_synthesize_high_risk_manual_review():
    """High risk -> MANUAL_REVIEW."""
    arith = ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS)
    dup = DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE)
    policy = PolicyVerificationResult(passed=True, should_block=False, requires_review=False, violations=[])
    risk = RiskResult(risk_score=70, risk_level=RiskLevel.HIGH, recommended_action=RecommendedAction.MANUAL_REVIEW)

    decision = synthesize_decision(arith, dup, policy=policy, risk=risk)
    assert decision.decision == AgentDecision.MANUAL_REVIEW
    assert decision.requires_human is True


def test_synthesize_arithmetic_fail_review():
    """Arithmetic failure -> MANUAL_REVIEW (not AUTO_APPROVE)."""
    arith = ArithmeticVerificationResult(passed=False, status=VerificationStatus.FAIL)
    dup = DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE)
    risk = RiskResult(risk_score=10, risk_level=RiskLevel.LOW, recommended_action=RecommendedAction.AUTO_APPROVE)

    decision = synthesize_decision(arith, dup, risk=risk)
    assert decision.decision == AgentDecision.MANUAL_REVIEW
    assert decision.requires_human is True


def test_synthesize_no_evidence_review():
    """No evidence at all -> MANUAL_REVIEW."""
    decision = synthesize_decision()
    assert decision.decision == AgentDecision.MANUAL_REVIEW
    assert "Insufficient" in (decision.human_review_reason or "")


def test_synthesize_policy_requires_review():
    """Policy requires review (but not block) -> MANUAL_REVIEW."""
    arith = ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS)
    dup = DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE)
    policy = PolicyVerificationResult(
        passed=False, should_block=False, requires_review=True,
        violations=[PolicyViolation(rule="HIGH_VALUE_REVIEW", observed_value="X", threshold="Y", action="REVIEW")]
    )
    risk = RiskResult(risk_score=10, risk_level=RiskLevel.LOW, recommended_action=RecommendedAction.AUTO_APPROVE)

    decision = synthesize_decision(arith, dup, policy=policy, risk=risk)
    assert decision.decision == AgentDecision.MANUAL_REVIEW


def test_build_evidence_empty():
    """No results -> empty evidence list."""
    evidence = build_evidence()
    assert evidence == []


def test_build_evidence_complete():
    """All results -> 5 evidence items."""
    evidence = build_evidence(
        ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS),
        DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE),
        VendorHistoryResult(vendor_id="V1", invoice_count=5, new_vendor=False),
        PolicyVerificationResult(passed=True, should_block=False, requires_review=False, violations=[]),
        RiskResult(risk_score=5, risk_level=RiskLevel.LOW, recommended_action=RecommendedAction.AUTO_APPROVE),
    )
    assert len(evidence) == 5
    assert all(isinstance(e, EvidenceItem) for e in evidence)
