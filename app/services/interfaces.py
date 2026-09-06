"""Service interface abstractions for LedgerGuard data and execution layers.

Decouples business logic, agent orchestration, and worker loops from concrete
cloud providers (boto3) and enables offline deterministic testing.
"""

from abc import ABC, abstractmethod
from typing import Sequence

from app.models.audit import AuditEvent
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
