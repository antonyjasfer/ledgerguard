"""Service interface abstractions for LedgerGuard data and execution layers.

Decouples business logic, agent orchestration, and worker loops from concrete
cloud providers (boto3) and enables offline deterministic testing.
"""

from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.models.audit import AuditEvent
from app.models.batch import BatchRecord, DocumentIngestionRecord
from app.models.decision import AgentDecision
from app.models.job import ProcessingJob
from app.models.persistence import InvoiceRecord
from app.services.state import ProcessingState


class DocumentStore(ABC):
    """Abstract contract for document artifact storage (e.g. S3)."""

    @abstractmethod
    def upload_document(
        self,
        invoice_id: str,
        filename: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload raw document bytes and return its unique storage key."""
        pass

    @abstractmethod
    def download_document(self, key: str) -> bytes:
        """Download and return raw document bytes for a given storage key."""
        pass

    @abstractmethod
    def document_exists(self, key: str) -> bool:
        """Check whether a document exists at the given key."""
        pass

    @abstractmethod
    def delete_document(self, key: str) -> bool:
        """Delete a document from storage if explicitly requested."""
        pass

    @abstractmethod
    def generate_key(self, invoice_id: str, filename: str) -> str:
        """Generate a sanitized, traversal-safe storage key for a document."""
        pass


class InvoiceRepository(ABC):
    """Abstract contract for invoice persistence, state tracking, and audit logging (e.g. DynamoDB)."""

    @abstractmethod
    def save_record(self, record: InvoiceRecord) -> None:
        """Save or overwrite an invoice record."""
        pass

    @abstractmethod
    def get_record(self, invoice_id: str) -> InvoiceRecord | None:
        """Retrieve an invoice record by unique invoice identifier."""
        pass

    @abstractmethod
    def update_status(
        self,
        invoice_id: str,
        status: ProcessingState,
        decision: AgentDecision | None = None,
        updated_at: str | None = None,
    ) -> None:
        """Update lifecycle status and optionally the decision of an invoice record."""
        pass

    @abstractmethod
    def save_audit_event(self, event: AuditEvent) -> None:
        """Append an immutable audit event to the audit trail."""
        pass

    @abstractmethod
    def get_audit_events(self, invoice_id: str) -> list[AuditEvent]:
        """Retrieve chronological audit trail events for an invoice."""
        pass

    @abstractmethod
    def is_already_processed(self, invoice_id: str) -> bool:
        """Check if an invoice has already reached a completed/terminal state."""
        pass

    @abstractmethod
    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        status: ProcessingState | None = None,
        vendor_id: str | None = None,
        search: str | None = None,
    ) -> list[InvoiceRecord]:
        """List persisted invoice records with optional filtering."""
        pass

    @abstractmethod
    def count_records(
        self,
        status: ProcessingState | None = None,
        vendor_id: str | None = None,
        search: str | None = None,
    ) -> int:
        """Count records matching criteria."""
        pass

    @abstractmethod
    def get_dashboard_stats(self, batch_id: str | None = None, date_range: str | None = None) -> dict[str, Any]:
        """Aggregate high-level invoice processing statistics and metrics."""
        pass


class BatchRepository(ABC):
    """Abstract contract for bulk invoice batch and document ingestion persistence."""

    @abstractmethod
    def save_batch(self, batch: BatchRecord) -> None:
        """Save or overwrite a batch metadata record."""
        pass

    @abstractmethod
    def get_batch(self, batch_id: str) -> BatchRecord | None:
        """Retrieve a batch record by unique batch identifier."""
        pass

    @abstractmethod
    def list_batches(self, limit: int = 50, offset: int = 0) -> list[BatchRecord]:
        """List batches ordered by creation timestamp."""
        pass

    @abstractmethod
    def save_document_record(self, doc: DocumentIngestionRecord) -> None:
        """Save or overwrite a document ingestion record."""
        pass

    @abstractmethod
    def get_document_record(self, batch_id: str, document_id: str) -> DocumentIngestionRecord | None:
        """Retrieve a document ingestion record by batch and document ID."""
        pass

    @abstractmethod
    def list_batch_documents(self, batch_id: str) -> list[DocumentIngestionRecord]:
        """List all document records belonging to a batch."""
        pass

    def list_batch_documents_paginated(
        self,
        batch_id: str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[DocumentIngestionRecord], int]:
        """List documents within a batch with pagination and optional status filter."""
        docs = self.list_batch_documents(batch_id)
        if status:
            docs = [d for d in docs if (d.status.value if hasattr(d.status, "value") else d.status) == status]
        return docs[offset : offset + limit], len(docs)


    @abstractmethod
    def find_document_by_hash(self, document_hash: str) -> DocumentIngestionRecord | None:
        """Lookup an existing document by its content SHA-256 hash across all batches."""
        pass

    @abstractmethod
    def save_document_hash_index(
        self,
        document_hash: str,
        document_id: str,
        batch_id: str,
        s3_key: str | None = None,
    ) -> None:
        """Register a document content hash index item for fast duplicate lookups."""
        pass

    def save_extraction_result(self, batch_id: str, document_id: str, result: Any) -> None:
        """Store structured extraction result in repository."""
        pass

    def get_extraction_result(self, batch_id: str, document_id: str) -> dict[str, Any] | None:
        """Retrieve structured extraction result from repository."""
        return None


class JobQueue(ABC):
    """Abstract contract for background job distribution and queuing (e.g. SQS)."""

    @abstractmethod
    def send_job(self, job: ProcessingJob) -> str:
        """Publish a processing job message and return the message identifier."""
        pass

    @abstractmethod
    def receive_jobs(
        self,
        max_messages: int = 1,
        wait_time_seconds: int = 10,
        visibility_timeout: int | None = None,
    ) -> list[tuple[ProcessingJob, str]]:
        """Receive available jobs as pairs of (ProcessingJob, receipt_handle)."""
        pass

    @abstractmethod
    def ack_job(self, receipt_handle: str) -> None:
        """Acknowledge successful completion by deleting the job message from queue."""
        pass

    @abstractmethod
    def nack_job(self, receipt_handle: str, visibility_timeout: int = 0) -> None:
        """Reject or release message back to queue for retry by resetting visibility."""
        pass


class SecretProvider(ABC):
    """Abstract contract for retrieving application secrets (e.g. Secrets Manager)."""

    @abstractmethod
    def get_secret(self, secret_name: str) -> str:
        """Retrieve plaintext secret value by secret name."""
        pass
