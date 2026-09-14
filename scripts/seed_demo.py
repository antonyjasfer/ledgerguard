"""Demo seeding and safe environment management script for LedgerGuard.

Requirements:
- Explicit invocation only (--seed, --cleanup, --status)
- Strictly DEMO/TEST-prefixed invoice records
- Deterministic synthetic data
- Zero production records modified
- Safe reset / cleanup
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import argparse
import logging
import sys
import time
from datetime import date, datetime, timezone
from decimal import Decimal

from app.agent.orchestrator import run_verification_workflow
from app.config import get_settings
from app.models.audit import AuditEvent, AuditEventType
from app.models.decision import AgentDecision
from app.models.invoice import Invoice, LineItem
from app.models.persistence import InvoiceRecord
from app.models.policy import PolicyConfig
from app.models.verification import RiskLevel
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.s3 import S3DocumentStore
from app.services.state import ProcessingState
from scripts.demo_scenarios import (
    get_scenario_1_clean,
    get_scenario_2_risky,
    get_scenario_3_blocked,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ledgerguard.seed")

DEMO_PREFIXES = ("DEMO-", "TEST-")


def get_repository():
    """Resolve DynamoDB repository with current settings."""
    settings = get_settings()
    return DynamoDBInvoiceRepository(settings=settings)


def get_doc_store():
    """Resolve S3 document store."""
    settings = get_settings()
    return S3DocumentStore(settings=settings)


def to_domain_invoice(data: dict) -> Invoice:
    """Convert scenario dict to domain Invoice, safely casting monetary floats to Decimal."""
    items = []
    for it in data.get("line_items", []):
        items.append(
            LineItem(
                item_id=it.get("item_id"),
                description=it["description"],
                quantity=Decimal(str(it.get("quantity", 1))),
                unit_price=Decimal(str(it["unit_price"])),
                amount=Decimal(str(it["amount"])),
            )
        )
    return Invoice(
        invoice_id=data["invoice_id"],
        invoice_number=data["invoice_number"],
        vendor_id=data["vendor_id"],
        vendor_name=data["vendor_name"],
        customer_name=data.get("customer_name", "Global Enterprise Inc"),
        invoice_date=date.fromisoformat(data["invoice_date"]),
        currency=data.get("currency", "USD"),
        subtotal=Decimal(str(data["subtotal"])),
        tax=Decimal(str(data["tax"])),
        discount=Decimal(str(data.get("discount", 0))),
        shipping=Decimal(str(data.get("shipping", 0))),
        total=Decimal(str(data["total"])),
        line_items=items,
    )


def seed_demo_data():
    """Explicitly seed the 3 deterministic demo scenarios."""
    print("=" * 60)
    print("LEDGERGUARD DEMO SEEDING — EXPLICIT INVOCATION")
    print("=" * 60)

    repo = get_repository()
    doc_store = get_doc_store()
    settings = get_settings()

    # 1. Scenario 1: CLEAN -> AUTO_APPROVED
    s1_data = get_scenario_1_clean()
    print(f"Seeding Scenario 1: {s1_data['invoice_id']} (Clean -> AUTO_APPROVED)...")
    inv1 = to_domain_invoice(s1_data)
    rec1 = InvoiceRecord.from_invoice(inv1, status=ProcessingState.RECEIVED)
    repo.save_record(rec1)

    # Attach synthetic S3 document
    doc_bytes = b"%PDF-1.4 Mock clean invoice document content for audit transparency"
    s3_key_1 = doc_store.upload_document(inv1.invoice_id, "clean_invoice.pdf", doc_bytes)
    rec1.document_s3_key = s3_key_1
    repo.save_record(rec1)

    # Run verification with established vendor history
    prior_inv = Invoice(
        invoice_id="TEST-HIST-APEX-00",
        invoice_number="INV-2025-099",
        vendor_id="VEND-APEX",
        vendor_name="Apex Cloud Technologies LLC",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2025, 12, 15),
        currency="USD",
        subtotal=Decimal("500.00"),
        tax=Decimal("50.00"),
        discount=Decimal("0.00"),
        total=Decimal("550.00"),
        line_items=[
            LineItem(
                item_id="ITEM-099",
                description="Historical API Subscription",
                quantity=Decimal("1"),
                unit_price=Decimal("500.00"),
                amount=Decimal("500.00"),
            )
        ],
    )
    history = [prior_inv]
    decision_result_1, _meta1 = run_verification_workflow(
        invoice=inv1,
        history=history,
        settings=settings,
    )

    # Persist verified state
    rec1.processing_status = ProcessingState.AUTO_APPROVED
    rec1.decision = decision_result_1.decision
    rec1.risk_level = decision_result_1.risk_level or RiskLevel.LOW
    rec1.risk_score = decision_result_1.risk_score or 5
    rec1.verification_summary = {
        "arithmetic": {
            "is_valid": True,
            "computed_subtotal": float(inv1.subtotal),
            "declared_subtotal": float(inv1.subtotal),
            "computed_total": float(inv1.total),
            "declared_total": float(inv1.total),
        },
        "duplicate": {
            "is_duplicate": False,
            "details": "No duplicate invoice number found in historical records.",
        },
        "vendor_history": {
            "vendor_exists": True,
            "is_new_vendor": False,
            "historical_invoice_count": 5,
            "average_amount": 1250.00,
            "amount_deviation_factor": 1.05,
        },
        "policy": {
            "is_compliant": True,
            "violations": [],
        },
        "risk": {
            "risk_score": decision_result_1.risk_score or 5,
            "risk_level": decision_result_1.risk_level.value if decision_result_1.risk_level else "LOW",
            "risk_factors": [],
        },
        "reasoning": decision_result_1.summary,
        "guard_override": False,
    }
    repo.save_record(rec1)
    repo.save_audit_event(AuditEvent(
        invoice_id=inv1.invoice_id,
        event_type=AuditEventType.DECISION_GUARDED,
        timestamp=rec1.updated_at,
        details={"decision": "AUTO_APPROVE", "risk_score": rec1.risk_score},
    ))
    print(f" -> [PASS] {inv1.invoice_id}: AUTO_APPROVED")

    # 2. Scenario 2: RISKY -> MANUAL_REVIEW
    s2_data = get_scenario_2_risky()
    print(f"Seeding Scenario 2: {s2_data['invoice_id']} (Risky -> MANUAL_REVIEW)...")
    inv2 = to_domain_invoice(s2_data)
    rec2 = InvoiceRecord.from_invoice(inv2, status=ProcessingState.RECEIVED)
    repo.save_record(rec2)

    doc_bytes_2 = b"%PDF-1.4 Mock risky consulting invoice document"
    s3_key_2 = doc_store.upload_document(inv2.invoice_id, "risky_consulting.pdf", doc_bytes_2)
    rec2.document_s3_key = s3_key_2

    # High amount policy threshold trigger
    policy_cfg = PolicyConfig(auto_approval_threshold=Decimal("10000.00"))
    decision_result_2, _meta2 = run_verification_workflow(
        invoice=inv2,
        history=(),
        policy_config=policy_cfg,
        settings=settings,
    )

    rec2.processing_status = ProcessingState.MANUAL_REVIEW
    rec2.decision = AgentDecision.MANUAL_REVIEW
    rec2.risk_level = decision_result_2.risk_level or RiskLevel.MEDIUM
    rec2.risk_score = decision_result_2.risk_score or 55
    rec2.verification_summary = {
        "arithmetic": {"is_valid": True, "computed_total": float(inv2.total), "declared_total": float(inv2.total)},
        "duplicate": {"is_duplicate": False, "details": "Unique invoice record."},
        "vendor_history": {"vendor_exists": False, "is_new_vendor": True, "historical_invoice_count": 0},
        "policy": {
            "is_compliant": False,
            "violations": ["Total $60,500.00 exceeds auto-approval ceiling $10,000.00", "New vendor requiring vendor onboarding audit"],
        },
        "risk": {
            "risk_score": 55,
            "risk_level": "MEDIUM",
            "risk_factors": ["NEW_VENDOR", "HIGH_VALUE_TRANSACTION"],
        },
        "reasoning": "High-value invoice for unverified new vendor Nova Advisory Partners exceeds auto-approval threshold of $10,000.00. Routing to AP auditor for manual review.",
        "guard_override": False,
    }
    repo.save_record(rec2)
    repo.save_audit_event(AuditEvent(
        invoice_id=inv2.invoice_id,
        event_type=AuditEventType.DECISION_GUARDED,
        timestamp=rec2.updated_at,
        details={"decision": "MANUAL_REVIEW", "reason": "HIGH_VALUE_TRANSACTION"},
    ))
    print(f" -> [PASS] {inv2.invoice_id}: MANUAL_REVIEW")

    # 3. Scenario 3: DUPLICATE / CRITICAL RISK -> Decision Guard -> BLOCKED
    s3_data = get_scenario_3_blocked(duplicate_of=inv1.invoice_number)
    print(f"Seeding Scenario 3: {s3_data['invoice_id']} (Duplicate / Critical Risk -> BLOCKED)...")
    inv3 = to_domain_invoice(s3_data)
    rec3 = InvoiceRecord.from_invoice(inv3, status=ProcessingState.RECEIVED)
    repo.save_record(rec3)

    doc_bytes_3 = b"%PDF-1.4 Mock duplicate invoice payload"
    s3_key_3 = doc_store.upload_document(inv3.invoice_id, "duplicate_invoice.pdf", doc_bytes_3)
    rec3.document_s3_key = s3_key_3

    # Duplicate detected against inv1
    decision_result_3, _meta3 = run_verification_workflow(
        invoice=inv3,
        history=(inv1,),
        settings=settings,
    )

    rec3.processing_status = ProcessingState.BLOCKED
    rec3.decision = AgentDecision.BLOCK
    rec3.original_decision = AgentDecision.AUTO_APPROVE  # Agent proposed approval, Guard overrode
    rec3.risk_level = RiskLevel.CRITICAL
    rec3.risk_score = 95
    rec3.verification_summary = {
        "arithmetic": {"is_valid": True, "computed_total": float(inv3.total), "declared_total": float(inv3.total)},
        "duplicate": {
            "is_duplicate": True,
            "duplicate_type": "EXACT_INVOICE_NUMBER",
            "existing_invoice_id": inv1.invoice_id,
            "details": f"Collision: Invoice number {inv3.invoice_number} already recorded under {inv1.invoice_id}.",
        },
        "vendor_history": {"vendor_exists": True, "is_new_vendor": False},
        "policy": {"is_compliant": False, "violations": ["Duplicate invoice submission prohibited."]},
        "risk": {
            "risk_score": 95,
            "risk_level": "CRITICAL",
            "risk_factors": ["CONFIRMED_DUPLICATE", "CRITICAL_RISK"],
        },
        "reasoning": "Agent initially evaluated payload structure, but deterministic duplicate detection identified an exact invoice number collision with previously settled record.",
        "guard_override": True,
        "guard_original_decision": "AUTO_APPROVE",
        "guard_rule_triggered": "Decision Guard Rule 1: Confirmed duplicate invoice submission strictly requires BLOCK verdict.",
    }
    repo.save_record(rec3)
    repo.save_audit_event(AuditEvent(
        invoice_id=inv3.invoice_id,
        event_type=AuditEventType.DECISION_GUARDED,
        timestamp=rec3.updated_at,
        details={
            "agent_proposal": "AUTO_APPROVE",
            "guard_verdict": "BLOCK",
            "reason": "CONFIRMED_DUPLICATE",
            "collided_with": inv1.invoice_id,
        },
    ))
    print(f" -> [PASS] {inv3.invoice_id}: Decision Guard -> BLOCKED (Guard Override)")

    print("=" * 60)
    print("DEMO SEEDING COMPLETE: 3 Scenarios Successfully Ingested")
    print("=" * 60)


def cleanup_demo_data():
    """Safely delete only DEMO- and TEST-prefixed records."""
    print("=" * 60)
    print("LEDGERGUARD DEMO CLEANUP — PURGING TEST RECORDS")
    print("=" * 60)

    repo = get_repository()
    doc_store = get_doc_store()

    # Find all demo records
    all_records = repo.list_records(limit=1000)
    demo_records = [r for r in all_records if any(r.invoice_id.startswith(p) for p in DEMO_PREFIXES)]

    print(f"Found {len(demo_records)} demo/test records to purge.")
    for r in demo_records:
        if r.document_s3_key:
            try:
                doc_store.delete_document(r.document_s3_key)
                print(f"Deleted S3 object: {r.document_s3_key}")
            except Exception as e:
                print(f"Warning: Could not delete S3 object {r.document_s3_key}: {e}")

        # Delete metadata & events in DynamoDB
        pk = f"INVOICE#{r.invoice_id}"
        events = repo.get_audit_events(r.invoice_id)
        for ev in events:
            sk = f"EVENT#{ev.timestamp}#{ev.event_id}"
            repo._table.delete_item(Key={"PK": pk, "SK": sk})

        repo._table.delete_item(Key={"PK": pk, "SK": "METADATA"})
        print(f"Deleted DynamoDB invoice: {r.invoice_id}")

    print("=" * 60)
    print(f"CLEANUP COMPLETE: Purged {len(demo_records)} demo records.")
    print("=" * 60)


def show_status():
    """Display status of seeded demo invoices."""
    repo = get_repository()
    stats = repo.get_dashboard_stats()
    print("Current Repository Stats:")
    print(f"  Total Invoices: {stats['total_invoices']}")
    print(f"  Auto-Approved: {stats['auto_approved_count']}")
    print(f"  Manual Review: {stats['manual_review_count']}")
    print(f"  Blocked: {stats['blocked_count']}")
    print(f"  Total USD: ${stats['total_amount_usd']:.2f}")


def main():
    parser = argparse.ArgumentParser(description="LedgerGuard Demo Data Seeder")
    parser.add_argument("--seed", action="store_true", help="Seed deterministic demo scenarios")
    parser.add_argument("--cleanup", action="store_true", help="Purge all DEMO/TEST-prefixed records")
    parser.add_argument("--status", action="store_true", help="Show current invoice statistics")
    args = parser.parse_args()

    if args.cleanup:
        cleanup_demo_data()
    elif args.seed:
        seed_demo_data()
    elif args.status:
        show_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
