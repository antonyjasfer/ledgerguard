"""Audit event models for LedgerGuard.

Provides immutable, structured audit trail records for compliance, observability,
and verification tracking. Explicitly forbids secrets and credentials in audit payloads.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AuditEventType(str, Enum):
    """Categories of auditable processing events."""
    DOCUMENT_RECEIVED = "DOCUMENT_RECEIVED"
    JOB_QUEUED = "JOB_QUEUED"
    PROCESSING_STARTED = "PROCESSING_STARTED"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    DECISION_CREATED = "DECISION_CREATED"
    DECISION_GUARDED = "DECISION_GUARDED"
    PROCESSING_COMPLETED = "PROCESSING_COMPLETED"
    PROCESSING_FAILED = "PROCESSING_FAILED"


_SENSITIVE_PATTERNS = {
    "password", "secret", "token", "api_key", "apikey",
    "access_key", "secret_key", "authorization", "bearer",
    "credentials", "credential",
}


def _scrub_sensitive(obj: Any) -> Any:
    """Recursively scrub any sensitive keys from details dictionaries."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(pat in k_lower for pat in _SENSITIVE_PATTERNS):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = _scrub_sensitive(v)
        return cleaned
    if isinstance(obj, list):
        return [_scrub_sensitive(item) for item in obj]
    return obj


class AuditEvent(BaseModel):
    """Structured audit event record for LedgerGuard processing steps."""

    event_id: str = Field(
        default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}",
        description="Unique identifier for the audit event",
    )
    invoice_id: str = Field(..., min_length=1, description="Associated invoice identifier")
    job_id: str | None = Field(default=None, description="Associated background job identifier")
    event_type: AuditEventType = Field(..., description="Category of event")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of occurrence",
    )
    source: str = Field(default="ledgerguard_worker", description="Emitting component identifier")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured contextual metadata (must never include credentials or raw PDFs)",
    )

    @field_validator("details", mode="before")
    @classmethod
    def scrub_details(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return _scrub_sensitive(v)
        return v
