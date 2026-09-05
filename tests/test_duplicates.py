"""Unit tests for deterministic duplicate invoice detection tool.

Tests confirmed duplicate rules, possible duplicate rules with date windows,
empty history, multiple matching records, and cross-vendor isolation.
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.models.invoice import Invoice, LineItem
from app.models.verification import DuplicateStatus
from app.tools.duplicates import check_duplicate_invoice
from tests.fixtures import (
    get_clean_invoice,
    get_confirmed_duplicate_invoice,
    get_possible_duplicate_invoice,
    get_historical_invoices,
)


def test_duplicates_empty_history_returns_no_duplicate():
    """Verify empty historical dataset produces NO_DUPLICATE."""
    inv = get_clean_invoice()
    result = check_duplicate_invoice(inv, history=[])
    assert result.status == DuplicateStatus.NO_DUPLICATE
    assert result.matched_invoice_ids == []


def test_duplicates_confirmed_match():
    """Verify same vendor and invoice number triggers CONFIRMED_DUPLICATE."""
    inv = get_confirmed_duplicate_invoice()
    history = get_historical_invoices()

    result = check_duplicate_invoice(inv, history)
    assert result.status == DuplicateStatus.CONFIRMED_DUPLICATE
    assert "HIST-001" in result.matched_invoice_ids
    assert "same_vendor" in result.match_reasons
    assert "same_invoice_number" in result.match_reasons


def test_duplicates_possible_match_within_window():
    """Verify same vendor and amount within 7 days triggers POSSIBLE_DUPLICATE."""
    inv = get_possible_duplicate_invoice()  # 4 days after HIST-002, same amount 440.00
    history = get_historical_invoices()

    result = check_duplicate_invoice(inv, history, max_days=7)
    assert result.status == DuplicateStatus.POSSIBLE_DUPLICATE
    assert "HIST-002" in result.matched_invoice_ids
    assert "same_vendor" in result.match_reasons
    assert "same_amount" in result.match_reasons


def test_duplicates_outside_window_is_no_duplicate():
    """Verify same vendor and amount outside date window is NOT marked as possible duplicate."""
    inv = get_possible_duplicate_invoice()
    # Shift date to 30 days later
    inv_outside = inv.model_copy(update={"invoice_date": date(2026, 4, 1)})
    history = get_historical_invoices()

    result = check_duplicate_invoice(inv_outside, history, max_days=7)
    assert result.status == DuplicateStatus.NO_DUPLICATE
    assert result.matched_invoice_ids == []


def test_duplicates_different_vendor_same_number_is_no_duplicate():
    """Verify identical invoice number from a different vendor does not trigger duplicate."""
    inv = Invoice(
        invoice_id="INV-DIFF-VEND",
        invoice_number="ACME-2026-001",  # Same number as HIST-001
        vendor_id="VEND-OTHER-99",       # Different vendor
        vendor_name="Other Supplies",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 2, 1),
        currency="USD",
        subtotal=Decimal("200.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("200.00"),
    )
    history = get_historical_invoices()
    result = check_duplicate_invoice(inv, history)
    assert result.status == DuplicateStatus.NO_DUPLICATE


def test_duplicates_multiple_matches_collects_all_ids():
    """Verify multiple matching records in history are all captured in matched_invoice_ids."""
    dup1 = Invoice(
        invoice_id="HIST-DUP-A",
        invoice_number="DUP-999",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 2, 1),
        total=Decimal("100.00"),
    )
    dup2 = Invoice(
        invoice_id="HIST-DUP-B",
        invoice_number="DUP-999",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 2, 5),
        total=Decimal("100.00"),
    )
    candidate = Invoice(
        invoice_id="INV-CANDIDATE",
        invoice_number="DUP-999",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme",
        customer_name="Corp",
        invoice_date=date(2026, 2, 10),
        total=Decimal("100.00"),
    )

    result = check_duplicate_invoice(candidate, history=[dup1, dup2])
    assert result.status == DuplicateStatus.CONFIRMED_DUPLICATE
    assert set(result.matched_invoice_ids) == {"HIST-DUP-A", "HIST-DUP-B"}


def test_duplicates_ignores_self_identity():
    """Verify an invoice comparing against a dataset containing itself does not match itself."""
    inv = get_clean_invoice()
    result = check_duplicate_invoice(inv, history=[inv])
    assert result.status == DuplicateStatus.NO_DUPLICATE
