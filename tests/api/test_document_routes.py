"""Offline unit tests for document attachment and S3 storage routes."""

from app.models.persistence import InvoiceRecord
from app.services.state import ProcessingState


def test_upload_document_success(client, mock_repo, mock_doc_store, auth_headers):
    """Uploading a valid document uploads to S3, links key to record, and records audit event."""
    record = InvoiceRecord(
        invoice_id="INV-DOC-01",
        invoice_number="NUM-01",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
        processing_status=ProcessingState.QUEUED,
    )
    mock_repo.save_record(record)

    file_bytes = b"%PDF-1.4 simulated pdf payload"
    response = client.post(
        "/invoices/INV-DOC-01/document",
        files={"file": ("invoice_receipt.pdf", file_bytes, "application/pdf")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["invoice_id"] == "INV-DOC-01"
    assert data["filename"] == "invoice_receipt.pdf"
    assert data["file_size"] == len(file_bytes)
    assert "invoices/INV-DOC-01/invoice_receipt.pdf" in data["s3_key"]

    # Verify S3 store double has the bytes
    stored_bytes = mock_doc_store.download_document(data["s3_key"])
    assert stored_bytes == file_bytes

    # Verify record in repo was updated
    updated_rec = mock_repo.get_record("INV-DOC-01")
    assert updated_rec.document_s3_key == data["s3_key"]

    # Verify audit event emitted
    events = mock_repo.get_audit_events("INV-DOC-01")
    assert any(e.event_type == "DOCUMENT_RECEIVED" for e in events)


def test_upload_document_plural_alias_success(client, mock_repo, mock_doc_store, auth_headers):
    """Uploading via plural /documents alias uploads to S3, links key, and records audit event."""
    record = InvoiceRecord(
        invoice_id="INV-DOC-PLURAL",
        invoice_number="NUM-PLURAL",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
        processing_status=ProcessingState.QUEUED,
    )
    mock_repo.save_record(record)

    file_bytes = b"%PDF-1.4 simulated pdf payload for plural alias"
    response = client.post(
        "/invoices/INV-DOC-PLURAL/documents",
        files={"file": ("invoice_plural.pdf", file_bytes, "application/pdf")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["invoice_id"] == "INV-DOC-PLURAL"
    assert data["filename"] == "invoice_plural.pdf"
    assert "invoices/INV-DOC-PLURAL/invoice_plural.pdf" in data["s3_key"]

    updated_rec = mock_repo.get_record("INV-DOC-PLURAL")
    assert updated_rec.document_s3_key == data["s3_key"]


def test_upload_document_nonexistent_invoice(client, auth_headers):
    """Attempting to upload a document for a missing invoice returns 404."""
    response = client.post(
        "/invoices/NONEXISTENT/document",
        files={"file": ("sample.pdf", b"content", "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"] == "INVOICE_NOT_FOUND"


def test_upload_document_path_traversal_sanitized(client, mock_repo, mock_doc_store, auth_headers):
    """Filenames with directory traversal sequences are strictly sanitized."""
    record = InvoiceRecord(
        invoice_id="INV-DOC-SAFE",
        invoice_number="NUM-01",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
    )
    mock_repo.save_record(record)

    unsafe_filename = "../../../etc/passwd.pdf"
    response = client.post(
        "/invoices/INV-DOC-SAFE/document",
        files={"file": (unsafe_filename, b"safe content", "application/pdf")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    # Directory traversal remnants must not appear in key
    assert ".." not in data["s3_key"]
    assert "passwd.pdf" in data["s3_key"]


def test_upload_document_payload_too_large(client, mock_repo, auth_headers):
    """Oversized uploads exceeding configured limit return 413 Payload Too Large."""
    record = InvoiceRecord(
        invoice_id="INV-DOC-LARGE",
        invoice_number="NUM-01",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
    )
    mock_repo.save_record(record)

    # test_settings configured limit is 1MB (1024 * 1024 bytes)
    huge_bytes = b"0" * (1024 * 1024 + 50)
    response = client.post(
        "/invoices/INV-DOC-LARGE/document",
        files={"file": ("huge.pdf", huge_bytes, "application/pdf")},
        headers=auth_headers,
    )

    assert response.status_code == 413
    assert response.json()["error"] == "PAYLOAD_TOO_LARGE"


def test_upload_document_empty_file_rejected(client, mock_repo, auth_headers):
    """Empty uploaded files return 400 Bad Request."""
    record = InvoiceRecord(
        invoice_id="INV-DOC-EMPTY",
        invoice_number="NUM-01",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
    )
    mock_repo.save_record(record)

    response = client.post(
        "/invoices/INV-DOC-EMPTY/document",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_INVOICE"
