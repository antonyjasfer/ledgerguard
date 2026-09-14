"""Batch and Document Ingestion domain models for LedgerGuard Phase 7 & 8.

Defines schemas, explicit states, and serialization for multi-document batch ingestion,
document hashing, duplicate tracking, autonomous extraction, and downstream job dispatch.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, Field


class BatchStatus(str, Enum):
    """Lifecycle states for a bulk invoice ingestion batch."""
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    UPLOADING = "UPLOADING"
    QUEUING = "QUEUING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_EXCEPTIONS = "COMPLETED_WITH_EXCEPTIONS"
    FAILED = "FAILED"


class DocumentStatus(str, Enum):
    """Lifecycle states for an individual document within an ingestion batch."""
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    UPLOADING = "UPLOADING"
    STORED = "STORED"
    AWAITING_EXTRACTION = "AWAITING_EXTRACTION"
    EXTRACTING = "EXTRACTING"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    EXTRACTION_VALIDATED = "EXTRACTION_VALIDATED"
    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    AUTO_APPROVED = "AUTO_APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCKED = "BLOCKED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"
    FAILED = "FAILED" 


class DocumentIngestionRecord(BaseModel):
    """Authoritative metadata record for an individual ingested invoice document."""

    document_id: str = Field(
        default_factory=lambda: f"doc_{uuid.uuid4().hex[:12]}",
        description="Unique document identifier",
    )
    batch_id: str = Field(..., min_length=1, description="Associated batch identifier")
    original_filename: str = Field(..., min_length=1, description="Client-provided filename")
    safe_filename: str = Field(..., min_length=1, description="Sanitized, traversal-safe filename")
    content_type: str = Field(default="application/pdf", description="MIME content type")
    file_size: int = Field(default=0, ge=0, description="Size in bytes")
    document_hash: str = Field(..., min_length=1, description="SHA-256 hex digest of file bytes")
    s3_key: str | None = Field(default=None, description="S3 storage key if uploaded")
    status: DocumentStatus = Field(default=DocumentStatus.RECEIVED, description="Document processing status")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC creation timestamp",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC last update timestamp",
    )
    error_code: str | None = Field(default=None, description="Error code if rejected/failed")
    error_message: str | None = Field(default=None, description="Safe error explanation if rejected/failed")
    matched_document_id: str | None = Field(default=None, description="Prior document ID if duplicate")
    matched_batch_id: str | None = Field(default=None, description="Prior batch ID if duplicate")
    duplicate_reason: str | None = Field(default=None, description="Explanation for duplicate detection")
    idempotency_key: str | None = Field(default=None, description="Idempotency token for ingestion operation")

    # Phase 8: Extraction traceability
    extraction_status: str | None = Field(default=None, description="Phase 8 extraction outcome")
    overall_confidence: float | None = Field(default=None, description="Extraction aggregate confidence score")
    extractor_provider: str | None = Field(default=None, description="Provider used for extraction")
    extractor_version: str | None = Field(default=None, description="Version of extractor applied")
    extracted_invoice_id: str | None = Field(default=None, description="Associated canonical invoice ID")
    extraction_summary: dict[str, Any] | None = Field(default=None, description="Sanitized extraction summary")

    # Phase 9: Scale & Retry Lifecycle Fields
    attempt_count: int = Field(default=0, ge=0, description="Total execution attempts")
    max_attempts: int = Field(default=3, ge=1, description="Maximum permitted execution attempts")
    last_error_category: str | None = Field(default=None, description="Classification of last encountered error")
    last_attempt_at: str | None = Field(default=None, description="ISO timestamp of last execution attempt")

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB single-table item format."""
        item: dict[str, Any] = {
            "PK": f"BATCH#{self.batch_id}",
            "SK": f"DOCUMENT#{self.document_id}",
            "entity_type": "BATCH_DOCUMENT",
            "document_id": self.document_id,
            "batch_id": self.batch_id,
            "original_filename": self.original_filename,
            "safe_filename": self.safe_filename,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "document_hash": self.document_hash,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.s3_key:
            item["s3_key"] = self.s3_key
        if self.error_code:
            item["error_code"] = self.error_code
        if self.error_message:
            item["error_message"] = self.error_message
        if self.matched_document_id:
            item["matched_document_id"] = self.matched_document_id
        if self.matched_batch_id:
            item["matched_batch_id"] = self.matched_batch_id
        if self.duplicate_reason:
            item["duplicate_reason"] = self.duplicate_reason
        if self.idempotency_key:
            item["idempotency_key"] = self.idempotency_key
        if self.extraction_status:
            item["extraction_status"] = self.extraction_status
        if self.overall_confidence is not None:
            item["overall_confidence"] = str(round(self.overall_confidence, 4))
        if self.extractor_provider:
            item["extractor_provider"] = self.extractor_provider
        if self.extractor_version:
            item["extractor_version"] = self.extractor_version
        if self.extracted_invoice_id:
            item["extracted_invoice_id"] = self.extracted_invoice_id
        if self.extraction_summary:
            item["extraction_summary"] = self.extraction_summary
        item["attempt_count"] = self.attempt_count
        item["max_attempts"] = self.max_attempts
        if self.last_error_category:
            item["last_error_category"] = self.last_error_category
        if self.last_attempt_at:
            item["last_attempt_at"] = self.last_attempt_at
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "DocumentIngestionRecord":
        """Reconstruct record from DynamoDB item."""
        status_val = item.get("status", DocumentStatus.RECEIVED.value)
        try:
            status_enum = DocumentStatus(status_val)
        except ValueError:
            status_enum = DocumentStatus.RECEIVED

        overall_conf = item.get("overall_confidence")
        if overall_conf is not None:
            try:
                overall_conf = float(overall_conf)
            except (ValueError, TypeError):
                overall_conf = None

        return cls(
            document_id=item["document_id"],
            batch_id=item["batch_id"],
            original_filename=item["original_filename"],
            safe_filename=item["safe_filename"],
            content_type=item.get("content_type", "application/pdf"),
            file_size=int(item.get("file_size", 0)),
            document_hash=item["document_hash"],
            s3_key=item.get("s3_key"),
            status=status_enum,
            created_at=item.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=item.get("updated_at", datetime.now(timezone.utc).isoformat()),
            error_code=item.get("error_code"),
            error_message=item.get("error_message"),
            matched_document_id=item.get("matched_document_id"),
            matched_batch_id=item.get("matched_batch_id"),
            duplicate_reason=item.get("duplicate_reason"),
            idempotency_key=item.get("idempotency_key"),
            extraction_status=item.get("extraction_status"),
            overall_confidence=overall_conf,
            extractor_provider=item.get("extractor_provider"),
            extractor_version=item.get("extractor_version"),
            extracted_invoice_id=item.get("extracted_invoice_id"),
            extraction_summary=item.get("extraction_summary"),
            attempt_count=int(item.get("attempt_count", 0)),
            max_attempts=int(item.get("max_attempts", 3)),
            last_error_category=item.get("last_error_category"),
            last_attempt_at=item.get("last_attempt_at"),
        )


class BatchRecord(BaseModel):
    """Authoritative metadata record for a bulk invoice ingestion batch."""

    batch_id: str = Field(
        default_factory=lambda: f"LG-BATCH-{uuid.uuid4().hex[:8].upper()}",
        description="Unique batch identifier",
    )
    status: BatchStatus = Field(default=BatchStatus.RECEIVED, description="Batch lifecycle status")
    source: str = Field(default="UI_UPLOAD", description="Originating channel: UI_UPLOAD, CLI_FOLDER, API")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC creation timestamp",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC last update timestamp",
    )

    document_count: int = Field(default=0, ge=0, description="Total documents submitted in batch")
    received_count: int = Field(default=0, ge=0, description="Documents received")
    accepted_count: int = Field(default=0, ge=0, description="Documents validated and stored")
    rejected_count: int = Field(default=0, ge=0, description="Documents rejected during validation")
    duplicate_count: int = Field(default=0, ge=0, description="Documents identified as duplicates")
    failed_count: int = Field(default=0, ge=0, description="Documents that encountered fatal errors")

    # Phase 8 extraction counts
    extracted_count: int = Field(default=0, ge=0, description="Documents successfully extracted")
    low_confidence_count: int = Field(default=0, ge=0, description="Documents requiring review due to confidence")
    extraction_failed_count: int = Field(default=0, ge=0, description="Documents where extraction failed")

    queued_count: int = Field(default=0, ge=0, description="Jobs successfully dispatched to SQS")
    processing_count: int = Field(default=0, ge=0, description="Downstream jobs currently in execution")
    completed_count: int = Field(default=0, ge=0, description="Downstream jobs completed")

    auto_approved_count: int = Field(default=0, ge=0, description="Downstream invoices auto-approved")
    manual_review_count: int = Field(default=0, ge=0, description="Downstream invoices requiring manual review")
    blocked_count: int = Field(default=0, ge=0, description="Downstream invoices blocked")

    error_count: int = Field(default=0, ge=0, description="Number of document-level errors encountered")

    # Phase 9: Scale-Ready Batch Metrics & Timestamps
    started_at: str | None = Field(default=None, description="ISO timestamp when batch processing commenced")
    completed_at: str | None = Field(default=None, description="ISO timestamp when batch reached terminal state")
    last_progress_at: str | None = Field(default=None, description="ISO timestamp of most recent progress update")
    retry_count: int = Field(default=0, ge=0, description="Cumulative retry count across all documents")
    processing_failed: int = Field(default=0, ge=0, description="Total documents failing verification or execution")

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB single-table item format."""
        return {
            "PK": f"BATCH#{self.batch_id}",
            "SK": "METADATA",
            "entity_type": "BATCH_METADATA",
            "batch_id": self.batch_id,
            "status": self.status.value,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "document_count": self.document_count,
            "received_count": self.received_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "duplicate_count": self.duplicate_count,
            "failed_count": self.failed_count,
            "extracted_count": self.extracted_count,
            "low_confidence_count": self.low_confidence_count,
            "extraction_failed_count": self.extraction_failed_count,
            "queued_count": self.queued_count,
            "processing_count": self.processing_count,
            "completed_count": self.completed_count,
            "auto_approved_count": self.auto_approved_count,
            "manual_review_count": self.manual_review_count,
            "blocked_count": self.blocked_count,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "processing_failed": self.processing_failed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "last_progress_at": self.last_progress_at,
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "BatchRecord":
        """Reconstruct record from DynamoDB item."""
        status_val = item.get("status", BatchStatus.RECEIVED.value)
        try:
            status_enum = BatchStatus(status_val)
        except ValueError:
            status_enum = BatchStatus.RECEIVED

        return cls(
            batch_id=item["batch_id"],
            status=status_enum,
            source=item.get("source", "API"),
            created_at=item.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=item.get("updated_at", datetime.now(timezone.utc).isoformat()),
            document_count=int(item.get("document_count", 0)),
            received_count=int(item.get("received_count", 0)),
            accepted_count=int(item.get("accepted_count", 0)),
            rejected_count=int(item.get("rejected_count", 0)),
            duplicate_count=int(item.get("duplicate_count", 0)),
            failed_count=int(item.get("failed_count", 0)),
            extracted_count=int(item.get("extracted_count", 0)),
            low_confidence_count=int(item.get("low_confidence_count", 0)),
            extraction_failed_count=int(item.get("extraction_failed_count", 0)),
            queued_count=int(item.get("queued_count", 0)),
            processing_count=int(item.get("processing_count", 0)),
            completed_count=int(item.get("completed_count", 0)),
            auto_approved_count=int(item.get("auto_approved_count", 0)),
            manual_review_count=int(item.get("manual_review_count", 0)),
            blocked_count=int(item.get("blocked_count", 0)),
            error_count=int(item.get("error_count", 0)),
            retry_count=int(item.get("retry_count", 0)),
            processing_failed=int(item.get("processing_failed", 0)),
            started_at=item.get("started_at"),
            completed_at=item.get("completed_at"),
            last_progress_at=item.get("last_progress_at"),
        )

    def finalize_status(self) -> None:
        """Deterministically determine final batch state based on counters."""
        if self.failed_count > 0 or self.rejected_count > 0 or self.duplicate_count > 0:
            if self.accepted_count > 0 or self.duplicate_count > 0:
                self.status = BatchStatus.COMPLETED_WITH_EXCEPTIONS
            else:
                self.status = BatchStatus.FAILED
        elif self.accepted_count > 0 and self.accepted_count == self.document_count:
            self.status = BatchStatus.COMPLETED
        else:
            self.status = BatchStatus.COMPLETED_WITH_EXCEPTIONS
        self.updated_at = datetime.now(timezone.utc).isoformat()
