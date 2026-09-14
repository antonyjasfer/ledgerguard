"""Opt-in live AWS integration test for LedgerGuard Phase 7 Bulk Ingestion.

Requires active AWS credentials and configured environment:
- LEDGERGUARD_S3_BUCKET
- LEDGERGUARD_DYNAMODB_TABLE
- LEDGERGUARD_SQS_QUEUE_URL

Skipped by default unless LEDGERGUARD_ENABLE_LIVE_AWS_TESTS=true is set.
"""

import os
import uuid
import pytest

from app.config import get_settings
from app.models.batch import BatchRecord, BatchStatus, DocumentIngestionRecord, DocumentStatus
from app.models.job import ProcessingJob
from app.services.dynamodb import DynamoDBBatchRepository
from app.services.s3 import S3DocumentStore
from app.services.sqs import SQSJobQueue

pytestmark = pytest.mark.skipif(
    os.getenv("LEDGERGUARD_ENABLE_LIVE_AWS_TESTS", "false").lower() != "true",
    reason="Live AWS tests are opt-in. Set LEDGERGUARD_ENABLE_LIVE_AWS_TESTS=true to run.",
)


def test_live_aws_batch_ingestion_lifecycle():
    """Verify live S3 upload, DynamoDB batch metadata persistence, and SQS queuing."""
    settings = get_settings()
    doc_store = S3DocumentStore(settings=settings)
    batch_repo = DynamoDBBatchRepository(settings=settings)
    job_queue = SQSJobQueue(settings=settings)

    batch_id = f"LG-TEST-BATCH-{uuid.uuid4().hex[:6].upper()}"
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    content = b"%PDF-1.4 Live AWS Phase 7 Integration Test Content"

    # 1. S3 Upload
    s3_key = doc_store.upload_batch_document(
        batch_id=batch_id,
        document_id=doc_id,
        filename="live_test.pdf",
        data=content,
    )
    assert doc_store.document_exists(s3_key)

    # 2. DynamoDB Batch & Document Persistence
    batch = BatchRecord(batch_id=batch_id, document_count=1, accepted_count=1, status=BatchStatus.COMPLETED)
    batch_repo.save_batch(batch)

    retrieved_batch = batch_repo.get_batch(batch_id)
    assert retrieved_batch is not None
    assert retrieved_batch.batch_id == batch_id

    doc_record = DocumentIngestionRecord(
        document_id=doc_id,
        batch_id=batch_id,
        original_filename="live_test.pdf",
        safe_filename="live_test.pdf",
        document_hash="dummyhash123",
        s3_key=s3_key,
        status=DocumentStatus.QUEUED,
    )
    batch_repo.save_document_record(doc_record)
    retrieved_doc = batch_repo.get_document_record(batch_id, doc_id)
    assert retrieved_doc is not None
    assert retrieved_doc.document_id == doc_id

    # 3. SQS Job Dispatch
    job = ProcessingJob(
        invoice_id=doc_id,
        batch_id=batch_id,
        document_id=doc_id,
        s3_key=s3_key,
        idempotency_key=f"live_test_{batch_id}_{doc_id}",
    )
    msg_id = job_queue.send_job(job)
    assert msg_id is not None

    # Cleanup live S3 test object
    doc_store.delete_document(s3_key)
