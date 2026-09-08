"""Pydantic request and response schemas for LedgerGuard REST API.

Enforces strict financial precision (Decimal, no floats) and clean API contracts.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.invoice import LineItem, _reject_float


class InvoiceCreateRequest(BaseModel):
    """Request schema for submitting an invoice to LedgerGuard for processing."""

    invoice_id: str = Field(..., min_length=1, description="Unique internal invoice identifier")
    invoice_number: str = Field(..., min_length=1, description="Vendor-assigned invoice number")
    vendor_id: str = Field(..., min_length=1, description="Vendor identifier")
    vendor_name: str = Field(..., min_length=1, description="Vendor legal entity name")
    customer_name: str = Field(default="Global Enterprise Inc", min_length=1, description="Bill-to customer name")
    invoice_date: date = Field(..., description="Invoice issue date")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="ISO currency code")
    subtotal: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice reported subtotal")
    tax: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice reported tax amount")
    discount: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice reported discount")
    total: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice reported grand total")
    line_items: list[LineItem] = Field(default_factory=list, description="List of invoiced line items")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary operational metadata")
    idempotency_key: str | None = Field(default=None, description="Optional client idempotency key")

    @field_validator("subtotal", "tax", "discount", "total", mode="before")
    @classmethod
    def check_no_float(cls, v: Any, info: Any) -> Any:
        if isinstance(v, float):
            raise ValueError(
                f"Floating-point values are strictly forbidden for financial calculations in '{info.field_name}'. "
                f"Use Decimal or a string representation instead."
            )
        return v


class InvoiceCreateResponse(BaseModel):
    """Response schema when an invoice is successfully ingested and queued."""

    invoice_id: str = Field(..., description="Unique internal invoice identifier")
    job_id: str = Field(..., description="Background processing job identifier")
    status: str = Field(default="QUEUED", description="Current queuing status")
    processing_status: str = Field(default="QUEUED", description="Current lifecycle state")
    created_at: str = Field(..., description="ISO UTC creation timestamp")


class DocumentUploadResponse(BaseModel):
    """Response schema when an invoice source document is uploaded to S3."""

    invoice_id: str = Field(..., description="Associated invoice identifier")
    s3_key: str = Field(..., description="S3 object key where document is stored")
    filename: str = Field(..., description="Sanitized document filename")
    file_size: int = Field(..., description="Uploaded document size in bytes")
    uploaded_at: str = Field(..., description="ISO UTC upload timestamp")


class InvoiceStatusResponse(BaseModel):
    """Comprehensive invoice status and verification result representation."""

    invoice_id: str = Field(..., description="Unique internal invoice identifier")
    invoice_number: str = Field(..., description="Vendor-supplied invoice identifier")
    vendor_id: str = Field(..., description="Vendor identifier")
    vendor_name: str = Field(..., description="Vendor legal entity name")
    customer_name: str | None = Field(default=None, description="Customer entity name")
    invoice_date: str = Field(..., description="ISO invoice date string")
    currency: str = Field(..., description="ISO currency code")
    subtotal: Decimal | None = Field(default=None, description="Subtotal amount")
    tax: Decimal | None = Field(default=None, description="Tax amount")
    discount: Decimal | None = Field(default=None, description="Discount amount")
    total: Decimal | None = Field(default=None, description="Grand total amount")
    document_s3_key: str | None = Field(default=None, description="S3 storage key for document")
    processing_status: str = Field(..., description="Current lifecycle state")
    decision: str | None = Field(default=None, description="Final verification decision")
    risk_level: str | None = Field(default=None, description="Assigned risk level")
    risk_score: int | None = Field(default=None, description="Assigned risk score (0-100)")
    agent_run_id: str | None = Field(default=None, description="Associated Strands Agent run ID")
    verification_summary: dict[str, Any] = Field(default_factory=dict, description="Tool evidence summary")
    original_decision: str | None = Field(default=None, description="Automated decision before human review")
    review_decision: str | None = Field(default=None, description="Human reviewer action")
    reviewer: str | None = Field(default=None, description="Human reviewer identifier")
    review_timestamp: str | None = Field(default=None, description="Human review timestamp")
    review_comment: str | None = Field(default=None, description="Human review comment/rationale")
    created_at: str = Field(..., description="Record creation timestamp")
    updated_at: str = Field(..., description="Last updated timestamp")


class AuditEventResponse(BaseModel):
    """Structured audit event response for compliance inspection."""

    event_id: str = Field(..., description="Unique audit event ID")
    invoice_id: str = Field(..., description="Associated invoice ID")
    job_id: str | None = Field(default=None, description="Associated job ID")
    event_type: str = Field(..., description="Categorical audit event type")
    timestamp: str = Field(..., description="ISO UTC event timestamp")
    source: str = Field(..., description="Emitting system component")
    details: dict[str, Any] = Field(default_factory=dict, description="Contextual audit details (sanitized)")


class HumanReviewRequest(BaseModel):
    """Request schema for recording a manual human review on an invoice."""

    reviewer: str = Field(..., min_length=1, description="Identifier of human reviewer")
    action: Literal["APPROVE", "REJECT", "REQUEST_INFORMATION"] = Field(
        ...,
        description="Review action (APPROVE, REJECT, REQUEST_INFORMATION)",
    )
    comment: str = Field(..., min_length=1, description="Reviewer justification and audit notes")


class HumanReviewResponse(BaseModel):
    """Response schema confirming recording of a human review action."""

    invoice_id: str = Field(..., description="Invoice identifier")
    original_decision: str = Field(..., description="Preserved original automated decision")
    review_decision: str = Field(..., description="Human reviewer decision action")
    reviewer: str = Field(..., description="Reviewer identifier")
    review_timestamp: str = Field(..., description="ISO UTC review timestamp")
    review_comment: str = Field(..., description="Reviewer justification comment")
    status: str = Field(..., description="Current invoice lifecycle state")


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str = Field(default="healthy", description="Service health status")
    service: str = Field(default="ledgerguard", description="Service name")
    version: str = Field(default="0.1.0", description="Service version")


class ReadyResponse(BaseModel):
    """Readiness probe response detailing dependencies."""

    status: str = Field(default="ready", description="Readiness status")
    service: str = Field(default="ledgerguard", description="Service name")
    dependencies: dict[str, Any] = Field(default_factory=dict, description="Dependency reachability checks")


class ErrorResponse(BaseModel):
    """Standardized, structured error response that prevents secret or internal leakage."""

    error: str = Field(..., description="Machine-readable error category")
    message: str = Field(..., description="Human-readable error explanation")
    request_id: str | None = Field(default=None, description="Correlation request identifier")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional non-sensitive error details")
