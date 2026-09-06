"""Unit tests for DynamoDB InvoiceRepository implementation."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.models.audit import AuditEvent, AuditEventType
from app.models.decision import AgentDecision
from app.models.persistence import InvoiceRecord, _serialize_for_dynamodb
from app.models.verification import RiskLevel
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.state import ProcessingState


def test_serialize_for_dynamodb():
    """Verify data types are properly sanitized for DynamoDB Table format."""
    data = {
        "status": ProcessingState.AUTO_APPROVED,
        "amount": Decimal("150.75"),
        "score": 85,
        "tags": {"risk", "vendor"},
        "details": {"nested_enum": AgentDecision.AUTO_APPROVE},
    }
    serialized = _serialize_for_dynamodb(data)
    assert serialized["status"] == "AUTO_APPROVED"
    assert serialized["amount"] == Decimal("150.75")
    assert serialized["details"]["nested_enum"] == "AUTO_APPROVE"
    assert isinstance(serialized["tags"], set)


def test_save_record():
    """Saving invoice record puts item with PK and SK."""
    mock_table = MagicMock()
    repo = DynamoDBInvoiceRepository(table=mock_table)

    record = InvoiceRecord(
        invoice_id="inv_202",
        invoice_number="INV-202",
        vendor_id="vend_01",
        vendor_name="Acme Corp",
        invoice_date="2026-09-01",
        total=Decimal("250.00"),
        processing_status=ProcessingState.RECEIVED,
    )

    repo.save_record(record)
    mock_table.put_item.assert_called_once()
    saved_item = mock_table.put_item.call_args[1]["Item"]
    assert saved_item["PK"] == "INVOICE#inv_202"
    assert saved_item["SK"] == "METADATA"
    assert saved_item["total"] == Decimal("250.00")
    assert saved_item["processing_status"] == "RECEIVED"


def test_get_record_found():
    """Retrieving record reconstructs InvoiceRecord model."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "PK": "INVOICE#inv_202",
            "SK": "METADATA",
            "invoice_id": "inv_202",
            "invoice_number": "INV-202",
            "vendor_id": "vend_01",
            "vendor_name": "Acme Corp",
            "invoice_date": "2026-09-01",
            "currency": "USD",
            "total": Decimal("250.00"),
            "processing_status": "AUTO_APPROVED",
            "decision": "AUTO_APPROVE",
            "risk_level": "LOW",
            "created_at": "2026-09-01T00:00:00Z",
            "updated_at": "2026-09-01T00:05:00Z",
        }
    }
    repo = DynamoDBInvoiceRepository(table=mock_table)

    record = repo.get_record("inv_202")
    assert record is not None
    assert record.invoice_id == "inv_202"
    assert record.processing_status == ProcessingState.AUTO_APPROVED
    assert record.decision == AgentDecision.AUTO_APPROVE
    assert record.risk_level == RiskLevel.LOW


def test_get_record_not_found():
    """Nonexistent record returns None."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    repo = DynamoDBInvoiceRepository(table=mock_table)

    assert repo.get_record("nonexistent") is None


def test_update_status():
    """Updating status calls update_item with expression values."""
    mock_table = MagicMock()
    repo = DynamoDBInvoiceRepository(table=mock_table)

    repo.update_status(
        invoice_id="inv_303",
        status=ProcessingState.BLOCKED,
        decision=AgentDecision.BLOCK,
        updated_at="2026-09-01T12:00:00Z",
    )

    mock_table.update_item.assert_called_once()
    call_kwargs = mock_table.update_item.call_args[1]
    assert call_kwargs["Key"] == {"PK": "INVOICE#inv_303", "SK": "METADATA"}
    assert ":status" in call_kwargs["ExpressionAttributeValues"]
    assert call_kwargs["ExpressionAttributeValues"][":status"] == "BLOCKED"
    assert call_kwargs["ExpressionAttributeValues"][":decision"] == "BLOCK"


def test_save_and_get_audit_events():
    """Saving and querying audit events under the invoice partition."""
    mock_table = MagicMock()
    repo = DynamoDBInvoiceRepository(table=mock_table)

    event = AuditEvent(
        event_id="evt_001",
        invoice_id="inv_404",
        job_id="job_001",
        event_type=AuditEventType.TOOL_EXECUTED,
        timestamp="2026-09-01T10:00:00Z",
        details={"tool": "calculate_invoice_arithmetic"},
    )

    repo.save_audit_event(event)
    mock_table.put_item.assert_called_once()
    item = mock_table.put_item.call_args[1]["Item"]
    assert item["PK"] == "INVOICE#inv_404"
    assert item["SK"] == "EVENT#2026-09-01T10:00:00Z#evt_001"
    assert item["event_type"] == "TOOL_EXECUTED"

    # Query audit events
    mock_table.query.return_value = {
        "Items": [item]
    }
    events = repo.get_audit_events("inv_404")
    assert len(events) == 1
    assert events[0].event_id == "evt_001"
    assert events[0].event_type == AuditEventType.TOOL_EXECUTED


def test_is_already_processed():
    """Checks whether invoice is in a terminal completed state."""
    mock_table = MagicMock()
    repo = DynamoDBInvoiceRepository(table=mock_table)

    # Missing -> False
    mock_table.get_item.return_value = {}
    assert repo.is_already_processed("inv_505") is False

    # Processing -> False
    mock_table.get_item.return_value = {
        "Item": {
            "invoice_id": "inv_505",
            "invoice_number": "INV-505",
            "vendor_id": "v1",
            "vendor_name": "V",
            "invoice_date": "2026-01-01",
            "processing_status": "PROCESSING",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    }
    assert repo.is_already_processed("inv_505") is False

    # AUTO_APPROVED -> True
    mock_table.get_item.return_value["Item"]["processing_status"] = "AUTO_APPROVED"
    assert repo.is_already_processed("inv_505") is True


def test_idempotent_save_skips_when_terminal():
    """Idempotent save refuses to overwrite already terminal records."""
    mock_table = MagicMock()
    repo = DynamoDBInvoiceRepository(table=mock_table)

    record = InvoiceRecord(
        invoice_id="inv_606",
        invoice_number="INV-606",
        vendor_id="v1",
        vendor_name="V",
        invoice_date="2026-01-01",
        processing_status=ProcessingState.AUTO_APPROVED,
    )

    # Mock get_item returning terminal record
    mock_table.get_item.return_value = {
        "Item": record.to_dynamodb_item()
    }

    saved = repo.idempotent_save(record)
    assert saved is False
    mock_table.put_item.assert_not_called()
