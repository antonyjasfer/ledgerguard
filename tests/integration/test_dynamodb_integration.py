"""Opt-in live DynamoDB integration test for LedgerGuard.

Requires LEDGERGUARD_RUN_AWS_INTEGRATION=true and configured LEDGERGUARD_DYNAMODB_TABLE.
"""

import os
import uuid
from decimal import Decimal
import pytest

from app.config import get_settings
from app.models.audit import AuditEvent, AuditEventType
from app.models.persistence import InvoiceRecord
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.state import ProcessingState


@pytest.mark.integration
def test_dynamodb_live_crud_and_audit():
    settings = get_settings()
    repo = DynamoDBInvoiceRepository(settings=settings)
    test_id = f"TEST_{uuid.uuid4().hex[:8]}"

    record = InvoiceRecord(
        invoice_id=test_id,
        invoice_number=f"INV-{test_id}",
        vendor_id="VEND_TEST",
        vendor_name="Integration Test Vendor",
        invoice_date="2026-09-01",
        total=Decimal("150.00"),
        processing_status=ProcessingState.RECEIVED,
    )

    try:
        # 1. Save record
        repo.save_record(record)

        # 2. Get record
        retrieved = repo.get_record(test_id)
        assert retrieved is not None
        assert retrieved.invoice_id == test_id
        assert retrieved.total == Decimal("150.00")

        # 3. Save audit event
        event = AuditEvent(
            invoice_id=test_id,
            event_type=AuditEventType.PROCESSING_STARTED,
            details={"test_run": True},
        )
        repo.save_audit_event(event)

        # 4. Query audit events
        events = repo.get_audit_events(test_id)
        assert len(events) >= 1
        assert any(e.event_type == AuditEventType.PROCESSING_STARTED for e in events)

    finally:
        # Cleanup
        try:
            repo._table.delete_item(Key={"PK": f"INVOICE#{test_id}", "SK": "METADATA"})
            for e in repo.get_audit_events(test_id):
                repo._table.delete_item(Key={"PK": f"INVOICE#{test_id}", "SK": f"EVENT#{e.timestamp}#{e.event_id}"})
        except Exception:
            pass
