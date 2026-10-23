"""Unit tests for LedgerGuard deterministic anomaly detection engine."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.invoice import Invoice, LineItem
from app.tools.anomaly import (
    AnomalySeverity,
    AnomalyType,
    detect_arithmetic_anomalies,
    detect_duplicate_billing,
    detect_price_increases,
    detect_unregistered_vendor_anomalies,
    scan_invoice_anomalies,
)


def _make_invoice(
    invoice_id: str,
    invoice_number: str,
    vendor_id: str,
    vendor_name: str,
    total: str,
    invoice_date: date = date(2026, 10, 20),
    subtotal: str | None = None,
    line_items: list[LineItem] | None = None,
) -> Invoice:
    return Invoice(
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        customer_name="LedgerGuard Enterprise",
        invoice_date=invoice_date,
        currency="USD",
        subtotal=Decimal(subtotal) if subtotal else Decimal(total),
        total=Decimal(total),
        line_items=line_items or [],
    )


def test_detect_subscription_price_increase():
    """Detect significant recurring price increases compared to historical baseline."""
    history = [
        _make_invoice("inv-hist-001", "INV-2026-001", "v-acme", "Acme Cloud", "4000.00", date(2026, 9, 15))
    ]
    # 25% price increase
    candidate = _make_invoice("inv-new-001", "INV-2026-002", "v-acme", "Acme Cloud", "5000.00", date(2026, 10, 15))

    findings = detect_price_increases(candidate, history, max_acceptable_increase_pct=Decimal("5.0"))
    assert len(findings) == 1
    f = findings[0]
    assert f.anomaly_type == AnomalyType.SUBSCRIPTION_PRICE_INCREASE
    assert f.evidence.percentage_change == Decimal("25.0")
    assert f.evidence.delta_amount == Decimal("1000.00")
    assert f.severity == AnomalySeverity.HIGH


def test_detect_no_price_increase_when_equal_or_lower():
    """Equal or lower charge produces no price increase anomaly."""
    history = [
        _make_invoice("inv-hist-001", "INV-2026-001", "v-acme", "Acme Cloud", "4000.00", date(2026, 9, 15))
    ]
    candidate = _make_invoice("inv-new-001", "INV-2026-002", "v-acme", "Acme Cloud", "3800.00", date(2026, 10, 15))

    findings = detect_price_increases(candidate, history)
    assert len(findings) == 0


def test_detect_duplicate_billing_exact_and_proximity():
    """Identify both exact invoice number duplicate and near-window identical amount charges."""
    history = [
        _make_invoice("inv-hist-042", "INV-2026-042", "v-apex", "Apex Hardware", "8400.00", date(2026, 9, 30)),
        _make_invoice("inv-hist-099", "INV-2026-099", "v-nexus", "Nexus Freight", "3520.00", date(2026, 10, 16)),
    ]

    # Exact duplicate invoice number
    exact_candidate = _make_invoice("inv-dup-1", "INV-2026-042", "v-apex", "Apex Hardware", "8400.00", date(2026, 10, 20))
    findings = detect_duplicate_billing(exact_candidate, history)
    assert any(f.severity == AnomalySeverity.CRITICAL for f in findings)
    assert any(f.anomaly_type == AnomalyType.DUPLICATE_BILLING for f in findings)

    # Proximity duplicate (same vendor, same amount within 2 days)
    prox_candidate = _make_invoice("inv-dup-2", "INV-2026-100", "v-nexus", "Nexus Freight", "3520.00", date(2026, 10, 18))
    prox_findings = detect_duplicate_billing(prox_candidate, history, proximity_days=7)
    assert len(prox_findings) == 1
    assert prox_findings[0].severity == AnomalySeverity.HIGH


def test_detect_arithmetic_anomalies():
    """Identify unbacked subtotal padding where line items do not sum to subtotal."""
    line_item = LineItem(
        description="Pallets",
        quantity=Decimal("10"),
        unit_price=Decimal("200.00"),
        tax_rate=Decimal("0.00"),
    )
    # Line items sum to 2,000.00, but subtotal declared is 3,200.00
    candidate = _make_invoice(
        "inv-arith-1", "INV-102", "v-nexus", "Nexus Freight", "3520.00",
        subtotal="3200.00",
        line_items=[line_item]
    )

    findings = detect_arithmetic_anomalies(candidate)
    assert len(findings) == 1
    assert findings[0].anomaly_type == AnomalyType.ARITHMETIC_MISMATCH
    assert findings[0].evidence.delta_amount == Decimal("1200.00")


def test_detect_unregistered_vendor_spend_breach():
    """Identify unregistered vendor breaching the $25,000 spend limit."""
    candidate = _make_invoice("inv-shadow-1", "INV-104", "v-shadow", "Shadow Consulting LLC", "38500.00")
    registered = {"v-acme", "v-apex", "v-nexus"}

    findings = detect_unregistered_vendor_anomalies(candidate, registered, spend_threshold=Decimal("25000.00"))
    assert len(findings) == 1
    assert findings[0].anomaly_type == AnomalyType.UNREGISTERED_VENDOR_BREACH
    assert findings[0].severity == AnomalySeverity.HIGH
    assert findings[0].is_suspected_anomaly is True


def test_scan_invoice_anomalies_consolidated():
    """Compile comprehensive scan report for all evaluated rules."""
    history = [
        _make_invoice("inv-hist-042", "INV-2026-042", "v-apex", "Apex Hardware Supply", "8400.00", date(2026, 9, 30))
    ]
    candidate = _make_invoice("INV-2026-103", "INV-2026-042", "v-apex", "Apex Hardware Supply", "8400.00", date(2026, 10, 20))

    report = scan_invoice_anomalies(candidate, history)
    assert report.findings_count >= 1
    assert report.has_critical_anomaly is True
    assert "DUPLICATE_BILLING" in [f.anomaly_type.value for f in report.findings]
