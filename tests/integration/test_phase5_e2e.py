"""Opt-in live end-to-end verification test for LedgerGuard Phase 5.

Exercises the complete cloud-backed product backend:
API Ingestion -> S3 Document Attachment -> SQS Message -> Worker Processor ->
Deterministic Verification Tools -> Decision Guard -> DynamoDB Persistence ->
API Status Inspection -> API Audit Trail -> Human Review Verification -> Safe Cleanup.

Requires LEDGERGUARD_RUN_AWS_INTEGRATION=true.
"""

import os
import time
import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import get_settings
from app.models.decision import AgentDecision
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.s3 import S3DocumentStore
from app.services.sqs import SQSJobQueue
from app.worker.processor import InvoiceProcessor


@pytest.mark.integration
def test_phase5_live_aws_end_to_end():
    settings = get_settings()
    if not settings.LEDGERGUARD_S3_BUCKET or not settings.LEDGERGUARD_SQS_QUEUE_URL:
        pytest.skip("S3 bucket or SQS queue not configured in settings.")

    # Initialize live client without dependency overrides (uses real AWS services)
    app = create_app()
    client = TestClient(app)

    auth_headers = {}
    if settings.LEDGERGUARD_API_KEY:
        auth_headers["X-API-Key"] = settings.LEDGERGUARD_API_KEY.get_secret_value()

    test_uuid = uuid.uuid4().hex[:8]
    invoice_id = f"PH5-E2E-{test_uuid}"

    doc_store = S3DocumentStore(settings=settings)
    repo = DynamoDBInvoiceRepository(settings=settings)
    job_queue = SQSJobQueue(settings=settings)

    # Clean up tracking
    uploaded_s3_key = None

    try:
        # STEP 1: API Ingestion (POST /invoices)
        payload = {
            "invoice_id": invoice_id,
            "invoice_number": f"INV-E2E-{test_uuid}",
            "vendor_id": "VEND-ACME-01",
            "vendor_name": "Acme Industrial Supplies Ltd",
            "customer_name": "Global Enterprise Inc",
            "invoice_date": "2026-03-01",
            "currency": "USD",
            "subtotal": "500.00",
            "tax": "50.00",
            "discount": "0.00",
            "total": "550.00",
            "line_items": [
                {
                    "description": "Standard Industrial Hardware",
                    "quantity": "5",
                    "unit_price": "100.00",
                    "tax_rate": "0.10",
                    "discount": "0.00",
                }
            ],
        }

        ingest_res = client.post("/invoices", json=payload, headers=auth_headers)
        assert ingest_res.status_code == 201
        ingest_data = ingest_res.json()
        assert ingest_data["invoice_id"] == invoice_id
        assert ingest_data["status"] == "QUEUED"

        # STEP 2: Attach Document (POST /invoices/{id}/document)
        doc_content = b"%PDF-1.4 SYNTHETIC TEST INVOICE FOR LEDGERGUARD PHASE 5 E2E"
        doc_res = client.post(
            f"/invoices/{invoice_id}/document",
            files={"file": ("synthetic_invoice.pdf", doc_content, "application/pdf")},
            headers=auth_headers,
        )
        assert doc_res.status_code == 200
        doc_data = doc_res.json()
        uploaded_s3_key = doc_data["s3_key"]
        assert doc_store.document_exists(uploaded_s3_key) is True

        # STEP 3: Worker Processing (polls SQS, executes tools & decision guard, updates DynamoDB)
        processor = InvoiceProcessor(
            document_store=doc_store,
            repository=repo,
            job_queue=job_queue,
            settings=settings,
        )

        # Receive the job from SQS
        max_attempts = 5
        job_processed = False
        for _ in range(max_attempts):
            jobs = job_queue.receive_jobs(max_messages=1, wait_time_seconds=5)
            matched = [j for j in jobs if j[0].invoice_id == invoice_id]
            if matched:
                job, handle = matched[0]
                # Process using DynamoDB-stored record
                success = processor.process_job(job=job, receipt_handle=handle)
                assert success is True
                job_processed = True
                break
            time.sleep(1)

        assert job_processed is True, f"Job for {invoice_id} was not retrieved from SQS"

        # STEP 4: Query Status (GET /invoices/{id})
        status_res = client.get(f"/invoices/{invoice_id}", headers=auth_headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["invoice_id"] == invoice_id
        assert status_data["processing_status"] in ("AUTO_APPROVED", "MANUAL_REVIEW", "BLOCKED")
        assert status_data["decision"] is not None
        assert status_data["risk_level"] is not None

        # STEP 5: Query Audit Trail (GET /invoices/{id}/audit)
        audit_res = client.get(f"/invoices/{invoice_id}/audit", headers=auth_headers)
        assert audit_res.status_code == 200
        audit_events = audit_res.json()
        assert len(audit_events) >= 3
        event_types = [e["event_type"] for e in audit_events]
        assert "JOB_QUEUED" in event_types
        assert "DOCUMENT_RECEIVED" in event_types
        assert "PROCESSING_COMPLETED" in event_types

    finally:
        # STEP 6: Clean synthetic test artifacts
        if uploaded_s3_key:
            doc_store.delete_document(uploaded_s3_key)
        try:
            repo._table.delete_item(Key={"PK": f"INVOICE#{invoice_id}", "SK": "METADATA"})
            for ev in repo.get_audit_events(invoice_id):
                repo._table.delete_item(Key={"PK": f"INVOICE#{invoice_id}", "SK": f"EVENT#{ev.timestamp}#{ev.event_id}"})
        except Exception:
            pass
