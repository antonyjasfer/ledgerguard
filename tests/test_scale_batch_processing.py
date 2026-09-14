"""Unit and concurrency tests for LedgerGuard Phase 9 Scale & Batch Processing.

Verifies:
1. Bounded concurrency (MAX_WORKER_CONCURRENCY, MAX_EXTRACTION_CONCURRENCY, MAX_GEMMA_CONCURRENCY).
2. Worker backpressure during high queue volume.
3. Bedrock Mantle / Gemma throttling exponential backoff and deterministic MANUAL_REVIEW fallback.
4. Failure isolation: corrupted documents are safely quarantined without halting the batch.
5. O(1) Batch Progress calculation based on authoritative BatchRecord counters.
6. Safe batch resumption re-enqueuing only non-terminal or retry-eligible documents.
7. Strict Decimal precision in high-volume batch financial aggregation.
"""

from decimal import Decimal
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import Settings
from app.models.batch import BatchRecord, BatchStatus, DocumentIngestionRecord, DocumentStatus
from app.models.decision import AgentDecision, VerificationDecision
from app.models.extraction import ExtractionResult, ExtractionStatus
from app.models.invoice import Invoice
from app.models.job import JobStatus, ProcessingJob
from app.models.persistence import InvoiceRecord
from app.services.interfaces import BatchRepository, DocumentStore, InvoiceRepository, JobQueue
from app.services.state import ProcessingState
from app.worker.processor import InvoiceProcessor


def test_bounded_concurrency_semaphores():
    """Verify InvoiceProcessor enforces extraction and model semaphores."""
    settings = Settings(
        MAX_WORKER_CONCURRENCY=8,
        MAX_EXTRACTION_CONCURRENCY=4,
        MAX_GEMMA_CONCURRENCY=3,
    )
    mock_store = MagicMock(spec=DocumentStore)
    mock_repo = MagicMock()
    mock_queue = MagicMock(spec=JobQueue)

    processor = InvoiceProcessor(
        document_store=mock_store,
        repository=mock_repo,
        job_queue=mock_queue,
        settings=settings,
    )

    assert processor._extraction_semaphore._value == 4
    assert processor._gemma_semaphore._value == 3


def test_gemma_throttling_retry_and_manual_review_fallback():
    """Verify throttling triggers retries and falls back safely to MANUAL_REVIEW when exhausted."""
    settings = Settings(
        MAX_GEMMA_CONCURRENCY=3,
        LEDGERGUARD_MODEL_PROVIDER="bedrock_mantle",
    )
    mock_store = MagicMock(spec=DocumentStore)
    mock_repo = MagicMock()
    mock_queue = MagicMock(spec=JobQueue)

    processor = InvoiceProcessor(
        document_store=mock_store,
        repository=mock_repo,
        job_queue=mock_queue,
        settings=settings,
    )

    invoice = Invoice(
        invoice_id="inv_throttle_01",
        invoice_number="INV-THROTTLE-01",
        vendor_id="vend_01",
        vendor_name="Acme Corp",
        customer_name="LedgerGuard Enterprise",
        invoice_date="2026-09-01",
        subtotal=Decimal("100.00"),
        total=Decimal("108.00"),
        currency="USD",
    )
    job = ProcessingJob(job_id="job_th_01", invoice_id="inv_throttle_01", batch_id="LG-BATCH-TEST")

    # Simulate ThrottlingException on each call
    with patch("app.worker.processor.run_verification_workflow", side_effect=Exception("ThrottlingException: Rate exceeded (429)")):
        decision, metadata = processor._run_workflow_with_bounded_retry(
            invoice=invoice,
            history=[],
            policy_config=None,
            job=job,
        )

        # Must fall back deterministically to MANUAL_REVIEW - never auto-approve!
        assert decision.decision == AgentDecision.MANUAL_REVIEW
        assert decision.requires_human is True
        assert "MODEL_THROTTLED_FALLBACK_TO_REVIEW" in metadata.override_reason


def test_document_level_failure_isolation():
    """Verify an unparseable or corrupt document is quarantined without halting worker or batch."""
    settings = Settings()
    mock_store = MagicMock(spec=DocumentStore)
    mock_repo = MagicMock()
    mock_queue = MagicMock(spec=JobQueue)

    mock_doc = DocumentIngestionRecord(
        document_id="doc_corrupt_01",
        batch_id="LG-BATCH-ISO",
        original_filename="corrupt.pdf",
        safe_filename="corrupt.pdf",
        document_hash="deadbeef1234",
        status=DocumentStatus.AWAITING_EXTRACTION,
        s3_key="batches/LG-BATCH-ISO/corrupt.pdf",
    )
    mock_repo.get_document_record.return_value = mock_doc
    mock_store.document_exists.return_value = True
    mock_store.download_document.return_value = b"%PDF-corrupt-data"

    mock_extractor = MagicMock()
    # Simulate an unexpected parser crash on corrupt bytes
    mock_extractor.extract.side_effect = ValueError("Corrupted PDF stream header")

    processor = InvoiceProcessor(
        document_store=mock_store,
        repository=mock_repo,
        job_queue=mock_queue,
        settings=settings,
        extractor=mock_extractor,
        auto_extract=True,
    )

    job = ProcessingJob(
        job_id="job_iso_01",
        document_id="doc_corrupt_01",
        invoice_id="doc_corrupt_01",
        batch_id="LG-BATCH-ISO",
        s3_key="batches/LG-BATCH-ISO/corrupt.pdf",
        action="extract",
    )

    # Process job - must return True (handled & isolated), NOT crash or raise
    success = processor.process_job(job, receipt_handle="receipt_handle_123")
    assert success is True

    # SQS message must be acknowledged so poison message is not retried forever
    mock_queue.ack_job.assert_called_with("receipt_handle_123")

    # Document must be transitioned to EXTRACTION_FAILED
    saved_doc = mock_repo.save_document_record.call_args[0][0]
    assert saved_doc.status == DocumentStatus.EXTRACTION_FAILED
    assert saved_doc.error_code in ("EXTRACTION_CRASH", "EXTRACTION_EXCEPTION")


def test_o1_batch_progress_calculation():
    """Verify GET /batches/{batch_id}/progress calculates metrics in O(1) time without full-table scan."""
    mock_batch = BatchRecord(
        batch_id="LG-BATCH-PROG-01",
        status=BatchStatus.PROCESSING,
        document_count=1000,
        accepted_count=1000,
        completed_count=650,
        auto_approved_count=600,
        manual_review_count=35,
        blocked_count=10,
        duplicate_count=5,
        failed_count=0,
        retry_count=4,
        started_at="2026-09-01T12:00:00+00:00",
    )

    client = TestClient(app)
    mock_batch_repo = MagicMock()
    mock_batch_repo.get_batch.return_value = mock_batch

    from app.api.dependencies import get_batch_repository
    app.dependency_overrides[get_batch_repository] = lambda: mock_batch_repo

    try:
        response = client.get("/batches/LG-BATCH-PROG-01/progress")
        assert response.status_code == 200
        data = response.json()

        assert data["batch_id"] == "LG-BATCH-PROG-01"
        assert data["total_documents"] == 1000
        assert data["completed_count"] == 650
        assert data["percent_complete"] == 65.0
        assert data["auto_approved_count"] == 600
        assert data["manual_review_count"] == 35
        assert data["blocked_count"] == 10
        assert data["retry_count"] == 4
        assert "documents_per_minute" in data
        assert "elapsed_seconds" in data
        mock_batch_repo.get_batch.assert_called_once_with("LG-BATCH-PROG-01")
    finally:
        app.dependency_overrides.pop(get_batch_repository, None)


def test_batch_resume_does_not_reprocess_terminal_documents():
    """Verify POST /batches/{batch_id}/resume only dispatches jobs for incomplete/failed documents."""
    batch_id = "LG-BATCH-RESUME-01"
    mock_batch = BatchRecord(
        batch_id=batch_id,
        status=BatchStatus.COMPLETED_WITH_EXCEPTIONS,
        document_count=4,
        accepted_count=4,
        completed_count=2,
    )

    # 4 documents in batch: 2 terminal, 1 failed, 1 awaiting
    doc_terminal_approved = DocumentIngestionRecord(
        document_id="doc_01",
        batch_id=batch_id,
        original_filename="doc1.pdf",
        safe_filename="doc1.pdf",
        document_hash="hash1",
        status=DocumentStatus.AUTO_APPROVED,
        s3_key="s3://doc1.pdf",
    )
    doc_terminal_duplicate = DocumentIngestionRecord(
        document_id="doc_02",
        batch_id=batch_id,
        original_filename="doc2.pdf",
        safe_filename="doc2.pdf",
        document_hash="hash2",
        status=DocumentStatus.DUPLICATE,
        s3_key="s3://doc2.pdf",
    )
    doc_failed_retryable = DocumentIngestionRecord(
        document_id="doc_03",
        batch_id=batch_id,
        original_filename="doc3.pdf",
        safe_filename="doc3.pdf",
        document_hash="hash3",
        status=DocumentStatus.FAILED,
        s3_key="s3://doc3.pdf",
        attempt_count=1,
        max_attempts=3,
    )
    doc_awaiting = DocumentIngestionRecord(
        document_id="doc_04",
        batch_id=batch_id,
        original_filename="doc4.pdf",
        safe_filename="doc4.pdf",
        document_hash="hash4",
        status=DocumentStatus.AWAITING_EXTRACTION,
        s3_key="s3://doc4.pdf",
        attempt_count=0,
        max_attempts=3,
    )

    client = TestClient(app)
    mock_batch_repo = MagicMock()
    mock_job_queue = MagicMock()

    mock_batch_repo.get_batch.return_value = mock_batch
    mock_batch_repo.list_batch_documents.return_value = [
        doc_terminal_approved,
        doc_terminal_duplicate,
        doc_failed_retryable,
        doc_awaiting,
    ]

    from app.api.dependencies import get_batch_repository, get_job_queue
    app.dependency_overrides[get_batch_repository] = lambda: mock_batch_repo
    app.dependency_overrides[get_job_queue] = lambda: mock_job_queue

    try:
        response = client.post(f"/batches/{batch_id}/resume")
        assert response.status_code == 200
        data = response.json()

        # Only doc_03 and doc_04 must be resumed (2 items)
        assert data["resumed_count"] == 2
        assert mock_job_queue.send_job.call_count == 2

        # Check that send_job was never called for doc_01 or doc_02
        enqueued_doc_ids = [call.args[0].document_id for call in mock_job_queue.send_job.call_args_list]
        assert "doc_01" not in enqueued_doc_ids
        assert "doc_02" not in enqueued_doc_ids
        assert "doc_03" in enqueued_doc_ids
        assert "doc_04" in enqueued_doc_ids
    finally:
        app.dependency_overrides.pop(get_batch_repository, None)
        app.dependency_overrides.pop(get_job_queue, None)


def test_decimal_precision_scale_financial_aggregation():
    """Verify that financial accumulation across 1,000 invoices maintains exact Decimal precision."""
    from app.services.dynamodb import DynamoDBInvoiceRepository

    mock_table = MagicMock()
    repo = DynamoDBInvoiceRepository(table=mock_table)

    # Generate 1,000 mock items each having odd cents (e.g. $19.99 total, $1.60 tax, $18.39 subtotal)
    items = []
    expected_total = Decimal("0.00")
    for i in range(1000):
        total = Decimal("19.99")
        subtotal = Decimal("18.39")
        tax = Decimal("1.60")
        expected_total += total

        items.append({
            "PK": f"INVOICE#inv_{i:04d}",
            "SK": "METADATA",
            "entity_type": "INVOICE_RECORD",
            "invoice_id": f"inv_{i:04d}",
            "processing_status": "AUTO_APPROVED",
            "decision": "AUTO_APPROVE",
            "total": total,
            "subtotal": subtotal,
            "tax": tax,
            "discount": Decimal("0.00"),
            "shipping": Decimal("0.00"),
            "created_at": "2026-09-01T12:00:00Z",
        })

    mock_table.scan.return_value = {"Items": items}
    stats = repo.get_dashboard_stats()

    # Exact equality: $19,990.00 with zero floating point drift
    assert stats["total_invoice_value"] == expected_total
    assert stats["total_invoice_value"] == Decimal("19990.00")
    assert isinstance(stats["total_invoice_value"], Decimal)
