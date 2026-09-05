"""Unit tests for deterministic invoice arithmetic verification tool.

Tests happy path, subtotal mismatches, grand total mismatches, missing fields (INSUFFICIENT_DATA),
boundary quantities, boundary prices, zero tax, zero discount, and half-up rounding.
"""

from datetime import date
from decimal import Decimal
import pytest

from app.models.invoice import Invoice, LineItem
from app.models.verification import VerificationStatus
from app.tools.arithmetic import calculate_invoice_arithmetic
from tests.fixtures import (
    get_clean_invoice,
    get_arithmetic_mismatch_invoice,
    get_incomplete_invoice,
    get_zero_tax_invoice,
    get_zero_discount_invoice,
    get_boundary_invoice,
)


def test_arithmetic_clean_invoice_passes():
    """Verify standard compliant invoice passes with status PASS."""
    inv = get_clean_invoice()
    result = calculate_invoice_arithmetic(inv)

    assert result.passed is True
    assert result.status == VerificationStatus.PASS
    assert result.expected_subtotal == Decimal("200.00")
    assert result.actual_subtotal == Decimal("200.00")
    assert result.expected_total == Decimal("220.00")
    assert result.actual_total == Decimal("220.00")
    assert result.difference == Decimal("0.00")


def test_arithmetic_mismatch_fails():
    """Verify discrepancy in grand total triggers status FAIL."""
    inv = get_arithmetic_mismatch_invoice()
    result = calculate_invoice_arithmetic(inv)

    assert result.passed is False
    assert result.status == VerificationStatus.FAIL
    assert result.expected_total == Decimal("220.00")
    assert result.actual_total == Decimal("250.00")
    assert result.difference == Decimal("30.00")
    assert any("Total mismatch" in d for d in result.details)


def test_arithmetic_subtotal_mismatch_fails():
    """Verify subtotal discrepancy triggers FAIL even if total formula was forced."""
    inv = Invoice(
        invoice_id="INV-SUB-FAIL",
        invoice_number="SUB-001",
        vendor_id="VEND-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 1, 1),
        currency="USD",
        subtotal=Decimal("300.00"),  # False subtotal: actual lines sum to 200.00
        tax=Decimal("20.00"),
        discount=Decimal("0.00"),
        total=Decimal("320.00"),
        line_items=[
            LineItem(
                description="Item 1",
                quantity=Decimal("2"),
                unit_price=Decimal("100.00"),
            )
        ],
    )
    result = calculate_invoice_arithmetic(inv)
    assert result.passed is False
    assert result.status == VerificationStatus.FAIL
    assert any("Subtotal mismatch" in d for d in result.details)


def test_arithmetic_incomplete_invoice_returns_insufficient_data():
    """Verify missing financial fields cleanly return INSUFFICIENT_DATA without crashing."""
    inv = get_incomplete_invoice()
    result = calculate_invoice_arithmetic(inv)

    assert result.passed is False
    assert result.status == VerificationStatus.INSUFFICIENT_DATA
    assert result.expected_total is None
    assert any("Insufficient financial data" in d for d in result.details)


def test_arithmetic_zero_tax_and_zero_discount():
    """Verify invoices with zero tax and zero discount compute accurately."""
    inv_tax = get_zero_tax_invoice()
    res_tax = calculate_invoice_arithmetic(inv_tax)
    assert res_tax.passed is True
    assert res_tax.actual_tax == Decimal("0.00")

    inv_disc = get_zero_discount_invoice()
    res_disc = calculate_invoice_arithmetic(inv_disc)
    assert res_disc.passed is True
    assert res_disc.actual_discount == Decimal("0.00")


@pytest.mark.parametrize("amount", [
    Decimal("0.00"),
    Decimal("0.01"),
    Decimal("99.99"),
    Decimal("1000.00"),
    Decimal("5000.00"),
    Decimal("9999.99"),
    Decimal("10000.00"),
])
def test_arithmetic_boundary_amounts(amount: Decimal):
    """Verify exact calculation across designated boundary values."""
    inv = get_boundary_invoice(amount)
    result = calculate_invoice_arithmetic(inv)
    assert result.passed is True
    assert result.actual_total == amount
    assert result.expected_total == amount
    assert result.difference == Decimal("0.00")


@pytest.mark.parametrize("qty,price,expected_sub", [
    (Decimal("0"), Decimal("100.00"), Decimal("0.00")),
    (Decimal("1"), Decimal("0.00"), Decimal("0.00")),
    (Decimal("1"), Decimal("0.01"), Decimal("0.01")),
    (Decimal("1"), Decimal("99.99"), Decimal("99.99")),
    (Decimal("10"), Decimal("1000.00"), Decimal("10000.00")),
])
def test_arithmetic_quantity_price_matrix(qty: Decimal, price: Decimal, expected_sub: Decimal):
    """Verify calculation across quantity and unit price matrix."""
    inv = Invoice(
        invoice_id="INV-MATRIX",
        invoice_number="NUM-M",
        vendor_id="VEND-M",
        vendor_name="Matrix Vendor",
        customer_name="Corp",
        invoice_date=date(2026, 1, 1),
        currency="USD",
        subtotal=expected_sub,
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=expected_sub,
        line_items=[
            LineItem(
                description="Matrix Item",
                quantity=qty,
                unit_price=price,
            )
        ],
    )
    result = calculate_invoice_arithmetic(inv)
    assert result.passed is True
    assert result.expected_subtotal == expected_sub


def test_arithmetic_rounding_precision_half_up():
    """Verify ROUND_HALF_UP precision at 0.005 boundary."""
    # 1 item @ 10.005 -> quantizes to 10.01
    item = LineItem(description="Fractional Unit", quantity=Decimal("1"), unit_price=Decimal("10.005"))
    sub = item.calculate_line_subtotal()
    assert sub == Decimal("10.01")


def test_arithmetic_tolerance():
    """Verify tolerance parameter allows controlled minor variances."""
    inv = Invoice(
        invoice_id="INV-TOL",
        invoice_number="TOL-001",
        vendor_id="VEND-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 1, 1),
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("100.02"),  # 0.02 off
        line_items=[
            LineItem(description="Item", quantity=Decimal("1"), unit_price=Decimal("100.00"))
        ],
    )
    # Default tolerance 0.00 fails
    assert calculate_invoice_arithmetic(inv).passed is False

    # Tolerance 0.05 passes
    assert calculate_invoice_arithmetic(inv, tolerance=Decimal("0.05")).passed is True
