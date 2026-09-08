"""Offline unit tests for invoice ingestion routes."""

from decimal import Decimal

from app.models.persistence import InvoiceRecord
from app.services.state import ProcessingState


def test_create_invoice_success(client, mock_repo, mock_queue, auth_headers):
    """Valid structured invoice ingestion persists record and dispatches SQS job."""
    payload = {
        "invoice_id": "INV-TEST-001",
        "invoice_number": "ACME-1001",
        "vendor_id": "VEND-ACME-01",
        "vendor_name": "Acme Industrial Corp",
        "customer_name": "Global Enterprise Inc",
        "invoice_date": "2026-03-01",
        "currency": "USD",
        "subtotal": "1000.00",
        "tax": "100.00",
        "discount": "0.00",
        "total": "1100.00",
        "line_items": [
            {
                "description": "Industrial Widget A",
                "quantity": "10",
                "unit_price": "100.00",
                "tax_rate": "0.10",
                "discount": "0.00",
            }
        ],
    }

    response = client.post("/invoices", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["invoice_id"] == "INV-TEST-001"
    assert data["status"] == "QUEUED"
    assert data["processing_status"] == "QUEUED"
    assert data["job_id"].startswith("job_")

    # Verify repository persistence
    record = mock_repo.get_record("INV-TEST-001")
    assert record is not None
    assert record.total == Decimal("1100.00")
    assert record.processing_status == ProcessingState.QUEUED

    # Verify SQS dispatch
    assert len(mock_queue.jobs) == 1
    assert mock_queue.jobs[0].invoice_id == "INV-TEST-001"

    # Verify audit event emitted
    events = mock_repo.get_audit_events("INV-TEST-001")
    assert len(events) == 1
    assert events[0].event_type == "JOB_QUEUED"


def test_create_invoice_rejects_floating_point(client, auth_headers):
    """Financial fields must strictly reject float types to prevent precision loss."""
    payload = {
        "invoice_id": "INV-TEST-FLOAT",
        "invoice_number": "ACME-FLOAT",
        "vendor_id": "VEND-01",
        "vendor_name": "Acme Corp",
        "invoice_date": "2026-03-01",
        "total": 1100.50,  # float literal in JSON
    }

    response = client.post("/invoices", json=payload, headers=auth_headers)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"


def test_create_invoice_idempotency_queued(client, mock_repo, mock_queue, auth_headers):
    """Re-submitting an already queued invoice safely returns existing job without duplicate dispatch."""
    payload = {
        "invoice_id": "INV-IDEM-01",
        "invoice_number": "NUM-01",
        "vendor_id": "VEND-01",
        "vendor_name": "Vendor 1",
        "invoice_date": "2026-03-01",
        "total": "500.00",
    }

    # First submission
    res1 = client.post("/invoices", json=payload, headers=auth_headers)
    assert res1.status_code == 201
    assert len(mock_queue.jobs) == 1
    job_id_first = res1.json()["job_id"]

    # Repeated submission
    res2 = client.post("/invoices", json=payload, headers=auth_headers)
    assert res2.status_code == 200
    assert res2.json()["invoice_id"] == "INV-IDEM-01"
    assert res2.json()["job_id"] == job_id_first
    # SQS jobs queue count must not increase
    assert len(mock_queue.jobs) == 1


def test_create_invoice_idempotency_terminal_conflict(client, mock_repo, auth_headers):
    """Submitting an invoice that has already completed terminal processing raises 409 Conflict."""
    terminal_rec = InvoiceRecord(
        invoice_id="INV-TERM-01",
        invoice_number="NUM-TERM",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
        processing_status=ProcessingState.AUTO_APPROVED,
    )
    mock_repo.save_record(terminal_rec)

    payload = {
        "invoice_id": "INV-TERM-01",
        "invoice_number": "NUM-TERM",
        "vendor_id": "VEND-01",
        "vendor_name": "Vendor 1",
        "invoice_date": "2026-03-01",
        "total": "500.00",
    }

    response = client.post("/invoices", json=payload, headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error"] == "CONFLICT"
    assert "terminal state" in response.json()["message"]
