"""Unit tests for deterministic AP invoice risk scoring engine.

Tests risk tiers (LOW, MEDIUM, HIGH, CRITICAL), factor point contributions,
score capping at 100, mandatory critical override on confirmed duplicate,
and action precedence.
"""

from decimal import Decimal
import pytest

from app.models.invoice import Invoice
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    PolicyViolation,
    RecommendedAction,
    RiskLevel,
    VendorHistoryResult,
    VerificationStatus,
)
from app.tools.risk import RiskWeights, calculate_invoice_risk
from tests.fixtures import get_clean_invoice, get_high_value_invoice


@pytest.fixture
def clean_arithmetic() -> ArithmeticVerificationResult:
    return ArithmeticVerificationResult(
        passed=True,
        status=VerificationStatus.PASS,
        expected_total=Decimal("220.00"),
        actual_total=Decimal("220.00"),
        difference=Decimal("0.00"),
    )


@pytest.fixture
def failed_arithmetic() -> ArithmeticVerificationResult:
    return ArithmeticVerificationResult(
        passed=False,
        status=VerificationStatus.FAIL,
        expected_total=Decimal("220.00"),
        actual_total=Decimal("250.00"),
        difference=Decimal("30.00"),
    )


@pytest.fixture
def clean_duplicate() -> DuplicateCheckResult:
    return DuplicateCheckResult(
        status=DuplicateStatus.NO_DUPLICATE,
        matched_invoice_ids=[],
    )


@pytest.fixture
def clean_vendor() -> VendorHistoryResult:
    return VendorHistoryResult(
        vendor_id="VEND-01",
        invoice_count=5,
        new_vendor=False,
    )


@pytest.fixture
def clean_policy() -> PolicyVerificationResult:
    return PolicyVerificationResult(
        passed=True,
        requires_review=False,
        should_block=False,
        violations=[],
    )


def test_risk_clean_invoice_is_low(
    clean_arithmetic, clean_duplicate, clean_vendor, clean_policy
):
    """Verify clean invoice yields score 0, LOW risk, and AUTO_APPROVE."""
    inv = get_clean_invoice()  # 220.00
    res = calculate_invoice_risk(
        clean_arithmetic, clean_duplicate, clean_vendor, clean_policy, inv
    )

    assert res.risk_score == 0
    assert res.risk_level == RiskLevel.LOW
    assert res.risk_factors == []
    assert res.recommended_action == RecommendedAction.AUTO_APPROVE


def test_risk_single_factor_new_vendor(
    clean_arithmetic, clean_duplicate, clean_policy
):
    """Verify single factor (new vendor = 20) yields score 20, LOW risk, MANUAL_REVIEW due to policy."""
    inv = get_clean_invoice()
    new_vendor = VendorHistoryResult(vendor_id="VEND-NEW", invoice_count=0, new_vendor=True)
    policy_with_review = PolicyVerificationResult(
        passed=False, requires_review=True, should_block=False, violations=[
            PolicyViolation(rule="NEW_VENDOR_REVIEW", observed_value="True", threshold="False", action="MANUAL_REVIEW")
        ]
    )

    res = calculate_invoice_risk(
        clean_arithmetic, clean_duplicate, new_vendor, policy_with_review, inv
    )

    # 20 (new_vendor) + 30 (policy_violation) = 50 -> HIGH risk, MANUAL_REVIEW
    assert "NEW_VENDOR" in res.risk_factors
    assert "POLICY_VIOLATION" in res.risk_factors
    assert res.risk_score == 50
    assert res.risk_level == RiskLevel.HIGH
    assert res.recommended_action == RecommendedAction.MANUAL_REVIEW


def test_risk_arithmetic_mismatch(
    failed_arithmetic, clean_duplicate, clean_vendor, clean_policy
):
    """Verify arithmetic mismatch (+50) alone reaches HIGH risk."""
    inv = get_clean_invoice()
    res = calculate_invoice_risk(
        failed_arithmetic, clean_duplicate, clean_vendor, clean_policy, inv
    )

    assert res.risk_score == 50
    assert res.risk_level == RiskLevel.HIGH
    assert "ARITHMETIC_MISMATCH" in res.risk_factors
    assert res.recommended_action == RecommendedAction.MANUAL_REVIEW


def test_risk_confirmed_duplicate_critical_override(
    clean_arithmetic, clean_vendor, clean_policy
):
    """Verify confirmed duplicate triggers mandatory CRITICAL override and BLOCK."""
    inv = get_clean_invoice()
    confirmed_dup = DuplicateCheckResult(
        status=DuplicateStatus.CONFIRMED_DUPLICATE,
        matched_invoice_ids=["HIST-001"],
    )

    res = calculate_invoice_risk(
        clean_arithmetic, confirmed_dup, clean_vendor, clean_policy, inv
    )

    assert res.risk_score == 100
    assert res.risk_level == RiskLevel.CRITICAL
    assert "CONFIRMED_DUPLICATE" in res.risk_factors
    assert res.recommended_action == RecommendedAction.BLOCK


def test_risk_score_capped_at_100():
    """Verify sum of multiple active factors exceeding 100 is strictly capped at 100."""
    arithmetic_fail = ArithmeticVerificationResult(passed=False, status=VerificationStatus.FAIL)
    dup_possible = DuplicateCheckResult(status=DuplicateStatus.POSSIBLE_DUPLICATE, matched_invoice_ids=["H1"])
    new_vendor = VendorHistoryResult(vendor_id="V1", new_vendor=True)
    policy_viol = PolicyVerificationResult(passed=False, violations=[PolicyViolation(rule="R", observed_value="O", threshold="T", action="A")])
    high_inv = get_high_value_invoice()  # 11000.00

    # Points: arithmetic(50) + possible_dup(15) + new_vendor(20) + policy(30) + high_value(20) = 135
    res = calculate_invoice_risk(
        arithmetic_fail, dup_possible, new_vendor, policy_viol, high_inv
    )

    assert res.risk_score == 100
    assert res.risk_level == RiskLevel.CRITICAL
    assert res.recommended_action == RecommendedAction.BLOCK


def test_risk_policy_blocking_precedence(
    clean_arithmetic, clean_duplicate, clean_vendor
):
    """Verify policy blocking mandates BLOCK even if score is low."""
    inv = get_clean_invoice()
    blocking_policy = PolicyVerificationResult(
        passed=False,
        requires_review=True,
        should_block=True,
        violations=[PolicyViolation(rule="CUSTOM_BLOCK", observed_value="X", threshold="Y", action="BLOCK")],
    )

    res = calculate_invoice_risk(
        clean_arithmetic, clean_duplicate, clean_vendor, blocking_policy, inv
    )

    assert res.recommended_action == RecommendedAction.BLOCK
