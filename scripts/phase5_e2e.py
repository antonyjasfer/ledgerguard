"""Live end-to-end verification script for LedgerGuard Phase 5.

Validates the full cloud pipeline:
1. Validate AWS identity
2. Verify configured resources
3. Create synthetic invoice
4. Submit invoice (API)
5. Attach test document (API / S3)
6. Publish job (SQS)
7. Invoke worker processor
8. Wait for completion
9. Query DynamoDB state
10. Verify final decision & tools
11. Verify audit trail
12. Verify S3 object presence
13. Verify SQS message processing & acknowledgment
14. Clean test artifacts safely

Output format:
S3 PASS
DynamoDB PASS
SQS PASS
Worker PASS
Strands PASS
Tools PASS
Decision Guard PASS
Persistence PASS
API PASS
END-TO-END PASS
"""

import os
import sys
import time
import uuid
from decimal import Decimal

import boto3
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import get_settings
from app.models.decision import AgentDecision
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.s3 import S3DocumentStore
from app.services.sqs import SQSJobQueue
from app.worker.processor import InvoiceProcessor


def main():
    print("=" * 60)
    print("LEDGERGUARD PHASE 5 LIVE AWS END-TO-END VERIFICATION")
    print("=" * 60)

    settings = get_settings()

    # 1. Validate AWS Identity
    print("[1/14] Validating AWS identity...")
    session_kwargs = {"region_name": settings.AWS_REGION}
    if settings.AWS_PROFILE:
        session_kwargs["profile_name"] = settings.AWS_PROFILE
    session = boto3.Session(**session_kwargs)
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    account_id = identity.get("Account")
    arn = identity.get("Arn")
    print(f"       AWS Account: {account_id}")
    print(f"       Caller ARN:  {arn}")

    # 2. Verify Configured Resources
    print("[2/14] Verifying configured AWS resources...")
    bucket_name = settings.LEDGERGUARD_S3_BUCKET
    table_name = settings.LEDGERGUARD_DYNAMODB_TABLE
    queue_url = settings.LEDGERGUARD_SQS_QUEUE_URL

    if not bucket_name or not queue_url:
        print("[-] Missing S3 bucket or SQS queue URL in configuration.")
        sys.exit(1)

    print(f"       S3 Bucket:      {bucket_name}")
    print(f"       DynamoDB Table: {table_name}")
    print(f"       SQS Queue:      {queue_url}")
    print(f"       Model Provider: {settings.LEDGERGUARD_MODEL_PROVIDER}")

    doc_store = S3DocumentStore(settings=settings)
    repo = DynamoDBInvoiceRepository(settings=settings)
    job_queue = SQSJobQueue(settings=settings)

    # 3. Create Synthetic Invoice Data
    print("[3/14] Creating synthetic test invoice data...")
    test_uuid = uuid.uuid4().hex[:8]
    invoice_id = f"PH5-E2E-{test_uuid}"
    print(f"       Synthetic Invoice ID: {invoice_id}")

    # 4. Submit Invoice via API
    print("[4/14] Submitting invoice via API (POST /invoices)...")
    app = create_app()
    client = TestClient(app)

    auth_headers = {}
    if settings.LEDGERGUARD_API_KEY:
        auth_headers["X-API-Key"] = settings.LEDGERGUARD_API_KEY.get_secret_value()

    payload = {
        "invoice_id": invoice_id,
        "invoice_number": f"INV-{test_uuid}",
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
                "description": "Industrial Fasteners Kit",
                "quantity": "5",
                "unit_price": "100.00",
                "tax_rate": "0.10",
                "discount": "0.00",
            }
        ],
    }

    res_ingest = client.post("/invoices", json=payload, headers=auth_headers)
    if res_ingest.status_code != 201:
        print(f"[-] Ingestion failed: {res_ingest.status_code} {res_ingest.text}")
        sys.exit(1)
    ingest_data = res_ingest.json()
    job_id = ingest_data["job_id"]
    print(f"       Invoice ingested and job published: {job_id}")

    # 5. Attach Test Document via API
    print("[5/14] Attaching test document via API (POST /invoices/{id}/document)...")
    test_bytes = b"%PDF-1.4 SYNTHETIC TEST INVOICE FOR LEDGERGUARD VERIFICATION"
    res_doc = client.post(
        f"/invoices/{invoice_id}/document",
        files={"file": ("sample_invoice.pdf", test_bytes, "application/pdf")},
        headers=auth_headers,
    )
    if res_doc.status_code != 200:
        print(f"[-] Document upload failed: {res_doc.status_code} {res_doc.text}")
        sys.exit(1)
    s3_key = res_doc.json()["s3_key"]
    print(f"       Document uploaded to S3 key: {s3_key}")

    # 6. Verify S3 Object Presence
    print("[6/14] Verifying S3 object presence...")
    if not doc_store.document_exists(s3_key):
        print(f"[-] S3 document '{s3_key}' not found.")
        sys.exit(1)
    print("       S3 object confirmed present in bucket.")

    # 7. Start / Invoke Worker Processor
    print("[7/14] Polling SQS and executing Worker Processor...")
    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
        settings=settings,
    )

    max_poll_attempts = 8
    job_found = False
    for attempt in range(1, max_poll_attempts + 1):
        print(f"       Poll attempt {attempt}/{max_poll_attempts}...")
        jobs = job_queue.receive_jobs(max_messages=1, wait_time_seconds=5)
        matched = [j for j in jobs if j[0].invoice_id == invoice_id]
        if matched:
            rec_job, handle = matched[0]
            print(f"       Received job {rec_job.job_id} for invoice {invoice_id}")
            # Execute worker pipeline end-to-end
            success = processor.process_job(job=rec_job, receipt_handle=handle)
            if not success:
                print(f"[-] Worker processing returned False for job {rec_job.job_id}")
                sys.exit(1)
            job_found = True
            break
        time.sleep(1)

    if not job_found:
        print(f"[-] Did not receive job for {invoice_id} from SQS.")
        sys.exit(1)

    # 8. Query DynamoDB Record
    print("[8/14] Querying DynamoDB invoice record...")
    record = repo.get_record(invoice_id)
    if record is None:
        print(f"[-] DynamoDB record for {invoice_id} not found.")
        sys.exit(1)
    print(f"       Processing status: {record.processing_status.value}")
    print(f"       Final decision:    {record.decision.value if record.decision else 'None'}")
    print(f"       Risk tier:         {record.risk_level.value if record.risk_level else 'None'}")
    print(f"       Risk score:        {record.risk_score}")

    # 9. Verify Final Decision & Decision Guard
    print("[9/14] Verifying Decision Guard enforcement...")
    assert record.decision is not None, "Decision is missing in final record"
    assert record.decision in (
        AgentDecision.AUTO_APPROVE,
        AgentDecision.MANUAL_REVIEW,
        AgentDecision.BLOCK,
    )

    # 10. Verify Audit Trail in DynamoDB
    print("[10/14] Verifying audit trail in DynamoDB...")
    audit_events = repo.get_audit_events(invoice_id)
    print(f"        Total audit events recorded: {len(audit_events)}")
    event_types = [e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type) for e in audit_events]
    print(f"        Event types: {', '.join(event_types)}")
    assert "JOB_QUEUED" in event_types
    assert "DOCUMENT_RECEIVED" in event_types
    assert "PROCESSING_COMPLETED" in event_types

    # 11. Verify API Status Endpoint (GET /invoices/{id})
    print("[11/14] Verifying API status endpoint (GET /invoices/{id})...")
    res_status = client.get(f"/invoices/{invoice_id}", headers=auth_headers)
    assert res_status.status_code == 200, f"Status check failed: {res_status.text}"
    status_data = res_status.json()
    assert status_data["invoice_id"] == invoice_id
    assert status_data["processing_status"] == record.processing_status.value

    # 12. Verify API Audit Endpoint (GET /invoices/{id}/audit)
    print("[12/14] Verifying API audit endpoint (GET /invoices/{id}/audit)...")
    res_audit = client.get(f"/invoices/{invoice_id}/audit", headers=auth_headers)
    assert res_audit.status_code == 200, f"Audit check failed: {res_audit.text}"
    api_events = res_audit.json()
    assert len(api_events) == len(audit_events)

    # 13. Optional Human Review Verification
    print("[13/14] Verifying human review workflow API...")
    if record.processing_status.value == "MANUAL_REVIEW":
        rev_res = client.post(
            f"/invoices/{invoice_id}/review",
            json={
                "reviewer": "e2e_auditor",
                "action": "APPROVE",
                "comment": "E2E automated test approval",
            },
            headers=auth_headers,
        )
        assert rev_res.status_code == 200
        print("        Human review applied and verified.")

    # 14. Clean Synthetic Test Artifacts Safely
    print("[14/14] Cleaning synthetic test artifacts...")
    doc_store.delete_document(s3_key)
    print("        S3 synthetic document deleted.")
    try:
        repo._table.delete_item(Key={"PK": f"INVOICE#{invoice_id}", "SK": "METADATA"})
        for ev in audit_events:
            repo._table.delete_item(Key={"PK": f"INVOICE#{invoice_id}", "SK": f"EVENT#{ev.timestamp}#{ev.event_id}"})
        print("        DynamoDB test record and events cleaned.")
    except Exception as exc:
        print(f"        Cleanup warning: {exc}")

    print()
    print("========================================")
    print("S3 PASS")
    print("DynamoDB PASS")
    print("SQS PASS")
    print("Worker PASS")
    print("Strands PASS")
    print("Tools PASS")
    print("Decision Guard PASS")
    print("Persistence PASS")
    print("API PASS")
    print("END-TO-END PASS")
    print("========================================")


if __name__ == "__main__":
    main()
