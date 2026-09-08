"""Pytest fixtures and test doubles for LedgerGuard offline API testing."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import (
    get_current_settings,
    get_document_store,
    get_invoice_repository,
    get_job_queue,
)
from app.api.main import create_app
from app.config import Settings
from app.models.audit import AuditEvent
from app.models.decision import AgentDecision
from app.models.job import ProcessingJob
from app.models.persistence import InvoiceRecord
from app.services.interfaces import DocumentStore, InvoiceRepository, JobQueue
from app.services.s3 import sanitize_filename, sanitize_id
from app.services.state import TERMINAL_STATES, ProcessingState


class InMemoryDocumentStore(DocumentStore):
    """In-memory document store for offline testing."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def generate_key(self, invoice_id: str, filename: str) -> str:
        safe_inv_id = sanitize_id(invoice_id)
        safe_fname = sanitize_filename(filename)
        return f"invoices/{safe_inv_id}/{safe_fname}"

    def upload_document(
        self,
        invoice_id: str,
        filename: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        key = self.generate_key(invoice_id, filename)
        self.files[key] = data
        return key

    def download_document(self, key: str) -> bytes:
        if key not in self.files:
            raise FileNotFoundError(f"Key '{key}' not found")
        return self.files[key]

    def document_exists(self, key: str) -> bool:
        return key in self.files

    def delete_document(self, key: str) -> bool:
        if key in self.files:
            del self.files[key]
            return True
        return False


class InMemoryInvoiceRepository(InvoiceRepository):
    """In-memory invoice repository and audit event store for offline testing."""

    def __init__(self):
        self.records: dict[str, InvoiceRecord] = {}
        self.audit_events: dict[str, list[AuditEvent]] = {}

    def save_record(self, record: InvoiceRecord) -> None:
        self.records[record.invoice_id] = record

    def get_record(self, invoice_id: str) -> InvoiceRecord | None:
        return self.records.get(invoice_id)

    def update_status(
        self,
        invoice_id: str,
        status: ProcessingState,
        decision: AgentDecision | None = None,
        updated_at: str | None = None,
    ) -> None:
        if invoice_id in self.records:
            rec = self.records[invoice_id]
            rec.processing_status = status
            if decision is not None:
                rec.decision = decision
            rec.updated_at = updated_at or datetime.now(timezone.utc).isoformat()

    def save_audit_event(self, event: AuditEvent) -> None:
        if event.invoice_id not in self.audit_events:
            self.audit_events[event.invoice_id] = []
        self.audit_events[event.invoice_id].append(event)

    def get_audit_events(self, invoice_id: str) -> list[AuditEvent]:
        return self.audit_events.get(invoice_id, [])

    def is_already_processed(self, invoice_id: str) -> bool:
        rec = self.get_record(invoice_id)
        if rec is None:
            return False
        return rec.processing_status in TERMINAL_STATES


class InMemoryJobQueue(JobQueue):
    """In-memory SQS job queue double for offline testing."""

    def __init__(self):
        self.jobs: list[ProcessingJob] = []

    def send_job(self, job: ProcessingJob) -> str:
        self.jobs.append(job)
        return f"msg_{len(self.jobs)}"

    def receive_jobs(
        self,
        max_messages: int = 1,
        wait_time_seconds: int = 10,
        visibility_timeout: int | None = None,
    ) -> list[tuple[ProcessingJob, str]]:
        if not self.jobs:
            return []
        job = self.jobs.pop(0)
        return [(job, f"receipt_{job.job_id}")]

    def ack_job(self, receipt_handle: str) -> None:
        pass

    def nack_job(self, receipt_handle: str, visibility_timeout: int = 0) -> None:
        pass


@pytest.fixture
def mock_doc_store():
    return InMemoryDocumentStore()


@pytest.fixture
def mock_repo():
    return InMemoryInvoiceRepository()


@pytest.fixture
def mock_queue():
    return InMemoryJobQueue()


@pytest.fixture
def test_settings():
    return Settings(
        LEDGERGUARD_API_KEY=SecretStr("test-secret-key"),
        LEDGERGUARD_S3_BUCKET="test-bucket",
        LEDGERGUARD_DYNAMODB_TABLE="test-table",
        LEDGERGUARD_SQS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        MAX_DOCUMENT_SIZE_BYTES=1024 * 1024,  # 1MB for tests
    )


@pytest.fixture
def app(mock_doc_store, mock_repo, mock_queue, test_settings):
    application = create_app()
    application.dependency_overrides[get_current_settings] = lambda: test_settings
    application.dependency_overrides[get_document_store] = lambda: mock_doc_store
    application.dependency_overrides[get_invoice_repository] = lambda: mock_repo
    application.dependency_overrides[get_job_queue] = lambda: mock_queue
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-secret-key"}
