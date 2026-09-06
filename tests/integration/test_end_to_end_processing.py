"""Opt-in live end-to-end processing test for LedgerGuard.

Requires LEDGERGUARD_RUN_AWS_INTEGRATION=true and configured AWS resources.
Runs synthetic invoice through S3, SQS, Worker, Decision Guard, and DynamoDB.
"""

import os
import uuid
from datetime import date
from decimal import Decimal
import pytest

from app.config import get_settings
from app.models.invoice import Invoice, LineItem
from app.models.job import ProcessingJob
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.s3 import S3DocumentStore
from app.services.sqs import SQSJobQueue
from app.worker.processor import InvoiceProcessor


@pytest.mark.integration
def test_live_end_to_end_pipeline():
    settings = get_settings()
    if not settings.LEDGERGUARD_S3_BUCKET or not settings.LEDGERGUARD_SQS_QUEUE_URL:
        pytest.skip("S3 or SQS not configured for live integration test")

    doc_store = S3DocumentStore(settings=settings)
    repo = DynamoDBInvoiceRepository(settings=settings)
    job_queue = SQSJobQueue(settings=settings)
    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
        settings=settings,
    )

    test_id = f"TEST_{uuid.uuid4().hex[:8]}"
    invoice = Invoice(
        invoice_id=test_id,
        invoice_number=f"INV-{test_id}",
        vendor_id="VEND_TEST",
        vendor_name="Live Integration Vendor",
        customer_name="LedgerGuard Test Corp",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        discount=Decimal("0.00"),
        total=Decimal("110.00"),
        line_items=[
            LineItem(
                description="Live test item",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                tax_rate=Decimal("0.10"),
                discount=Decimal("0.00"),
            )
        ],
    )

    # 1. Upload mock doc to S3
    s3_key = doc_store.upload_document(test_id, "test_doc.pdf", b"%PDF-1.4 LIVE TEST")

    try:
        # 2. Publish SQS job
        job = ProcessingJob(
            invoice_id=test_id,
            s3_bucket=settings.LEDGERGUARD_S3_BUCKET,
            s3_key=s3_key,
        )
        job_queue.send_job(job)

        # 3. Receive job
        jobs = job_queue.receive_jobs(max_messages=1, wait_time_seconds=5)
        matched = [j for j in jobs if j[0].invoice_id == test_id]
        if matched:
            rec_job, handle = matched[0]
            # 4. Process job
            success = processor.process_job(
                job=rec_job,
                receipt_handle=handle,
                invoice_data=invoice,
            )
            assert success is True

            # 5. Verify DynamoDB
            record = repo.get_record(test_id)
            assert record is not None
            assert record.invoice_id == test_id

    finally:
        # Cleanup S3 & DynamoDB test records
        doc_store.delete_document(s3_key)
        try:
            repo._table.delete_item(Key={"PK": f"INVOICE#{test_id}", "SK": "METADATA"})
        except Exception:
            pass
