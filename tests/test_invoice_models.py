"""Unit tests for Invoice and LineItem domain models.

Verifies strict Decimal enforcement, rejection of floats, rejection of negatives,
support for incomplete financial fields, and line-level calculations.
"""

from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.models.invoice import Invoice, LineItem, quantize_money


def test_line_item_valid_decimal():
    """Verify valid LineItem creation using Decimal."""
    item = LineItem(
        description="Widget Pro",
        quantity=Decimal("3"),
        unit_price=Decimal("49.99"),
        tax_rate=Decimal("8.25"),
        discount=Decimal("5.00"),
    )
    assert item.quantity == Decimal("3")
    assert item.unit_price == Decimal("49.99")
    assert item.calculate_line_subtotal() == Decimal("149.97")


def test_line_item_rejects_float():
    """Verify float is strictly rejected in LineItem."""
    with pytest.raises(TypeError, match="Floating-point values are strictly forbidden"):
        LineItem(description="Float Item", unit_price=19.99)  # type: ignore

    with pytest.raises(TypeError, match="Floating-point values are strictly forbidden"):
        LineItem(description="Float Quantity", quantity=2.5, unit_price=Decimal("10.00"))  # type: ignore


def test_line_item_rejects_negative():
    """Verify negative quantity or price raises validation error."""
    with pytest.raises(ValidationError):
        LineItem(description="Negative Price", quantity=Decimal("1"), unit_price=Decimal("-10.00"))

    with pytest.raises(ValidationError):
        LineItem(description="Negative Qty", quantity=Decimal("-1"), unit_price=Decimal("10.00"))


def test_invoice_creation_valid():
    """Verify complete invoice initialization with Decimals."""
    inv = Invoice(
        invoice_id="INV-001",
        invoice_number="NUM-001",
        vendor_id="VEND-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 1, 1),
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        discount=Decimal("5.00"),
        total=Decimal("105.00"),
    )
    assert inv.subtotal == Decimal("100.00")
    assert inv.total == Decimal("105.00")


def test_invoice_rejects_float():
    """Verify float is strictly rejected in Invoice financial fields."""
    with pytest.raises(TypeError, match="Floating-point values are strictly forbidden"):
        Invoice(
            invoice_id="INV-001",
            invoice_number="NUM-001",
            vendor_id="VEND-01",
            vendor_name="Acme",
            customer_name="Corp",
            invoice_date=date(2026, 1, 1),
            total=105.50,  # type: ignore
        )


def test_invoice_allows_none_financials():
    """Verify incomplete invoice with None financials initializes cleanly."""
    inv = Invoice(
        invoice_id="INV-INCOMPLETE",
        invoice_number="RAW-001",
        vendor_id="VEND-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 1, 1),
        subtotal=None,
        tax=None,
        discount=None,
        total=None,
    )
    assert inv.subtotal is None
    assert inv.total is None


def test_quantize_money():
    """Verify quantize_money helper function."""
    assert quantize_money(None) is None
    assert quantize_money(Decimal("10.005")) == Decimal("10.01")
    assert quantize_money(Decimal("10.004")) == Decimal("10.00")
