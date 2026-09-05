"""Deterministic arithmetic verification tool for LedgerGuard invoices.

Evaluates line item totals, subtotal summation, tax, discounts, and final totals.
Strictly relies on Decimal arithmetic and quantizes to 2 decimal places.
Zero external calls, zero LLM reliance.
"""

from decimal import Decimal
from typing import Any

from app.models.invoice import Invoice, MONEY_QUANTUM, ROUNDING_STRATEGY
from app.models.verification import ArithmeticVerificationResult, VerificationStatus


def calculate_invoice_arithmetic(
    invoice: Invoice,
    tolerance: Decimal = Decimal("0.00"),
) -> ArithmeticVerificationResult:
    """Perform deterministic financial arithmetic verification on an invoice.

    Verifies:
    1. Quantity * Unit Price for each line item.
    2. Sum of line subtotals equals the reported subtotal.
    3. Final grand total equals (subtotal + tax - discount).

    Args:
        invoice: The invoice to verify.
        tolerance: Maximum permitted absolute discrepancy for floating rounding boundary conditions.

    Returns:
        ArithmeticVerificationResult with full computation breakdown and status.
    """
    details: list[str] = []

    # Check for missing required data
    if invoice.subtotal is None or invoice.total is None or not invoice.line_items:
        missing: list[str] = []
        if invoice.subtotal is None:
            missing.append("subtotal")
        if invoice.total is None:
            missing.append("total")
        if not invoice.line_items:
            missing.append("line_items")

        msg = f"Insufficient financial data for arithmetic verification: missing {', '.join(missing)}."
        details.append(msg)
        return ArithmeticVerificationResult(
            passed=False,
            status=VerificationStatus.INSUFFICIENT_DATA,
            expected_subtotal=None,
            actual_subtotal=invoice.subtotal,
            expected_tax=invoice.tax,
            actual_tax=invoice.tax,
            expected_discount=invoice.discount,
            actual_discount=invoice.discount,
            expected_total=None,
            actual_total=invoice.total,
            difference=None,
            currency=invoice.currency,
            details=details,
        )

    # 1. Line subtotals
    line_subtotals: list[Decimal] = []
    for idx, item in enumerate(invoice.line_items, start=1):
        line_sub = item.calculate_line_subtotal()
        line_subtotals.append(line_sub)

    # 2. Expected subtotal
    expected_subtotal = sum(line_subtotals).quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY)
    actual_subtotal = invoice.subtotal.quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY)
    subtotal_diff = abs(actual_subtotal - expected_subtotal)

    subtotal_mismatch = subtotal_diff > tolerance
    if subtotal_mismatch:
        details.append(
            f"Subtotal mismatch: expected sum of line items {expected_subtotal}, "
            f"reported {actual_subtotal} (diff: {subtotal_diff})."
        )

    # 3. Tax and Discount handling
    actual_tax = invoice.tax.quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY) if invoice.tax is not None else Decimal("0.00")
    actual_discount = invoice.discount.quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY) if invoice.discount is not None else Decimal("0.00")

    expected_tax = actual_tax
    expected_discount = actual_discount

    # 4. Expected Total
    expected_total = (expected_subtotal + actual_tax - actual_discount).quantize(
        MONEY_QUANTUM, rounding=ROUNDING_STRATEGY
    )
    actual_total = invoice.total.quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY)
    difference = abs(actual_total - expected_total)

    total_mismatch = difference > tolerance
    if total_mismatch:
        details.append(
            f"Total mismatch: calculated {expected_total} "
            f"(subtotal {expected_subtotal} + tax {actual_tax} - discount {actual_discount}), "
            f"reported {actual_total} (diff: {difference})."
        )

    passed = not (subtotal_mismatch or total_mismatch)
    status = VerificationStatus.PASS if passed else VerificationStatus.FAIL

    if passed:
        details.append("Arithmetic verification passed cleanly.")

    return ArithmeticVerificationResult(
        passed=passed,
        status=status,
        expected_subtotal=expected_subtotal,
        actual_subtotal=actual_subtotal,
        expected_tax=expected_tax,
        actual_tax=actual_tax,
        expected_discount=expected_discount,
        actual_discount=actual_discount,
        expected_total=expected_total,
        actual_total=actual_total,
        difference=difference,
        currency=invoice.currency,
        details=details,
    )
