"""Offline unit tests for audit trail retrieval routes."""

from app.models.audit import AuditEvent, AuditEventType
from app.models.persistence import InvoiceRecord


def test_get_invoice_audit_trail_success(client, mock_repo, auth_headers):
    """Querying audit trail returns ordered, structured audit events."""
    record = InvoiceRecord(
        invoice_id="INV-AUDIT-01",
        invoice_number="NUM-01",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
    )
    mock_repo.save_record(record)

    evt1 = AuditEvent(
        invoice_id="INV-AUDIT-01",
        event_type=AuditEventType.DOCUMENT_RECEIVED,
        details={"key": "invoices/INV-AUDIT-01/doc.pdf"},
    )
    evt2 = AuditEvent(
        invoice_id="INV-AUDIT-01",
        event_type=AuditEventType.JOB_QUEUED,
        details={"queue": "test-queue"},
    )
    mock_repo.save_audit_event(evt1)
    mock_repo.save_audit_event(evt2)

    response = client.get("/invoices/INV-AUDIT-01/audit", headers=auth_headers)
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 2
    assert events[0]["event_type"] == "DOCUMENT_RECEIVED"
    assert events[1]["event_type"] == "JOB_QUEUED"


def test_get_audit_trail_not_found(client, auth_headers):
    """Querying audit events for nonexistent invoice returns 404."""
    response = client.get("/invoices/INV-NONEXISTENT/audit", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"] == "INVOICE_NOT_FOUND"
