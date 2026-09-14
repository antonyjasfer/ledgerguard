"""Unit tests for LedgerGuard Phase 7: Bulk Invoice Ingestion.

Covers:
- File validation (sizes, extensions, MIME)
- Filename sanitization & traversal prevention
- SHA-256 content hashing & duplicate detection
- S3 key generation
- BatchRecord & DocumentIngestionRecord lifecycle & DynamoDB serialization
- SQS ProcessingJob Phase 7 fields
- Worker Phase 7 raw document handling (AWAITING_EXTRACTION)
- Batch REST API endpoints (create, upload, list, get, duplicates, exceptions)
"""

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_batch_repository,
    get_document_store,
    get_invoice_repository,
    get_job_queue,
)
from app.api.main import create_app
from app.models.audit import AuditEvent, AuditEventType
from app.models.batch import (
    BatchRecord,
    BatchStatus,
    DocumentIngestionRecord,
    DocumentStatus,
)
from app.models.job import ProcessingJob
from app.services.batch_validator import (
    MAX_BATCH_FILES,
    MAX_BATCH_SIZE_BYTES,
    MAX_FILE_SIZE_BYTES,
    compute_sha256,
    generate_batch_key,
    sanitize_document_filename,
    validate_batch_files,
    validate_single_file,
)
from app.services.interfaces import BatchRepository, DocumentStore, InvoiceRepository, JobQueue
from app.services.state import ProcessingState
from app.worker.processor import InvoiceProcessor


# =============================================================================
# In-Memory Test Repositories
# =============================================================================

class InMemoryBatchRepository(BatchRepository):
    """In-memory implementation for isolated unit testing."""

    def __init__(self):
        self.batches: dict[str, BatchRecord] = {}
        self.documents: dict[tuple[str, str], DocumentIngestionRecord] = {}
        self.hash_index: dict[str, tuple[str, str, str]] = {}

    def save_batch(self, batch: BatchRecord) -> None:
        self.batches[batch.batch_id] = batch

    def get_batch(self, batch_id: str) -> BatchRecord | None:
        return self.batches.get(batch_id)

    def list_batches(self, limit: int = 50, offset: int = 0) -> list[BatchRecord]:
        sorted_batches = sorted(self.batches.values(), key=lambda b: b.created_at, reverse=True)
        return sorted_batches[offset : offset + limit]

    def save_document_record(self, doc: DocumentIngestionRecord) -> None:
        self.documents[(doc.batch_id, doc.document_id)] = doc

    def get_document_record(self, batch_id: str, document_id: str) -> DocumentIngestionRecord | None:
        return self.documents.get((batch_id, document_id))

    def list_batch_documents(self, batch_id: str) -> list[DocumentIngestionRecord]:
        return [doc for (b_id, _), doc in self.documents.items() if b_id == batch_id]

    def find_document_by_hash(self, document_hash: str) -> DocumentIngestionRecord | None:
        if document_hash in self.hash_index:
            doc_id, batch_id, _ = self.hash_index[document_hash]
            return self.get_document_record(batch_id, doc_id)
        for doc in self.documents.values():
            if doc.document_hash == document_hash:
                return doc
        return None

    def save_document_hash_index(
        self,
        document_hash: str,
        document_id: str,
        batch_id: str,
        s3_key: str | None = None,
    ) -> None:
        self.hash_index[document_hash] = (document_id, batch_id, s3_key or "")


class InMemoryDocumentStore(DocumentStore):
    """In-memory document store."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.bucket_name = "test-ledgerguard-bucket"

    def upload_document(self, invoice_id: str, filename: str, data: bytes, content_type: str = "application/pdf") -> str:
        key = f"invoices/{invoice_id}/{filename}"
        self.files[key] = data
        return key

    def upload_batch_document(self, batch_id: str, document_id: str, filename: str, data: bytes, content_type: str = "application/pdf") -> str:
        key = f"batches/{batch_id}/documents/{document_id}/{filename}"
        self.files[key] = data
        return key

    def download_document(self, key: str) -> bytes:
        if key not in self.files:
            raise FileNotFoundError(f"Key {key} not found")
        return self.files[key]

    def document_exists(self, key: str) -> bool:
        return key in self.files

    def delete_document(self, key: str) -> bool:
        if key in self.files:
            del self.files[key]
            return True
        return False

    def generate_key(self, invoice_id: str, filename: str) -> str:
        return f"invoices/{invoice_id}/{filename}"


class InMemoryJobQueue(JobQueue):
    """In-memory job queue."""

    def __init__(self):
        self.jobs: list[ProcessingJob] = []
        self.acked_jobs: list[str] = []

    def send_job(self, job: ProcessingJob) -> str:
        self.jobs.append(job)
        return job.job_id

    def receive_jobs(self, max_messages: int = 1, wait_time_seconds: int = 10, visibility_timeout: int | None = None):
        return []

    def ack_job(self, receipt_handle: str) -> None:
        self.acked_jobs.append(receipt_handle)

    def nack_job(self, receipt_handle: str, visibility_timeout: int = 0) -> None:
        pass


# =============================================================================
# 1. File Validation & Sanitization Tests
# =============================================================================

def test_file_validation_allowed_extensions():
    """Valid PDF, PNG, JPG, and JPEG extensions must be accepted."""
    assert validate_single_file("invoice.pdf", 1024, "application/pdf")[0] is True
    assert validate_single_file("receipt.png", 2048, "image/png")[0] is True
    assert validate_single_file("photo.jpg", 4096, "image/jpeg")[0] is True
    assert validate_single_file("scan.jpeg", 8192, "image/jpeg")[0] is True


def test_file_validation_disallowed_extensions():
    """Disallowed executable or script extensions must be rejected."""
    is_valid, code, msg = validate_single_file("malware.exe", 1024)
    assert is_valid is False
    assert code == "UNSUPPORTED_EXTENSION"

    is_valid, code, _ = validate_single_file("script.sh", 100)
    assert is_valid is False
    assert code == "UNSUPPORTED_EXTENSION"


def test_file_validation_size_limits():
    """Files exceeding 10MB or having 0 bytes must be rejected."""
    is_valid, code, msg = validate_single_file("empty.pdf", 0)
    assert is_valid is False
    assert code == "EMPTY_FILE"

    is_valid, code, msg = validate_single_file("giant.pdf", MAX_FILE_SIZE_BYTES + 1)
    assert is_valid is False
    assert code == "FILE_TOO_LARGE"


def test_filename_sanitization_traversal():
    """Directory traversal sequences and unsafe characters must be scrubbed."""
    assert sanitize_document_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_document_filename("..\\..\\secret.pdf") == "secret.pdf"
    assert sanitize_document_filename("inv<oice>#1?.pdf") == "inv_oice__1_.pdf"
    assert sanitize_document_filename("___") == "document.pdf"


def test_sha256_computation():
    """SHA-256 hash must be deterministic and hex-encoded."""
    data1 = b"Invoice content 123"
    data2 = b"Invoice content 123"
    data3 = b"Different invoice content"

    hash1 = compute_sha256(data1)
    hash2 = compute_sha256(data2)
    hash3 = compute_sha256(data3)

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64


def test_canonical_s3_key_generation():
    """S3 key must follow canonical hierarchy: batches/{batch_id}/documents/{document_id}/{safe_filename}."""
    key = generate_batch_key("LG-BATCH-001", "doc_abc123", "../../invoice#1.pdf")
    assert key == "batches/LG-BATCH-001/documents/doc_abc123/invoice_1.pdf"


# =============================================================================
# 2. Batch Domain Model & State Transitions
# =============================================================================

def test_batch_record_finalize_status_completed():
    """When all documents are accepted, status becomes COMPLETED."""
    batch = BatchRecord(batch_id="BATCH-001", document_count=3, accepted_count=3)
    batch.finalize_status()
    assert batch.status == BatchStatus.COMPLETED


def test_batch_record_finalize_status_exceptions():
    """When some documents fail/duplicate/reject, status becomes COMPLETED_WITH_EXCEPTIONS."""
    batch = BatchRecord(batch_id="BATCH-002", document_count=3, accepted_count=2, duplicate_count=1)
    batch.finalize_status()
    assert batch.status == BatchStatus.COMPLETED_WITH_EXCEPTIONS

    batch2 = BatchRecord(batch_id="BATCH-003", document_count=3, accepted_count=2, rejected_count=1)
    batch2.finalize_status()
    assert batch2.status == BatchStatus.COMPLETED_WITH_EXCEPTIONS


def test_batch_record_finalize_status_failed():
    """When all documents fail or are rejected, status becomes FAILED."""
    batch = BatchRecord(batch_id="BATCH-004", document_count=2, failed_count=2)
    batch.finalize_status()
    assert batch.status == BatchStatus.FAILED


def test_dynamodb_roundtrip_batch_record():
    """BatchRecord converts to and from DynamoDB single-table item without loss."""
    batch = BatchRecord(
        batch_id="LG-BATCH-TEST1",
        source="CLI_FOLDER",
        document_count=5,
        accepted_count=4,
        duplicate_count=1,
    )
    item = batch.to_dynamodb_item()
    assert item["PK"] == "BATCH#LG-BATCH-TEST1"
    assert item["SK"] == "METADATA"
    assert item["entity_type"] == "BATCH_METADATA"

    reconstructed = BatchRecord.from_dynamodb_item(item)
    assert reconstructed.batch_id == batch.batch_id
    assert reconstructed.accepted_count == 4
    assert reconstructed.duplicate_count == 1
    assert reconstructed.source == "CLI_FOLDER"


def test_dynamodb_roundtrip_document_record():
    """DocumentIngestionRecord converts to and from DynamoDB item without loss."""
    doc = DocumentIngestionRecord(
        document_id="doc_test123",
        batch_id="LG-BATCH-TEST1",
        original_filename="sample.pdf",
        safe_filename="sample.pdf",
        content_type="application/pdf",
        file_size=12345,
        document_hash="a" * 64,
        s3_key="batches/LG-BATCH-TEST1/documents/doc_test123/sample.pdf",
        status=DocumentStatus.QUEUED,
        idempotency_key="idemp_999",
    )
    item = doc.to_dynamodb_item()
    assert item["PK"] == "BATCH#LG-BATCH-TEST1"
    assert item["SK"] == "DOCUMENT#doc_test123"
    assert item["entity_type"] == "BATCH_DOCUMENT"

    reconstructed = DocumentIngestionRecord.from_dynamodb_item(item)
    assert reconstructed.document_id == doc.document_id
    assert reconstructed.document_hash == doc.document_hash
    assert reconstructed.status == DocumentStatus.QUEUED
    assert reconstructed.idempotency_key == "idemp_999"


# =============================================================================
# 3. SQS ProcessingJob Phase 7 Fields
# =============================================================================

def test_processing_job_phase7_fields():
    """ProcessingJob must support batch_id, document_id, idempotency_key, and roundtrip via SQS JSON."""
    job = ProcessingJob(
        invoice_id="doc_batch_123",
        batch_id="LG-BATCH-888",
        document_id="doc_batch_123",
        s3_bucket="ledgerguard-invoices",
        s3_key="batches/LG-BATCH-888/documents/doc_batch_123/inv.pdf",
        idempotency_key="batch_LG-BATCH-888_doc_batch_123",
    )
    sqs_body = job.to_sqs_message()
    parsed = ProcessingJob.from_sqs_message(sqs_body)

    assert parsed.batch_id == "LG-BATCH-888"
    assert parsed.document_id == "doc_batch_123"
    assert parsed.idempotency_key == "batch_LG-BATCH-888_doc_batch_123"
    assert parsed.s3_key == "batches/LG-BATCH-888/documents/doc_batch_123/inv.pdf"


# =============================================================================
# 4. Worker Raw Document Handling (AWAITING_EXTRACTION)
# =============================================================================

def test_worker_handles_raw_document_job_awaiting_extraction():
    """Worker processing a Phase 7 raw document job verifies S3 presence, emits DOCUMENT_INGESTED,

    retains document in AWAITING_EXTRACTION, and acknowledges SQS message without LLM reasoning.
    """
    doc_store = InMemoryDocumentStore()
    repo = MagicMock(spec=InvoiceRepository)
    repo.get_record.return_value = None
    queue = InMemoryJobQueue()

    # Place mock file in S3
    s3_key = "batches/LG-BATCH-001/documents/doc_1/inv.pdf"
    doc_store.files[s3_key] = b"%PDF-1.4 dummy"

    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=queue,
    )

    job = ProcessingJob(
        invoice_id="doc_1",
        batch_id="LG-BATCH-001",
        document_id="doc_1",
        s3_key=s3_key,
    )

    success = processor.process_job(job, receipt_handle="handle-1234")
    assert success is True
    assert "handle-1234" in queue.acked_jobs
    repo.save_audit_event.assert_called()
    called_event: AuditEvent = repo.save_audit_event.call_args[0][0]
    assert called_event.event_type == AuditEventType.DOCUMENT_INGESTED
    assert called_event.details["status"] == ProcessingState.AWAITING_EXTRACTION.value


# =============================================================================
# 5. REST API Batch Ingestion Endpoints Tests
# =============================================================================

@pytest.fixture
def api_test_client():
    batch_repo = InMemoryBatchRepository()
    doc_store = InMemoryDocumentStore()
    job_queue = InMemoryJobQueue()

    app = create_app()
    app.dependency_overrides[get_batch_repository] = lambda: batch_repo
    app.dependency_overrides[get_document_store] = lambda: doc_store
    app.dependency_overrides[get_job_queue] = lambda: job_queue

    client = TestClient(app)
    return client, batch_repo, doc_store, job_queue


def test_api_create_batch(api_test_client):
    """POST /batches creates a batch record in RECEIVED state."""
    client, batch_repo, _, _ = api_test_client
    resp = client.post("/batches", json={"source": "API", "document_count": 5})
    assert resp.status_code == 201
    data = resp.json()
    assert data["batch_id"].startswith("LG-BATCH-")
    assert data["status"] == "RECEIVED"
    assert data["document_count"] == 5


def test_api_upload_batch_documents_success(api_test_client):
    """POST /batches/upload ingests multiple files, stores in S3, records DynamoDB, and queues in SQS."""
    client, batch_repo, doc_store, job_queue = api_test_client

    files = [
        ("files", ("inv1.pdf", b"%PDF-1.4 Content 1", "application/pdf")),
        ("files", ("inv2.pdf", b"%PDF-1.4 Content 2", "application/pdf")),
        ("files", ("inv3.pdf", b"%PDF-1.4 Content 3", "application/pdf")),
    ]

    resp = client.post("/batches/upload", files=files, data={"source": "UI_UPLOAD"})
    assert resp.status_code == 201
    data = resp.json()

    assert data["document_count"] == 3
    assert data["accepted_count"] == 3
    assert data["rejected_count"] == 0
    assert data["duplicate_count"] == 0
    assert data["queued_count"] == 3
    assert data["status"] == "COMPLETED"

    # Verify S3 storage
    assert len(doc_store.files) == 3

    # Verify SQS jobs
    assert len(job_queue.jobs) == 3
    for job in job_queue.jobs:
        assert job.batch_id == data["batch_id"]
        assert job.document_id is not None
        assert job.s3_key is not None
        assert job.idempotency_key is not None


def test_api_upload_duplicate_detection(api_test_client):
    """Submitting the exact same file twice flags it as DUPLICATE and does not re-upload or re-queue."""
    client, batch_repo, doc_store, job_queue = api_test_client

    file_bytes = b"%PDF-1.4 Unique Invoice Content 999"
    files = [("files", ("first.pdf", file_bytes, "application/pdf"))]

    # First ingestion
    resp1 = client.post("/batches/upload", files=files)
    assert resp1.status_code == 201
    d1 = resp1.json()
    assert d1["accepted_count"] == 1
    assert d1["duplicate_count"] == 0
    assert len(job_queue.jobs) == 1

    # Second ingestion of the exact same content
    files2 = [("files", ("second.pdf", file_bytes, "application/pdf"))]
    resp2 = client.post("/batches/upload", files=files2)
    assert resp2.status_code == 201
    d2 = resp2.json()

    assert d2["duplicate_count"] == 1
    assert d2["accepted_count"] == 0
    assert d2["status"] == "COMPLETED_WITH_EXCEPTIONS"

    # Queue should still only have the 1 original job
    assert len(job_queue.jobs) == 1

    # Check duplicate document details
    dup_doc = d2["documents"][0]
    assert dup_doc["status"] == "DUPLICATE"
    assert dup_doc["matched_document_id"] == d1["documents"][0]["document_id"]


def test_api_upload_partial_failure_exceptions(api_test_client):
    """When a batch has 1 valid and 1 rejected file, it finalizes as COMPLETED_WITH_EXCEPTIONS."""
    client, batch_repo, doc_store, job_queue = api_test_client

    files = [
        ("files", ("valid.pdf", b"%PDF-1.4 Valid", "application/pdf")),
        ("files", ("malicious.exe", b"MZ...", "application/octet-stream")),
    ]

    resp = client.post("/batches/upload", files=files)
    assert resp.status_code == 201
    data = resp.json()

    assert data["accepted_count"] == 1
    assert data["rejected_count"] == 1
    assert data["status"] == "COMPLETED_WITH_EXCEPTIONS"
    assert len(job_queue.jobs) == 1


def test_api_list_and_get_batches(api_test_client):
    """GET /batches and GET /batches/{batch_id} retrieve batch records and documents."""
    client, batch_repo, _, _ = api_test_client

    files = [("files", ("inv.pdf", b"%PDF-1.4 Demo", "application/pdf"))]
    upload_resp = client.post("/batches/upload", files=files)
    batch_id = upload_resp.json()["batch_id"]

    # List batches
    list_resp = client.get("/batches")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # Get single batch
    get_resp = client.get(f"/batches/{batch_id}")
    assert get_resp.status_code == 200
    b_data = get_resp.json()
    assert b_data["batch_id"] == batch_id
    assert len(b_data["documents"]) == 1

    # Get batch documents
    docs_resp = client.get(f"/batches/{batch_id}/documents")
    assert docs_resp.status_code == 200
    assert docs_resp.json()["total"] == 1
