"""Deterministic policy evaluation engine for LedgerGuard invoices.

Evaluates an invoice against centralized corporate Accounts Payable policies.
Checks duplicate blocks, high-value thresholds, auto-approval ceilings, new-vendor rules,
missing PO requirements, unsupported currencies, large discounts, and required fields.
Zero LLM reliance, deterministic evidence-based rules.
"""

from decimal import Decimal

from app.models.invoice import Invoice
from app.models.policy import PolicyConfig
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    PolicyViolation,
    VendorContextResult,
    VendorHistoryResult,
)


def evaluate_invoice_policy(
    invoice: Invoice,
    vendor_history: VendorHistoryResult,
    duplicate_result: DuplicateCheckResult,
    config: PolicyConfig | None = None,
    vendor_context: VendorContextResult | None = None,
    arithmetic_result: ArithmeticVerificationResult | None = None,
) -> PolicyVerificationResult:
    """Evaluate candidate invoice against corporate AP approval and blocking policies.

    Args:
        invoice: The invoice to evaluate.
        vendor_history: Historical profile for the vendor.
        duplicate_result: Duplicate detection output for the candidate invoice.
        config: Centralized policy configuration (uses defaults if None).
        vendor_context: Optional deterministic vendor master comparison.
        arithmetic_result: Optional arithmetic check result for blocking rules.

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

    # 3. Arithmetic Mismatch Rule (if configured to block, triggers BLOCK violation)
    if arithmetic_result is not None and not arithmetic_result.passed:
        rules_evaluated.append("ARITHMETIC_MISMATCH")
        if cfg.arithmetic_mismatch_requires_block:
            should_block = True
            violations.append(
                PolicyViolation(
                    rule="ARITHMETIC_MISMATCH",
                    observed_value=f"discrepancy={arithmetic_result.difference}",
                    threshold=f"<={cfg.arithmetic_tolerance}",
                    action="BLOCK",
                )
            )

    # 4. High-Value Threshold Rule (inclusivity: amount >= threshold)
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

    # 5. Auto-Approval Limit Rule (inclusivity: amount > threshold triggers review)
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

    # 6. New Vendor Verification Rule
    rules_evaluated.append("NEW_VENDOR_REVIEW")
    if vendor_context is not None:
        is_new = vendor_context.is_new_vendor
    else:
        is_new = vendor_history.new_vendor

    if is_new and cfg.new_vendor_requires_review:
        requires_review = True
        violations.append(
            PolicyViolation(
                rule="NEW_VENDOR_REVIEW",
                observed_value="new_vendor=True",
                threshold="existing_vendor",
                action="MANUAL_REVIEW",
            )
        )

    # 7. Unsupported Currency Rule
    rules_evaluated.append("UNSUPPORTED_CURRENCY_REVIEW")
    if cfg.unsupported_currency_requires_review and invoice.currency:
        supported_uppers = [c.upper() for c in cfg.supported_currencies]
        if invoice.currency.upper() not in supported_uppers:
            requires_review = True
            violations.append(
                PolicyViolation(
                    rule="UNSUPPORTED_CURRENCY_REVIEW",
                    observed_value=invoice.currency,
                    threshold=f"in {cfg.supported_currencies}",
                    action="MANUAL_REVIEW",
                )
            )
        elif vendor_context and vendor_context.vendor_exists and not vendor_context.currency_supported:
            requires_review = True
            violations.append(
                PolicyViolation(
                    rule="UNSUPPORTED_CURRENCY_REVIEW",
                    observed_value=invoice.currency,
                    threshold=f"in vendor approved {vendor_context.approved_currencies}",
                    action="MANUAL_REVIEW",
                )
            )

    # 8. Missing Purchase Order Rule
    rules_evaluated.append("MISSING_PO_REVIEW")
    if cfg.missing_po_requires_review and vendor_context and vendor_context.missing_po:
        requires_review = True
        violations.append(
            PolicyViolation(
                rule="MISSING_PO_REVIEW",
                observed_value="PO missing",
                threshold="PO required",
                action="MANUAL_REVIEW",
            )
        )

    # 9. Large Discount Rule
    rules_evaluated.append("LARGE_DISCOUNT_REVIEW")
    if (
        cfg.large_discount_requires_review
        and invoice.discount is not None
        and invoice.subtotal is not None
        and invoice.subtotal > Decimal("0.00")
    ):
        discount_pct = (invoice.discount / invoice.subtotal) * Decimal("100.00")
        if discount_pct > cfg.maximum_discount_percent:
            requires_review = True
            violations.append(
                PolicyViolation(
                    rule="LARGE_DISCOUNT_REVIEW",
                    observed_value=f"{discount_pct.quantize(Decimal('0.01'))}%",
                    threshold=f"<={cfg.maximum_discount_percent}%",
                    action="MANUAL_REVIEW",
                )
            )

    # 10. Vendor Approval / Onboarding Rule (evaluated if vendor exists in master)
    rules_evaluated.append("VENDOR_NOT_APPROVED")
    if vendor_context and vendor_context.vendor_exists:
        if (
            vendor_context.status in ("SUSPENDED", "INACTIVE")
            or vendor_context.onboarding_status == "REJECTED"
            or (not vendor_context.is_active and not vendor_context.is_new_vendor)
        ):
            requires_review = True
            violations.append(
                PolicyViolation(
                    rule="VENDOR_NOT_APPROVED",
                    observed_value=f"status={vendor_context.status}, onboarding={vendor_context.onboarding_status}",
                    threshold="ACTIVE / APPROVED",
                    action="MANUAL_REVIEW",
                )
            )

    # 11. Required Fields Rule (evaluated when configured)
    if cfg.required_fields:
        rules_evaluated.append("REQUIRED_FIELDS_CHECK")
        missing_fields: list[str] = []
        for field_name in cfg.required_fields:
            val = getattr(invoice, field_name, None)
            if val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, list) and len(val) == 0):
                missing_fields.append(field_name)

        if missing_fields:
            requires_review = True
            violations.append(
                PolicyViolation(
                    rule="REQUIRED_FIELDS_CHECK",
                    observed_value=f"missing: {', '.join(missing_fields)}",
                    threshold="all required fields populated",
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
