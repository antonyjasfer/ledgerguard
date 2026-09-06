"""Unit tests for LedgerGuard background worker and processor.

Validates end-to-end asynchronous verification orchestration, idempotency,
state transitions, safe failure handling, and logging hygiene.
"""

import logging
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.audit import AuditEventType
from app.models.decision import AgentDecision, VerificationDecision
from app.models.invoice import Invoice, LineItem
from app.models.job import JobStatus, ProcessingJob
from app.models.persistence import InvoiceRecord
from app.models.verification import RiskLevel
from app.services.interfaces import DocumentStore, InvoiceRepository, JobQueue
from app.services.state import ProcessingState
from app.worker.processor import InvoiceProcessor, decision_to_state


@pytest.fixture
def sample_invoice():
    return Invoice(
        invoice_id="inv_worker_01",
        invoice_number="INV-2026-001",
        vendor_id="vend_verified_01",
        vendor_name="Reliable Logistics LLC",
        customer_name="LedgerGuard Corp",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        discount=Decimal("0.00"),
        total=Decimal("110.00"),
        line_items=[
            LineItem(
                description="Freight delivery",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                tax_rate=Decimal("0.10"),
                discount=Decimal("0.00"),
            )
        ],
    )


@pytest.fixture
def mock_services():
    doc_store = MagicMock(spec=DocumentStore)
    repo = MagicMock(spec=InvoiceRepository)
    job_queue = MagicMock(spec=JobQueue)

    # Defaults
    repo.is_already_processed.return_value = False
    repo.get_record.return_value = None
    doc_store.document_exists.return_value = True

    return doc_store, repo, job_queue


def test_decision_to_state_mapping():
    """Verify AgentDecision to ProcessingState mappings."""
    assert decision_to_state(AgentDecision.AUTO_APPROVE) == ProcessingState.AUTO_APPROVED
    assert decision_to_state(AgentDecision.MANUAL_REVIEW) == ProcessingState.MANUAL_REVIEW
    assert decision_to_state(AgentDecision.BLOCK) == ProcessingState.BLOCKED
    assert decision_to_state(AgentDecision.ESCALATE) == ProcessingState.MANUAL_REVIEW


def test_worker_happy_path(sample_invoice, mock_services):
    """Clean invoice with established vendor is verified, state persisted to AUTO_APPROVED, and message acknowledged."""
    doc_store, repo, job_queue = mock_services
    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
    )

    job = ProcessingJob(
        job_id="job_001",
        invoice_id=sample_invoice.invoice_id,
        s3_key="invoices/inv_worker_01/doc.pdf",
    )

    # Establish known vendor history so invoice qualifies for AUTO_APPROVE
    prior_invoice = Invoice(
        invoice_id="inv_prior_00",
        invoice_number="INV-2026-000",
        vendor_id=sample_invoice.vendor_id,
        vendor_name=sample_invoice.vendor_name,
        customer_name=sample_invoice.customer_name,
        invoice_date=date(2026, 8, 1),
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        discount=Decimal("0.00"),
        total=Decimal("110.00"),
    )

    success = processor.process_job(
        job=job,
        receipt_handle="receipt_handle_123",
        invoice_data=sample_invoice,
        history=[prior_invoice],
    )

    assert success is True
    # Document presence was checked
    doc_store.document_exists.assert_called_once_with("invoices/inv_worker_01/doc.pdf")

    # Record was persisted with AUTO_APPROVED state
    repo.save_record.assert_called()
    last_saved_record = repo.save_record.call_args[0][0]
    assert isinstance(last_saved_record, InvoiceRecord)
    assert last_saved_record.processing_status == ProcessingState.AUTO_APPROVED
    assert last_saved_record.decision == AgentDecision.AUTO_APPROVE

    # SQS message was acknowledged ONLY after persistence
    job_queue.ack_job.assert_called_once_with("receipt_handle_123")


def test_worker_idempotency_duplicate_job(sample_invoice, mock_services):
    """Processing an already completed invoice skips execution and acks message safely."""
    doc_store, repo, job_queue = mock_services
    repo.is_already_processed.return_value = True  # Already completed in terminal state

    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
    )

    job = ProcessingJob(
        job_id="job_duplicate_002",
        invoice_id=sample_invoice.invoice_id,
    )

    success = processor.process_job(
        job=job,
        receipt_handle="receipt_dup_456",
        invoice_data=sample_invoice,
    )

    assert success is True
    # Should NOT have re-saved record or called verification
    repo.save_record.assert_not_called()
    doc_store.document_exists.assert_not_called()

    # Should have acknowledged SQS message so it doesn't spin in queue
    job_queue.ack_job.assert_called_once_with("receipt_dup_456")

    # Should have saved an audit event recording duplicate skip
    repo.save_audit_event.assert_called_once()
    event = repo.save_audit_event.call_args[0][0]
    assert event.event_type == AuditEventType.PROCESSING_COMPLETED
    assert event.details.get("status") == "already_processed"


def test_worker_missing_s3_document(sample_invoice, mock_services):
    """Missing S3 document marks state FAILED and DOES NOT acknowledge message."""
    doc_store, repo, job_queue = mock_services
    doc_store.document_exists.return_value = False  # Missing document

    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
    )

    job = ProcessingJob(
        job_id="job_missing_s3",
        invoice_id=sample_invoice.invoice_id,
        s3_key="invoices/missing/file.pdf",
    )

    success = processor.process_job(
        job=job,
        receipt_handle="receipt_handle_fail",
        invoice_data=sample_invoice,
    )

    assert success is False
    # Marked FAILED
    repo.update_status.assert_called()
    failed_status = [c for c in repo.update_status.call_args_list if c[1].get("status") == ProcessingState.FAILED]
    assert len(failed_status) > 0

    # Message was NOT acknowledged
    job_queue.ack_job.assert_not_called()


def test_worker_missing_invoice_data(mock_services):
    """Absence of invoice payload fails gracefully without crash."""
    doc_store, repo, job_queue = mock_services
    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
    )

    job = ProcessingJob(
        job_id="job_no_data",
        invoice_id="inv_ghost",
    )

    success = processor.process_job(
        job=job,
        receipt_handle="receipt_ghost",
        invoice_data=None,
    )

    assert success is False
    job_queue.ack_job.assert_not_called()


def test_worker_agent_failure(sample_invoice, mock_services):
    """Unhandled agent failure marks job FAILED and leaves message in queue for retry."""
    doc_store, repo, job_queue = mock_services
    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
    )

    job = ProcessingJob(
        job_id="job_agent_crash",
        invoice_id=sample_invoice.invoice_id,
    )

    with patch("app.worker.processor.run_verification_workflow", side_effect=RuntimeError("LLM timed out")):
        success = processor.process_job(
            job=job,
            receipt_handle="receipt_crash",
            invoice_data=sample_invoice,
        )

    assert success is False
    job_queue.ack_job.assert_not_called()
    # Audit event emitted for failure
    audit_calls = [c[0][0] for c in repo.save_audit_event.call_args_list]
    failed_events = [e for e in audit_calls if e.event_type == AuditEventType.PROCESSING_FAILED]
    assert len(failed_events) > 0
    assert failed_events[0].details.get("error_category") == "AGENT_EXECUTION_FAILURE"


def test_worker_persistence_failure_prevents_sqs_ack(sample_invoice, mock_services):
    """If DynamoDB persistence fails, message MUST NOT be acknowledged from SQS."""
    doc_store, repo, job_queue = mock_services
    repo.save_record.side_effect = RuntimeError("DynamoDB ProvisionedThroughputExceededException")

    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
    )

    job = ProcessingJob(
        job_id="job_persist_fail",
        invoice_id=sample_invoice.invoice_id,
    )

    success = processor.process_job(
        job=job,
        receipt_handle="receipt_do_not_ack",
        invoice_data=sample_invoice,
    )

    assert success is False
    # CRITICAL: Message was NOT acknowledged
    job_queue.ack_job.assert_not_called()


def test_worker_safe_logging(sample_invoice, mock_services, caplog):
    """Worker logs must not contain raw document data or sensitive credentials."""
    doc_store, repo, job_queue = mock_services
    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=job_queue,
    )

    job = ProcessingJob(
        job_id="job_safe_log",
        invoice_id=sample_invoice.invoice_id,
    )

    with caplog.at_level(logging.INFO):
        processor.process_job(
            job=job,
            receipt_handle="handle_safe",
            invoice_data=sample_invoice,
        )

    for record in caplog.records:
        msg = record.getMessage()
        # Must not log secret strings or raw dumps
        assert "sk-or-v1" not in msg
        assert "password" not in msg.lower()
        assert "Authorization" not in msg
        assert "%PDF" not in msg
