"""Job models for background asynchronous invoice processing.

Defines the message payload exchanged via SQS and tracked in the state layer.
Raw invoice documents and heavy payloads are explicitly excluded from job messages.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status states for background processing jobs."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class ProcessingJob(BaseModel):
    """Background processing job representation and SQS message payload."""

    job_id: str = Field(
        default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}",
        description="Unique identifier for the processing job",
    )
    invoice_id: str = Field(
        default="",
        description="Target invoice identifier (defaults to document_id if not extracted yet)",
    )
    batch_id: str | None = Field(
        default=None,
        description="Optional bulk batch identifier for batch-ingested documents",
    )
    document_id: str | None = Field(
        default=None,
        description="Optional document identifier for pre-extraction documents",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Optional idempotency key preventing duplicate queue execution",
    )
    s3_bucket: str | None = Field(default=None, description="S3 bucket containing raw invoice document")
    s3_key: str | None = Field(default=None, description="S3 key referencing raw invoice document")
    action: str = Field(default="ingest", description="Job action type: ingest, extract, verify")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary lightweight job metadata")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Current status of the job")
    attempt: int = Field(default=1, ge=1, description="Execution attempt counter")
    max_attempts: int = Field(default=3, ge=1, description="Maximum permitted execution attempts")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of creation",
    )
    started_at: str | None = Field(default=None, description="ISO timestamp when processing began")
    completed_at: str | None = Field(default=None, description="ISO timestamp when processing finished")
    processing_version: str = Field(default="1.0", description="Schema version of processing pipeline")
    error_code: str | None = Field(default=None, description="Error classification code if failed")
    error_message: str | None = Field(default=None, description="Safe error description if failed")

    def to_sqs_message(self) -> str:
        """Serialize minimal job data to an SQS JSON message body."""
        payload = {
            "job_id": self.job_id,
            "invoice_id": self.invoice_id or (self.document_id or ""),
            "batch_id": self.batch_id,
            "document_id": self.document_id,
            "idempotency_key": self.idempotency_key,
            "s3_bucket": self.s3_bucket,
            "s3_key": self.s3_key,
            "action": self.action,
            "metadata": self.metadata,
            "status": self.status.value,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "processing_version": self.processing_version,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }
        return json.dumps(payload)

    to_sqs_message_body = to_sqs_message

    @classmethod
    def from_sqs_message(cls, body: str) -> "ProcessingJob":
        """Deserialize an SQS message body into a validated ProcessingJob instance."""
        data = json.loads(body)
        return cls(**data)

    from_sqs_message_body = from_sqs_message
