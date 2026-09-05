"""Unit tests for deterministic vendor history tool.

Tests new vendor classification, volume counts, spend averages,
first/last dates, recent invoice horizons, and multi-currency safety.
"""

from datetime import date
from decimal import Decimal
import pytest

from app.models.invoice import Invoice
from app.tools.vendor_history import get_vendor_history
from tests.fixtures import get_historical_invoices, get_multi_currency_history


def test_vendor_history_new_vendor():
    """Verify vendor without prior invoices is classified as new_vendor=True with zero counts."""
    result = get_vendor_history("VEND-UNKNOWN-99", history=[])
    assert result.new_vendor is True
    assert result.invoice_count == 0
    assert result.total_spend == {}
    assert result.average_invoice_amount == {}
    assert result.first_invoice_date is None
    assert result.last_invoice_date is None
    assert result.recent_invoice_count == 0


def test_vendor_history_single_invoice():
    """Verify vendor history with single invoice."""
    history = [
        Invoice(
            invoice_id="H-1",
            invoice_number="INV-1",
            vendor_id="VEND-01",
            vendor_name="Acme",
            customer_name="Corp",
            invoice_date=date(2026, 2, 1),
            currency="USD",
            total=Decimal("500.00"),
        )
    ]
    result = get_vendor_history("VEND-01", history)
    assert result.new_vendor is False
    assert result.invoice_count == 1
    assert result.total_spend["USD"] == Decimal("500.00")
    assert result.average_invoice_amount["USD"] == Decimal("500.00")
    assert result.largest_invoice_amount["USD"] == Decimal("500.00")
    assert result.first_invoice_date == date(2026, 2, 1)
    assert result.last_invoice_date == date(2026, 2, 1)


def test_vendor_history_multiple_invoices():
    """Verify aggregation of multiple historical invoices for the same vendor."""
    history = get_historical_invoices()  # 2 invoices: 220.00 on Feb 1, 440.00 on Feb 25
    result = get_vendor_history("VEND-ACME-01", history)

    assert result.new_vendor is False
    assert result.invoice_count == 2
    assert result.total_spend["USD"] == Decimal("660.00")
    assert result.average_invoice_amount["USD"] == Decimal("330.00")
    assert result.largest_invoice_amount["USD"] == Decimal("440.00")
    assert result.first_invoice_date == date(2026, 2, 1)
    assert result.last_invoice_date == date(2026, 2, 25)


def test_vendor_history_multi_currency_safety():
    """Verify amounts in different currencies are never combined into a single sum."""
    history = get_multi_currency_history()  # VEND-EUROPE-01: EUR 1190.00, USD 550.00
    result = get_vendor_history("VEND-EUROPE-01", history)

    assert result.new_vendor is False
    assert result.invoice_count == 2
    # Check that USD and EUR totals remain strictly distinct
    assert result.total_spend["EUR"] == Decimal("1190.00")
    assert result.total_spend["USD"] == Decimal("550.00")
    assert "EUR" in result.currency_distribution
    assert "USD" in result.currency_distribution
    assert result.currency_distribution["EUR"] == Decimal("1190.00")
    assert result.currency_distribution["USD"] == Decimal("550.00")


def test_vendor_history_recent_invoice_window():
    """Verify recent invoice counting respects configured window from reference date."""
    inv1 = Invoice(
        invoice_id="H-OLD",
        invoice_number="O-1",
        vendor_id="VEND-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 1, 1),
        total=Decimal("100.00"),
    )
    inv2 = Invoice(
        invoice_id="H-RECENT",
        invoice_number="R-1",
        vendor_id="VEND-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 3, 1),
        total=Decimal("100.00"),
    )

    result = get_vendor_history(
        "VEND-01",
        history=[inv1, inv2],
        recent_days=30,
        reference_date=date(2026, 3, 5),
    )
    assert result.invoice_count == 2
    assert result.recent_invoice_count == 1  # only inv2 is within 30 days of March 5
