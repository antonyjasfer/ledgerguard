"""Deterministic policy evaluation engine for LedgerGuard invoices.

Evaluates an invoice against centralized corporate Accounts Payable policies.
Checks duplicate blocks, high-value thresholds, auto-approval ceilings, and new-vendor rules.
Zero LLM reliance, deterministic evidence-based rules.
"""

from decimal import Decimal

from app.models.invoice import Invoice
from app.models.policy import PolicyConfig
from app.models.verification import (
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    PolicyViolation,
    VendorHistoryResult,
)


def evaluate_invoice_policy(
    invoice: Invoice,
    vendor_history: VendorHistoryResult,
    duplicate_result: DuplicateCheckResult,
    config: PolicyConfig | None = None,
) -> PolicyVerificationResult:
    """Evaluate candidate invoice against AP approval and blocking policies.

    Args:
        invoice: The invoice to evaluate.
        vendor_history: Historical profile for the vendor.
        duplicate_result: Duplicate detection output for the candidate invoice.
        config: Centralized policy configuration (uses defaults if None).

    Returns:
        PolicyVerificationResult detailing pass/review/block decisions and violations.
    """
    cfg = config or PolicyConfig()
    violations: list[PolicyViolation] = []
    warnings: list[str] = []
    rules_evaluated: list[str] = []

    should_block = False
    requires_review = False

    # 1. Confirmed Duplicate Rule
    rules_evaluated.append("DUPLICATE_BLOCK")
    if duplicate_result.status == DuplicateStatus.CONFIRMED_DUPLICATE and cfg.duplicate_requires_block:
        should_block = True
        violations.append(
            PolicyViolation(
                rule="DUPLICATE_BLOCK",
                observed_value=duplicate_result.status.value,
                threshold="NO_DUPLICATE",
                action="BLOCK",
            )
        )

    # 2. Possible Duplicate Rule
    rules_evaluated.append("POSSIBLE_DUPLICATE_REVIEW")
    if (
        duplicate_result.status == DuplicateStatus.POSSIBLE_DUPLICATE
        and cfg.possible_duplicate_requires_review
    ):
        requires_review = True
        violations.append(
            PolicyViolation(
                rule="POSSIBLE_DUPLICATE_REVIEW",
                observed_value=duplicate_result.status.value,
                threshold="NO_DUPLICATE",
                action="MANUAL_REVIEW",
            )
        )

    # 3. High-Value Threshold Rule (inclusivity: amount >= threshold)
    rules_evaluated.append("HIGH_VALUE_THRESHOLD")
    if invoice.total is not None and invoice.total >= cfg.high_value_threshold:
        requires_review = True
        violations.append(
            PolicyViolation(
                rule="HIGH_VALUE_THRESHOLD",
                observed_value=f"{invoice.currency} {invoice.total}",
                threshold=f">={cfg.high_value_threshold}",
                action="MANUAL_REVIEW",
            )
        )

    # 4. Auto-Approval Limit Rule (inclusivity: amount > threshold triggers review)
    rules_evaluated.append("AUTO_APPROVAL_LIMIT")
    if invoice.total is not None and invoice.total > cfg.auto_approval_limit:
        requires_review = True
        violations.append(
            PolicyViolation(
                rule="AUTO_APPROVAL_LIMIT",
                observed_value=f"{invoice.currency} {invoice.total}",
                threshold=f"<={cfg.auto_approval_limit}",
                action="MANUAL_REVIEW",
            )
        )

    # 5. New Vendor Verification Rule
    rules_evaluated.append("NEW_VENDOR_REVIEW")
    if vendor_history.new_vendor and cfg.new_vendor_requires_review:
        requires_review = True
        violations.append(
            PolicyViolation(
                rule="NEW_VENDOR_REVIEW",
                observed_value="new_vendor=True",
                threshold="existing_vendor",
                action="MANUAL_REVIEW",
            )
        )

    # If missing total, flag as review requirement
    if invoice.total is None:
        requires_review = True
        warnings.append("Invoice total is missing or undetermined; manual review required.")

    passed = (len(violations) == 0 and not should_block and not requires_review)

    return PolicyVerificationResult(
        passed=passed,
        requires_review=requires_review,
        should_block=should_block,
        violations=violations,
        warnings=warnings,
        rules_evaluated=rules_evaluated,
    )
