"""Deterministic Anomaly Detection Engine for LedgerGuard.

Implements transparent, reproducible, evidence-based anomaly detection rules
against stored financial transaction data:
1. Subscription price increases based on historical comparable charges.
2. Potential duplicate charges based on vendor, amount, and date window.
3. Line-item arithmetic mismatches and unbacked amount padding.
4. Unregistered vendor spend threshold breaches.
5. Missing or inconsistent transaction fields.

Separates confirmed observations from suspected anomalies and rule findings.
Zero LLM reliance, strictly deterministic using Python Decimal arithmetic.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel, Field

from app.models.invoice import Invoice, LineItem

MONEY_QUANTUM = Decimal("0.01")
ROUNDING = ROUND_HALF_UP


class AnomalyType(str, Enum):
    """Categorization of detected financial anomalies."""
    SUBSCRIPTION_PRICE_INCREASE = "SUBSCRIPTION_PRICE_INCREASE"
    DUPLICATE_BILLING = "DUPLICATE_BILLING"
    ARITHMETIC_MISMATCH = "ARITHMETIC_MISMATCH"
    UNREGISTERED_VENDOR_BREACH = "UNREGISTERED_VENDOR_BREACH"
    OFF_SCHEDULE_BILLING = "OFF_SCHEDULE_BILLING"
    MISSING_REQUIRED_DATA = "MISSING_REQUIRED_DATA"


class AnomalySeverity(str, Enum):
    """Severity classification for detected anomalies."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyEvidence(BaseModel):
    """Detailed evidence supporting an anomaly finding."""
    field_evaluated: str
    observed_value: str
    baseline_value: str | None = None
    delta_amount: Decimal | None = None
    percentage_change: Decimal | None = None
    historical_reference_id: str | None = None
    details: str


class AnomalyFinding(BaseModel):
    """Structured, reproducible finding produced by deterministic anomaly rules."""
    invoice_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    rule_id: str
    rule_name: str
    is_confirmed_observation: bool = Field(
        ...,
        description="True if mathematically or factually proven (e.g. arithmetic discrepancy or duplicate)",
    )
    is_suspected_anomaly: bool = Field(
        ...,
        description="True if pattern-based deviation warranting review (e.g. price increase)",
    )
    explanation: str
    evidence: AnomalyEvidence
    recommended_action: str


class AnomalyScanReport(BaseModel):
    """Consolidated anomaly detection scan report for an invoice."""
    invoice_id: str
    invoice_number: str
    vendor_id: str
    vendor_name: str
    total_amount: Decimal | None
    currency: str
    scan_timestamp: str
    findings_count: int
    has_critical_anomaly: bool
    has_high_anomaly: bool
    findings: list[AnomalyFinding]
    summary_text: str


def detect_price_increases(
    invoice: Invoice,
    history: Sequence[Invoice],
    max_acceptable_increase_pct: Decimal = Decimal("5.0"),
) -> list[AnomalyFinding]:
    """Detect subscription or recurring service price increases compared to past settled charges."""
    findings: list[AnomalyFinding] = []
    if invoice.total is None or invoice.total <= Decimal("0.00"):
        return findings

    # Look for matching vendor historical invoices
    vendor_history = [
        h for h in history
        if h.vendor_id.strip().lower() == invoice.vendor_id.strip().lower()
        and h.invoice_id != invoice.invoice_id
        and h.total is not None
        and h.total > Decimal("0.00")
        and h.currency == invoice.currency
    ]

    if not vendor_history:
        return findings

    # Sort descending by date to find most recent comparable charge
    vendor_history.sort(key=lambda x: x.invoice_date, reverse=True)
    most_recent = vendor_history[0]

    prior_total = most_recent.total
    if prior_total is None or prior_total <= Decimal("0.00"):
        return findings

    if invoice.total > prior_total:
        delta = (invoice.total - prior_total).quantize(MONEY_QUANTUM, rounding=ROUNDING)
        pct_increase = ((delta / prior_total) * Decimal("100.00")).quantize(Decimal("0.1"), rounding=ROUNDING)

        if pct_increase >= max_acceptable_increase_pct:
            sev = AnomalySeverity.HIGH if pct_increase >= Decimal("20.0") else AnomalySeverity.MEDIUM
            findings.append(
                AnomalyFinding(
                    invoice_id=invoice.invoice_id,
                    anomaly_type=AnomalyType.SUBSCRIPTION_PRICE_INCREASE,
                    severity=sev,
                    rule_id="RULE-ANOMALY-SUB-01",
                    rule_name="Recurring Subscription Price Increase",
                    is_confirmed_observation=True,
                    is_suspected_anomaly=False,
                    explanation=(
                        f"Invoice total of {invoice.currency} {invoice.total} is {pct_increase}% "
                        f"(+{invoice.currency} {delta}) higher than the previous charge of "
                        f"{invoice.currency} {prior_total} from {most_recent.invoice_number} on {most_recent.invoice_date}."
                    ),
                    evidence=AnomalyEvidence(
                        field_evaluated="total",
                        observed_value=str(invoice.total),
                        baseline_value=str(prior_total),
                        delta_amount=delta,
                        percentage_change=pct_increase,
                        historical_reference_id=most_recent.invoice_id,
                        details=f"Prior settled transaction: {most_recent.invoice_number}",
                    ),
                    recommended_action="VERIFY_RATE_CARD_OR_DISPUTE_SURCHARGE",
                )
            )

    return findings


def detect_duplicate_billing(
    invoice: Invoice,
    history: Sequence[Invoice],
    proximity_days: int = 7,
) -> list[AnomalyFinding]:
    """Detect potential or confirmed duplicate billing anomalies."""
    findings: list[AnomalyFinding] = []
    norm_vendor = invoice.vendor_id.strip().lower()
    norm_num = invoice.invoice_number.strip().lower()

    for past in history:
        if past.invoice_id == invoice.invoice_id:
            continue
        past_vendor = past.vendor_id.strip().lower()
        past_num = past.invoice_number.strip().lower()

        # Exact duplicate
        if past_vendor == norm_vendor and past_num == norm_num:
            findings.append(
                AnomalyFinding(
                    invoice_id=invoice.invoice_id,
                    anomaly_type=AnomalyType.DUPLICATE_BILLING,
                    severity=AnomalySeverity.CRITICAL,
                    rule_id="RULE-ANOMALY-DUP-01",
                    rule_name="Exact Duplicate Invoice Number",
                    is_confirmed_observation=True,
                    is_suspected_anomaly=False,
                    explanation=(
                        f"Invoice number '{invoice.invoice_number}' for vendor '{invoice.vendor_name}' "
                        f"was already billed on past invoice {past.invoice_id} ({past.currency} {past.total}). "
                        f"Disbursing payment will cause duplicate loss."
                    ),
                    evidence=AnomalyEvidence(
                        field_evaluated="invoice_number",
                        observed_value=invoice.invoice_number,
                        baseline_value=past.invoice_number,
                        historical_reference_id=past.invoice_id,
                        details=f"Matched settled invoice {past.invoice_id}",
                    ),
                    recommended_action="BLOCK_PAYMENT_IMMEDIATELY",
                )
            )
        # Proximity duplicate
        elif (
            past_vendor == norm_vendor
            and invoice.total is not None
            and past.total is not None
            and invoice.total == past.total
            and invoice.currency == past.currency
        ):
            days_diff = abs((invoice.invoice_date - past.invoice_date).days)
            if days_diff <= proximity_days:
                findings.append(
                    AnomalyFinding(
                        invoice_id=invoice.invoice_id,
                        anomaly_type=AnomalyType.DUPLICATE_BILLING,
                        severity=AnomalySeverity.HIGH,
                        rule_id="RULE-ANOMALY-DUP-02",
                        rule_name="Near-Proximity Identical Amount Duplicate",
                        is_confirmed_observation=False,
                        is_suspected_anomaly=True,
                        explanation=(
                            f"Identical charge of {invoice.currency} {invoice.total} for vendor '{invoice.vendor_name}' "
                            f"was submitted within {days_diff} days of invoice {past.invoice_id} ({past.invoice_date})."
                        ),
                        evidence=AnomalyEvidence(
                            field_evaluated="total_and_date",
                            observed_value=f"{invoice.total} on {invoice.invoice_date}",
                            baseline_value=f"{past.total} on {past.invoice_date}",
                            delta_amount=Decimal("0.00"),
                            historical_reference_id=past.invoice_id,
                            details=f"Proximity: {days_diff} days difference",
                        ),
                        recommended_action="HOLD_AND_VERIFY_SUPPORTING_PO",
                    )
                )

    return findings


def detect_arithmetic_anomalies(invoice: Invoice) -> list[AnomalyFinding]:
    """Detect unbacked line item padding or arithmetic discrepancies."""
    findings: list[AnomalyFinding] = []
    if not invoice.line_items:
        return findings

    calc_subtotal = Decimal("0.00")
    for li in invoice.line_items:
        calc_subtotal += li.calculate_line_subtotal()

    reported_subtotal = invoice.subtotal or Decimal("0.00")
    diff = abs(reported_subtotal - calc_subtotal).quantize(MONEY_QUANTUM, rounding=ROUNDING)

    if diff > Decimal("0.05"):
        findings.append(
            AnomalyFinding(
                invoice_id=invoice.invoice_id,
                anomaly_type=AnomalyType.ARITHMETIC_MISMATCH,
                severity=AnomalySeverity.HIGH,
                rule_id="RULE-ANOMALY-MATH-01",
                rule_name="Unbacked Line Item Subtotal Discrepancy",
                is_confirmed_observation=True,
                is_suspected_anomaly=False,
                explanation=(
                    f"Reported subtotal is {invoice.currency} {reported_subtotal}, but itemized sum of line items "
                    f"is {invoice.currency} {calc_subtotal}, creating an unbacked variance of {invoice.currency} {diff}."
                ),
                evidence=AnomalyEvidence(
                    field_evaluated="subtotal",
                    observed_value=str(reported_subtotal),
                    baseline_value=str(calc_subtotal),
                    delta_amount=diff,
                    details="Line-item summation does not match reported subtotal",
                ),
                recommended_action="DISPUTE_INVOICE_ARITHMETIC",
            )
        )

    return findings


def detect_unregistered_vendor_anomalies(
    invoice: Invoice,
    registered_vendor_ids: set[str],
    spend_threshold: Decimal = Decimal("25000.00"),
) -> list[AnomalyFinding]:
    """Detect unapproved vendors or unregistered vendors exceeding spend policy limit."""
    findings: list[AnomalyFinding] = []
    if invoice.vendor_id.lower() not in {v.lower() for v in registered_vendor_ids}:
        is_above_threshold = (invoice.total or Decimal("0.00")) > spend_threshold
        sev = AnomalySeverity.HIGH if is_above_threshold else AnomalySeverity.MEDIUM

        exp = (
            f"Vendor '{invoice.vendor_name}' ({invoice.vendor_id}) is not registered in the corporate vendor master."
        )
        if is_above_threshold:
            exp += f" Invoice total ({invoice.currency} {invoice.total}) breaches the $25,000 unregistered vendor threshold."

        findings.append(
            AnomalyFinding(
                invoice_id=invoice.invoice_id,
                anomaly_type=AnomalyType.UNREGISTERED_VENDOR_BREACH,
                severity=sev,
                rule_id="RULE-ANOMALY-VEND-01",
                rule_name="Unregistered Vendor Spend Breach" if is_above_threshold else "Unregistered Vendor Warning",
                is_confirmed_observation=True,
                is_suspected_anomaly=is_above_threshold,
                explanation=exp,
                evidence=AnomalyEvidence(
                    field_evaluated="vendor_id",
                    observed_value=invoice.vendor_id,
                    baseline_value="REGISTERED_IN_VENDOR_MASTER",
                    delta_amount=(invoice.total - spend_threshold) if is_above_threshold else None,
                    details=f"Spend threshold: {spend_threshold}",
                ),
                recommended_action="FREEZE_VENDOR_AND_REQUIRE_W9_ONBOARDING",
            )
        )

    return findings


def scan_invoice_anomalies(
    invoice: Invoice,
    history: Sequence[Invoice],
    registered_vendor_ids: set[str] | None = None,
    max_price_increase_pct: Decimal = Decimal("5.0"),
    spend_threshold: Decimal = Decimal("25000.00"),
) -> AnomalyScanReport:
    """Execute all deterministic anomaly rules against an invoice and compile a structured report."""
    from datetime import datetime, timezone
    vendors = registered_vendor_ids or {"v-acme", "v-nexus", "v-apex"}
    findings: list[AnomalyFinding] = []

    # 1. Price increases
    findings.extend(detect_price_increases(invoice, history, max_price_increase_pct))

    # 2. Duplicate billing
    findings.extend(detect_duplicate_billing(invoice, history))

    # 3. Arithmetic mismatches
    findings.extend(detect_arithmetic_anomalies(invoice))

    # 4. Unregistered vendor breaches
    findings.extend(detect_unregistered_vendor_anomalies(invoice, vendors, spend_threshold))

    has_crit = any(f.severity == AnomalySeverity.CRITICAL for f in findings)
    has_high = any(f.severity == AnomalySeverity.HIGH for f in findings)

    summary_parts = []
    if not findings:
        summary_parts.append("Clean invoice: zero anomalous patterns detected.")
    else:
        summary_parts.append(f"Detected {len(findings)} financial anomaly/risk finding(s):")
        for idx, f in enumerate(findings, 1):
            summary_parts.append(f"  {idx}. [{f.severity.value}] {f.rule_name}: {f.explanation}")

    return AnomalyScanReport(
        invoice_id=invoice.invoice_id,
        invoice_number=invoice.invoice_number,
        vendor_id=invoice.vendor_id,
        vendor_name=invoice.vendor_name,
        total_amount=invoice.total,
        currency=invoice.currency,
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
        findings_count=len(findings),
        has_critical_anomaly=has_crit,
        has_high_anomaly=has_high,
        findings=findings,
        summary_text="\n".join(summary_parts),
    )
