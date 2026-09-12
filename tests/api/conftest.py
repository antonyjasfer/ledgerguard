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

    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        status=None,
        vendor_id=None,
        search=None,
    ):
        records = list(self.records.values())
        if status is not None:
            records = [r for r in records if r.processing_status == status]
        if vendor_id is not None:
            records = [r for r in records if r.vendor_id == vendor_id]
        if search:
            s = search.lower()
            records = [
                r for r in records
                if s in r.invoice_id.lower() or s in r.invoice_number.lower() or s in r.vendor_name.lower()
            ]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[offset : offset + limit]

    def count_records(
        self,
        status=None,
        vendor_id=None,
        search=None,
    ) -> int:
        records = self.list_records(limit=10000, offset=0, status=status, vendor_id=vendor_id, search=search)
        return len(records)

    def get_dashboard_stats(self):
        from decimal import Decimal
        all_records = list(self.records.values())
        total = len(all_records)
        by_status = {}
        by_decision = {}
        by_risk_level = {}
        total_amount = Decimal("0.00")
        risk_scores = []

        auto_approved = 0
        manual_review = 0
        blocked = 0
        pending = 0
        processed = 0

        for r in all_records:
            st = r.processing_status.value
            by_status[st] = by_status.get(st, 0) + 1

            if r.processing_status in TERMINAL_STATES:
                processed += 1
            else:
                pending += 1

            if r.decision is not None:
                dec = r.decision.value
                by_decision[dec] = by_decision.get(dec, 0) + 1
                if dec == "AUTO_APPROVE":
                    auto_approved += 1
                elif dec in ("MANUAL_REVIEW", "ESCALATE"):
                    manual_review += 1
                elif dec == "BLOCK":
                    blocked += 1

            if r.risk_level is not None:
                rl = r.risk_level.value
                by_risk_level[rl] = by_risk_level.get(rl, 0) + 1

            if r.risk_score is not None:
                risk_scores.append(r.risk_score)

            if r.total is not None:
                try:
                    total_amount += Decimal(str(r.total))
                except Exception:
                    pass

        avg_risk = float(sum(risk_scores) / len(risk_scores)) if risk_scores else 0.0
        approval_rate = float((auto_approved / processed) * 100) if processed > 0 else 0.0

        return {
            "total_invoices": total,
            "pending_invoices": pending,
            "processed_invoices": processed,
            "auto_approved_count": auto_approved,
            "manual_review_count": manual_review,
            "blocked_count": blocked,
            "total_amount_usd": float(total_amount),
            "average_risk_score": round(avg_risk, 1),
            "auto_approval_rate_pct": round(approval_rate, 1),
            "by_status": by_status,
            "by_decision": by_decision,
            "by_risk_level": by_risk_level,
        }


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
