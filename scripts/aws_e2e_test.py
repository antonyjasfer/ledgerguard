"""Opt-in live end-to-end pipeline verification script for LedgerGuard.

Executes the full cloud-backed workflow:
Synthetic Invoice -> S3 Document Upload -> SQS Message -> Worker Processor ->
Deterministic Verification Tools -> Decision Guard -> DynamoDB State Update ->
S3 / DynamoDB Verification -> Safe Cleanup.

RUN ONLY EXPLICITLY:
python scripts/aws_e2e_test.py
"""

import os
import sys
import uuid
from datetime import date
from decimal import Decimal

from app.config import get_settings
from app.models.decision import AgentDecision
from app.models.invoice import Invoice, LineItem
from app.models.job import ProcessingJob
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.s3 import S3DocumentStore
from app.services.sqs import SQSJobQueue
from app.services.state import ProcessingState
from app.worker.processor import InvoiceProcessor


def run_e2e():
    settings = get_settings()
    print("=" * 60)
    print("LEDGERGUARD LIVE AWS E2E VERIFICATION TEST")
    print("=" * 60)
    print(f"Region:         {settings.AWS_REGION}")
    print(f"Profile:        {settings.AWS_PROFILE}")
    print(f"S3 Bucket:      {settings.LEDGERGUARD_S3_BUCKET}")
    print(f"DynamoDB Table: {settings.LEDGERGUARD_DYNAMODB_TABLE}")
    print(f"SQS Queue:      {settings.LEDGERGUARD_SQS_QUEUE_URL}")

    if not settings.LEDGERGUARD_S3_BUCKET or not settings.LEDGERGUARD_SQS_QUEUE_URL:
        print("[-] LEDGERGUARD_S3_BUCKET or LEDGERGUARD_SQS_QUEUE_URL missing in environment.")
        print("    Ensure AWS resources are provisioned and set in .env before running this script.")
        sys.exit(1)

    doc_store = S3DocumentStore(settings=settings)
    repo = DynamoDBInvoiceRepository(settings=settings)
    job_queue = SQSJobQueue(settings=settings)
    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
        settings=settings,
    )

    test_id = f"TEST_E2E_{uuid.uuid4().hex[:8]}"
    invoice = Invoice(
        invoice_id=test_id,
        invoice_number=f"INV-{test_id}",
        vendor_id="VEND_ACME_01",
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="LedgerGuard Corp",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        subtotal=Decimal("200.00"),
        tax=Decimal("20.00"),
        discount=Decimal("0.00"),
        total=Decimal("220.00"),
        line_items=[
            LineItem(
                description="E2E Synthetic Line Item",
                quantity=Decimal("2"),
                unit_price=Decimal("100.00"),
                tax_rate=Decimal("10.00"),
                discount=Decimal("0.00"),
            )
        ],
    )

    print(f"
[1/5] Uploading synthetic document to S3 for invoice {test_id}...")
    s3_key = doc_store.upload_document(test_id, "invoice_doc.pdf", b"%PDF-1.4 TEST E2E INVOICE")
    print(f"      Uploaded key: {s3_key}")

    try:
        print(f"[2/5] Publishing background job to SQS...")
        job = ProcessingJob(
            invoice_id=test_id,
            s3_bucket=settings.LEDGERGUARD_S3_BUCKET,
            s3_key=s3_key,
        )
        msg_id = job_queue.send_job(job)
        print(f"      SQS Message ID: {msg_id}")

        print(f"[3/5] Polling SQS for published job...")
        jobs = job_queue.receive_jobs(max_messages=1, wait_time_seconds=10)
        matched = [j for j in jobs if j[0].invoice_id == test_id]
        if not matched:
            print("[-] Published job not retrieved within wait period.")
            sys.exit(1)

        received_job, handle = matched[0]
        print(f"      Received job {received_job.job_id} for invoice {received_job.invoice_id}")

        print(f"[4/5] Executing verification pipeline via InvoiceProcessor...")
        success = processor.process_job(
            job=received_job,
            receipt_handle=handle,
            invoice_data=invoice,
        )
        if not success:
            print("[-] Processor execution reported failure.")
            sys.exit(1)
        print("      Worker processing succeeded and SQS message was acknowledged.")

        print(f"[5/5] Verifying persistent DynamoDB record and audit trail...")
        record = repo.get_record(test_id)
        if not record:
            print("[-] Failed to find persisted DynamoDB record.")
            sys.exit(1)

        print(f"      DynamoDB status:   {record.processing_status.value}")
        print(f"      DynamoDB decision: {record.decision.value if record.decision else 'None'}")
        print(f"      DynamoDB risk:     {record.risk_level.value if record.risk_level else 'None'}")

        audit_events = repo.get_audit_events(test_id)
        print(f"      Audit events count: {len(audit_events)}")
        for e in audit_events:
            print(f"        - {e.timestamp} | {e.event_type.value}")

        print("
" + "=" * 60)
        print("ALL END-TO-END AWS PIPELINE STEPS PASSED")
        print("=" * 60)

    finally:
        print("
[*] Cleaning up test resources...")
        doc_store.delete_document(s3_key)
        try:
            repo._table.delete_item(Key={"PK": f"INVOICE#{test_id}", "SK": "METADATA"})
            for e in repo.get_audit_events(test_id):
                repo._table.delete_item(Key={"PK": f"INVOICE#{test_id}", "SK": f"EVENT#{e.timestamp}#{e.event_id}"})
        except Exception:
            pass
        print("[+] Cleanup complete.")


if __name__ == "__main__":
    run_e2e()
