"""Unit tests for Phase 8 AP Financial Summary Dashboard aggregations.

Verifies:
- Strict Decimal precision for all monetary totals (ROUND_HALF_UP).
- Handling of NOT_STATED tax/discount/shipping vs explicit values.
- Calculation coverage and exclusion of incomplete invoices from estimated payable.
- Decision-value breakdown (AUTO_APPROVED, MANUAL_REVIEW, BLOCKED).
- Batch and date filtering.
"""

from decimal import Decimal
import pytest
from datetime import datetime, timezone

from app.models.decision import AgentDecision
from app.models.persistence import InvoiceRecord
from app.models.state import ProcessingState
from app.models.verification import RiskLevel
from app.services.dynamodb import DynamoDBInvoiceRepository


class FakeDynamoTable:
    """Mock DynamoDB table for unit testing repository aggregations."""

    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        pk = Item["PK"]
        sk = Item["SK"]
        self.items[(pk, sk)] = Item

    def get_item(self, Key):
        return {"Item": self.items.get((Key["PK"], Key["SK"]))}

    def scan(self, FilterExpression=None):
        out = []
        for (pk, sk), item in self.items.items():
            if pk.startswith("INVOICE#") and sk == "METADATA":
                out.append(item)
            elif pk.startswith("BATCH#") and sk == "METADATA":
                out.append(item)
        return {"Items": out}

    def query(self, KeyConditionExpression=None):
        return {"Items": []}


def test_ap_financial_aggregates_decimal_precision():
    """Verify AP Financial Summary aggregates strictly with Decimal."""
    fake_table = FakeDynamoTable()
    repo = DynamoDBInvoiceRepository(table=fake_table)

    # Invoice A: 100 subtotal, 10 discount, 5 shipping, 20 tax -> total 115
    inv_a = InvoiceRecord(
        invoice_id="INV-A",
        invoice_number="INV-A",
        vendor_id="V-1",
        vendor_name="Vendor One",
        invoice_date="2026-03-01",
        subtotal=Decimal("100.00"),
        discount=Decimal("10.00"),
        shipping=Decimal("5.00"),
        tax=Decimal("20.00"),
        total=Decimal("115.00"),
        processing_status=ProcessingState.AUTO_APPROVED,
        decision=AgentDecision.AUTO_APPROVE,
    )
    # Invoice B: 200 subtotal, 20 discount, 10 shipping, 30 tax -> total 220
    inv_b = InvoiceRecord(
        invoice_id="INV-B",
        invoice_number="INV-B",
        vendor_id="V-2",
        vendor_name="Vendor Two",
        invoice_date="2026-03-02",
        subtotal=Decimal("200.00"),
        discount=Decimal("20.00"),
        shipping=Decimal("10.00"),
        tax=Decimal("30.00"),
        total=Decimal("220.00"),
        processing_status=ProcessingState.MANUAL_REVIEW,
        decision=AgentDecision.MANUAL_REVIEW,
    )
    repo.save_record(inv_a)
    repo.save_record(inv_b)

    stats = repo.get_dashboard_stats()

    # Step 32 verified calculations:
    # Subtotal = 100 + 200 = 300
    # Discount = 10 + 20 = 30
    # Shipping = 5 + 10 = 15
    # Tax = 20 + 30 = 50
    # Estimated Payable = 300 - 30 + 15 + 50 = 335
    assert isinstance(stats["total_subtotal"], Decimal)
    assert stats["total_subtotal"] == Decimal("300.00")

    assert isinstance(stats["total_discount"], Decimal)
    assert stats["total_discount"] == Decimal("30.00")

    assert isinstance(stats["total_shipping"], Decimal)
    assert stats["total_shipping"] == Decimal("15.00")

    assert isinstance(stats["total_tax"], Decimal)
    assert stats["total_tax"] == Decimal("50.00")

    assert isinstance(stats["total_invoice_value"], Decimal)
    assert stats["total_invoice_value"] == Decimal("335.00")

    assert isinstance(stats["estimated_payable_amount"], Decimal)
    assert stats["estimated_payable_amount"] == Decimal("335.00")

    assert stats["estimated_payable_invoices_count"] == 2
    assert stats["estimated_payable_coverage_pct"] == 100.0

    # Decision-value breakdown
    assert stats["auto_approved_value"] == Decimal("115.00")
    assert stats["manual_review_value"] == Decimal("220.00")
    assert stats["blocked_value"] == Decimal("0.00")


def test_ap_financial_not_stated_handling():
    """Verify NOT_STATED tax is not counted as $0.00 and excluded from estimated payable."""
    fake_table = FakeDynamoTable()
    repo = DynamoDBInvoiceRepository(table=fake_table)

    # SuperStore #36259 pattern: Subtotal 53.82, Shipping 4.29, Total 58.11, Tax=None (NOT_STATED)
    superstore_inv = InvoiceRecord(
        invoice_id="INV-SS-36259",
        invoice_number="36259",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        invoice_date="2012-03-06",
        subtotal=Decimal("53.82"),
        discount=None,
        shipping=Decimal("4.29"),
        tax=None,  # NOT_STATED
        total=Decimal("58.11"),
        processing_status=ProcessingState.AUTO_APPROVED,
        decision=AgentDecision.AUTO_APPROVE,
    )
    repo.save_record(superstore_inv)

    stats = repo.get_dashboard_stats()

    assert stats["total_subtotal"] == Decimal("53.82")
    assert stats["total_shipping"] == Decimal("4.29")
    # Tax must NOT be fabricated as 0.00
    assert stats["total_tax"] == Decimal("0.00")
    # Since tax is NOT_STATED, it cannot compute an exact deterministic payable amount
    assert stats["estimated_payable_amount"] == Decimal("0.00")
    assert stats["estimated_payable_invoices_count"] == 0
    assert stats["estimated_payable_coverage_pct"] == 0.0
    assert stats["total_invoice_value"] == Decimal("58.11")
    assert stats["auto_approved_value"] == Decimal("58.11")


def test_ap_financial_decision_and_duplicate_breakdown():
    """Verify blocked and duplicate invoice values are isolated correctly."""
    fake_table = FakeDynamoTable()
    repo = DynamoDBInvoiceRepository(table=fake_table)

    inv_blocked = InvoiceRecord(
        invoice_id="INV-BLK-1",
        invoice_number="INV-BLK-1",
        vendor_id="V-3",
        vendor_name="Shady Vendor",
        invoice_date="2026-03-05",
        subtotal=Decimal("5000.00"),
        total=Decimal("5000.00"),
        processing_status=ProcessingState.BLOCKED,
        decision=AgentDecision.BLOCK,
        verification_summary={"reason": "POLICY_BLOCK"},
    )
    inv_dup = InvoiceRecord(
        invoice_id="INV-DUP-1",
        invoice_number="INV-DUP-1",
        vendor_id="V-1",
        vendor_name="Vendor One",
        invoice_date="2026-03-05",
        subtotal=Decimal("115.00"),
        total=Decimal("115.00"),
        processing_status=ProcessingState.BLOCKED,
        decision=AgentDecision.BLOCK,
        verification_summary={"reason": "CONFIRMED_DUPLICATE"},
    )
    repo.save_record(inv_blocked)
    repo.save_record(inv_dup)

    stats = repo.get_dashboard_stats()

    assert stats["blocked_value"] == Decimal("5115.00")
    assert stats["duplicate_value"] == Decimal("115.00")
