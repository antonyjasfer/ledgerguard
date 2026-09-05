"""Unit tests for the LedgerGuard decision guard.

Validates that deterministic safety rules override the LLM agent's proposed decisions
when tool evidence contradicts the agent's recommendation.
"""

from decimal import Decimal
import pytest

from app.agent.decision_guard import DecisionGuardResult, validate_agent_decision
from app.models.decision import AgentDecision
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    PolicyViolation,
    RiskLevel,
    RiskResult,
    RecommendedAction,
    VerificationStatus,
)


def test_guard_clean_auto_approve_accepted():
    """Guard accepts AUTO_APPROVE when all evidence is clean."""
    arith = ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS)
    dup = DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE)
    policy = PolicyVerificationResult(passed=True, should_block=False, requires_review=False, violations=[])
    risk = RiskResult(risk_score=0, risk_level=RiskLevel.LOW, recommended_action=RecommendedAction.AUTO_APPROVE)

    result = validate_agent_decision(AgentDecision.AUTO_APPROVE, arith, dup, policy, risk)
    assert result.was_overridden is False
    assert result.final_decision == AgentDecision.AUTO_APPROVE


def test_guard_duplicate_overrides_auto_approve_to_block():
    """Guard overrides AUTO_APPROVE to BLOCK when confirmed duplicate exists."""
    dup = DuplicateCheckResult(status=DuplicateStatus.CONFIRMED_DUPLICATE, matched_invoice_ids=["H1"])

    result = validate_agent_decision(AgentDecision.AUTO_APPROVE, duplicate=dup)
    assert result.was_overridden is True
    assert result.final_decision == AgentDecision.BLOCK
    assert "CONFIRMED_DUPLICATE" in result.override_reason


def test_guard_arithmetic_fail_overrides_auto_approve_to_review():
    """Guard overrides AUTO_APPROVE to MANUAL_REVIEW when arithmetic fails."""
    arith = ArithmeticVerificationResult(passed=False, status=VerificationStatus.FAIL)

    result = validate_agent_decision(AgentDecision.AUTO_APPROVE, arithmetic=arith)
    assert result.was_overridden is True
    assert result.final_decision == AgentDecision.MANUAL_REVIEW
    assert "Arithmetic" in result.override_reason


def test_guard_critical_risk_overrides_auto_approve_to_block():
    """Guard overrides AUTO_APPROVE to BLOCK when risk is CRITICAL."""
    risk = RiskResult(risk_score=100, risk_level=RiskLevel.CRITICAL, recommended_action=RecommendedAction.BLOCK)

    result = validate_agent_decision(AgentDecision.AUTO_APPROVE, risk=risk)
    assert result.was_overridden is True
    assert result.final_decision == AgentDecision.BLOCK
    assert "CRITICAL" in result.override_reason


def test_guard_insufficient_data_overrides_auto_approve_to_review():
    """Guard overrides AUTO_APPROVE to MANUAL_REVIEW when data is insufficient."""
    arith = ArithmeticVerificationResult(passed=False, status=VerificationStatus.INSUFFICIENT_DATA)

    result = validate_agent_decision(AgentDecision.AUTO_APPROVE, arithmetic=arith)
    assert result.was_overridden is True
    assert result.final_decision == AgentDecision.MANUAL_REVIEW
    assert "INSUFFICIENT_DATA" in result.override_reason


def test_guard_policy_block_overrides_manual_review_to_block():
    """Guard overrides MANUAL_REVIEW to BLOCK when policy mandates block."""
    policy = PolicyVerificationResult(
        passed=False, should_block=True, requires_review=True,
        violations=[PolicyViolation(rule="DUPLICATE_BLOCK", observed_value="X", threshold="Y", action="BLOCK")]
    )

    result = validate_agent_decision(AgentDecision.MANUAL_REVIEW, policy=policy)
    assert result.was_overridden is True
    assert result.final_decision == AgentDecision.BLOCK
    assert "Policy" in result.override_reason


def test_guard_block_not_overridden_by_clean_evidence():
    """Guard does not downgrade BLOCK even if evidence is clean."""
    arith = ArithmeticVerificationResult(passed=True, status=VerificationStatus.PASS)
    dup = DuplicateCheckResult(status=DuplicateStatus.NO_DUPLICATE)

    result = validate_agent_decision(AgentDecision.BLOCK, arith, dup)
    assert result.was_overridden is False
    assert result.final_decision == AgentDecision.BLOCK
