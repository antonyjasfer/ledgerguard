"""Unit tests for deterministic AP policy evaluation engine.

Tests auto-approval limits, high-value thresholds, new-vendor reviews,
confirmed duplicate blocking, boundary amounts, and multiple simultaneous violations.
"""

from datetime import date
from decimal import Decimal
import pytest

from app.models.invoice import Invoice
from app.models.policy import PolicyConfig
from app.models.verification import (
    DuplicateCheckResult,
    DuplicateStatus,
    VendorHistoryResult,
)
from app.tools.policy import evaluate_invoice_policy
from tests.fixtures import (
    get_clean_invoice,
    get_high_value_invoice,
    get_policy_violation_invoice,
    get_boundary_invoice,
)


@pytest.fixture
def clean_vendor_history() -> VendorHistoryResult:
    """Established vendor profile with history."""
    return VendorHistoryResult(
        vendor_id="VEND-ACME-01",
        invoice_count=5,
        total_spend={"USD": Decimal("2500.00")},
        new_vendor=False,
    )


@pytest.fixture
def no_duplicate_result() -> DuplicateCheckResult:
    """Clean duplicate detection result."""
    return DuplicateCheckResult(
        status=DuplicateStatus.NO_DUPLICATE,
        matched_invoice_ids=[],
    )


def test_policy_clean_invoice_passes(clean_vendor_history, no_duplicate_result):
    """Verify standard low-value invoice passes policy without review or block."""
    inv = get_clean_invoice()  # total 220.00 <= 1000.00 auto-approval limit
    result = evaluate_invoice_policy(inv, clean_vendor_history, no_duplicate_result)

    assert result.passed is True
    assert result.requires_review is False
    assert result.should_block is False
    assert len(result.violations) == 0


def test_policy_high_value_triggers_review(clean_vendor_history, no_duplicate_result):
    """Verify invoice meeting or exceeding high-value threshold ($5000) requires review."""
    inv = get_high_value_invoice()  # total 11000.00 >= 5000.00
    result = evaluate_invoice_policy(inv, clean_vendor_history, no_duplicate_result)

    assert result.passed is False
    assert result.requires_review is True
    assert result.should_block is False
    assert any(v.rule == "HIGH_VALUE_THRESHOLD" for v in result.violations)


def test_policy_auto_approval_ceiling_exceeded(clean_vendor_history, no_duplicate_result):
    """Verify invoice above auto-approval limit ($1000) but below high value ($5000) triggers review."""
    inv = get_policy_violation_invoice()  # total 2200.00
    result = evaluate_invoice_policy(inv, clean_vendor_history, no_duplicate_result)

    assert result.passed is False
    assert result.requires_review is True
    assert result.should_block is False
    assert any(v.rule == "AUTO_APPROVAL_LIMIT" for v in result.violations)
    assert not any(v.rule == "HIGH_VALUE_THRESHOLD" for v in result.violations)


def test_policy_new_vendor_triggers_review(no_duplicate_result):
    """Verify new vendor triggers review policy even for low-value invoice."""
    inv = get_clean_invoice()  # 220.00
    new_vendor_history = VendorHistoryResult(
        vendor_id="VEND-NEW-01",
        invoice_count=0,
        new_vendor=True,
    )

    result = evaluate_invoice_policy(inv, new_vendor_history, no_duplicate_result)
    assert result.passed is False
    assert result.requires_review is True
    assert any(v.rule == "NEW_VENDOR_REVIEW" for v in result.violations)


def test_policy_confirmed_duplicate_blocks(clean_vendor_history):
    """Verify confirmed duplicate triggers immediate payment block."""
    inv = get_clean_invoice()
    confirmed_dup = DuplicateCheckResult(
        status=DuplicateStatus.CONFIRMED_DUPLICATE,
        matched_invoice_ids=["HIST-001"],
    )

    result = evaluate_invoice_policy(inv, clean_vendor_history, confirmed_dup)
    assert result.passed is False
    assert result.should_block is True
    assert any(v.rule == "DUPLICATE_BLOCK" for v in result.violations)


def test_policy_possible_duplicate_requires_review(clean_vendor_history):
    """Verify possible duplicate triggers manual review without immediate block."""
    inv = get_clean_invoice()
    possible_dup = DuplicateCheckResult(
        status=DuplicateStatus.POSSIBLE_DUPLICATE,
        matched_invoice_ids=["HIST-002"],
    )

    result = evaluate_invoice_policy(inv, clean_vendor_history, possible_dup)
    assert result.passed is False
    assert result.requires_review is True
    assert result.should_block is False
    assert any(v.rule == "POSSIBLE_DUPLICATE_REVIEW" for v in result.violations)


def test_policy_boundary_threshold_inclusiveness(clean_vendor_history, no_duplicate_result):
    """Verify exact boundaries: 1000.00, 1000.01, 4999.99, 5000.00."""
    config = PolicyConfig(
        auto_approval_limit=Decimal("1000.00"),
        high_value_threshold=Decimal("5000.00"),
    )

    # 1. Exactly 1000.00: Not > 1000.00, so auto-approval passes
    inv_1000 = get_boundary_invoice(Decimal("1000.00"))
    res_1000 = evaluate_invoice_policy(inv_1000, clean_vendor_history, no_duplicate_result, config=config)
    assert res_1000.passed is True
    assert res_1000.requires_review is False

    # 2. 1000.01: > 1000.00, so triggers AUTO_APPROVAL_LIMIT review
    inv_1000_01 = get_boundary_invoice(Decimal("1000.01"))
    res_1000_01 = evaluate_invoice_policy(inv_1000_01, clean_vendor_history, no_duplicate_result, config=config)
    assert res_1000_01.passed is False
    assert res_1000_01.requires_review is True
    assert any(v.rule == "AUTO_APPROVAL_LIMIT" for v in res_1000_01.violations)

    # 3. 4999.99: < 5000.00, triggers AUTO_APPROVAL_LIMIT but NOT HIGH_VALUE_THRESHOLD
    inv_4999_99 = get_boundary_invoice(Decimal("4999.99"))
    res_4999_99 = evaluate_invoice_policy(inv_4999_99, clean_vendor_history, no_duplicate_result, config=config)
    assert any(v.rule == "AUTO_APPROVAL_LIMIT" for v in res_4999_99.violations)
    assert not any(v.rule == "HIGH_VALUE_THRESHOLD" for v in res_4999_99.violations)

    # 4. Exactly 5000.00: >= 5000.00, triggers HIGH_VALUE_THRESHOLD
    inv_5000 = get_boundary_invoice(Decimal("5000.00"))
    res_5000 = evaluate_invoice_policy(inv_5000, clean_vendor_history, no_duplicate_result, config=config)
    assert any(v.rule == "HIGH_VALUE_THRESHOLD" for v in res_5000.violations)


def test_policy_multiple_violations_retained():
    """Verify multiple concurrent violations are all preserved without overwriting."""
    inv = get_high_value_invoice()  # 11000.00
    new_vendor = VendorHistoryResult(vendor_id="VEND-NEW-01", invoice_count=0, new_vendor=True)
    dup = DuplicateCheckResult(status=DuplicateStatus.CONFIRMED_DUPLICATE, matched_invoice_ids=["HIST-X"])

    result = evaluate_invoice_policy(inv, new_vendor, dup)
    assert result.should_block is True
    assert result.requires_review is True
    rule_names = {v.rule for v in result.violations}
    assert "DUPLICATE_BLOCK" in rule_names
    assert "HIGH_VALUE_THRESHOLD" in rule_names
    assert "AUTO_APPROVAL_LIMIT" in rule_names
    assert "NEW_VENDOR_REVIEW" in rule_names
