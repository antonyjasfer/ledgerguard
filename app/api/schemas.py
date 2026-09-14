"""Pydantic request and response schemas for LedgerGuard REST API.

Enforces strict financial precision (Decimal, no floats) and clean API contracts.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, field_serializer

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
    shipping: Decimal | None = Field(default=Decimal("0"), ge=Decimal("0"), description="Invoice reported shipping amount")
    total: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice reported grand total")
    purchase_order_number: str | None = Field(default=None, description="Optional purchase order reference")
    line_items: list[LineItem] = Field(default_factory=list, description="List of invoiced line items")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary operational metadata")
    idempotency_key: str | None = Field(default=None, description="Optional client idempotency key")

    @field_validator("subtotal", "tax", "discount", "shipping", "total", mode="before")
    @classmethod
    def check_no_float(cls, v: Any, info: Any) -> Any:
        if isinstance(v, float):
            raise ValueError(
                f"Floating-point values are strictly forbidden for financial calculations in '{info.field_name}'. "
                f"Use Decimal or a string representation instead."
            )
        return v


class InvoiceCreateResponse(BaseModel):
    """Response schema returned upon synchronous ingestion and SQS queue dispatch."""

    invoice_id: str = Field(..., description="Unique internal invoice identifier")
    job_id: str = Field(..., description="Background worker processing job identifier")
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
    subtotal: Decimal | None = Field(default=None, description="Invoice subtotal")
    tax: Decimal | None = Field(default=None, description="Invoice tax amount")
    discount: Decimal | None = Field(default=None, description="Invoice discount amount")
    shipping: Decimal | None = Field(default=None, description="Invoice shipping amount")
    total: Decimal | None = Field(default=None, description="Grand total amount")
    document_s3_key: str | None = Field(default=None, description="Storage location of source document")
    processing_status: str = Field(..., description="Current processing state")
    decision: str | None = Field(default=None, description="Automated agent decision")
    risk_level: str | None = Field(default=None, description="Evaluated risk tier (LOW, MEDIUM, HIGH, CRITICAL)")
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


class DashboardStatsResponse(BaseModel):
    """Aggregated processing and risk statistics for the operations dashboard."""

    total_invoices: int = Field(..., description="Total invoices ingested")
    pending_invoices: int = Field(..., description="Invoices currently in non-terminal states")
    processed_invoices: int = Field(..., description="Invoices that have completed verification")
    auto_approved_count: int = Field(..., description="Invoices automatically approved")
    manual_review_count: int = Field(..., description="Invoices routed to human review")
    blocked_count: int = Field(..., description="Invoices blocked by Decision Guard or Agent")
    total_amount_usd: float = Field(..., description="Total cumulative invoice amount in USD")
    average_risk_score: float = Field(..., description="Mean risk score across invoices")
    auto_approval_rate_pct: float = Field(..., description="Percentage of processed invoices auto-approved")
    by_status: dict[str, int] = Field(default_factory=dict, description="Counts keyed by lifecycle state")
    by_decision: dict[str, int] = Field(default_factory=dict, description="Counts keyed by decision verdict")
    by_risk_level: dict[str, int] = Field(default_factory=dict, description="Counts keyed by risk level")
    new_vendors_detected: int = Field(default=0, description="Invoices with new vendors detected")
    duplicate_invoices_detected: int = Field(default=0, description="Invoices flagged as duplicate")
    high_risk_invoices: int = Field(default=0, description="Invoices evaluated at HIGH or CRITICAL risk")
    low_risk_invoices: int = Field(default=0, description="Invoices evaluated at LOW risk")
    total_verified_spend_usd: float = Field(default=0.0, description="Total spend of approved invoices in USD")
    active_policy_summary: dict[str, Any] = Field(default_factory=dict, description="Active corporate policy overview")

    # Phase 8: AP Financial Summary Dashboard Aggregate Fields (Strict Decimal Precision)
    total_invoice_value: Decimal = Field(default=Decimal("0.00"), description="Sum of declared invoice totals")
    total_subtotal: Decimal = Field(default=Decimal("0.00"), description="Sum of line item subtotals")
    total_discount: Decimal = Field(default=Decimal("0.00"), description="Sum of explicitly stated discounts")
    total_shipping: Decimal = Field(default=Decimal("0.00"), description="Sum of explicitly stated shipping fees")
    total_tax: Decimal = Field(default=Decimal("0.00"), description="Sum of explicitly stated taxes")
    estimated_payable_amount: Decimal = Field(default=Decimal("0.00"), description="Sum of calculated payable amounts")
    estimated_payable_coverage_pct: float = Field(default=0.0, description="Percentage of invoices with complete payable data")
    estimated_payable_invoices_count: int = Field(default=0, description="Number of invoices included in payable total")
    auto_approved_value: Decimal = Field(default=Decimal("0.00"), description="Total value of AUTO_APPROVED invoices")
    manual_review_value: Decimal = Field(default=Decimal("0.00"), description="Total value of MANUAL_REVIEW invoices")
    blocked_value: Decimal = Field(default=Decimal("0.00"), description="Total value of BLOCKED invoices")
    duplicate_value: Decimal = Field(default=Decimal("0.00"), description="Total value of detected duplicate invoices")
    extraction_success_count: int = Field(default=0, description="Number of successfully extracted documents")
    extraction_failed_count: int = Field(default=0, description="Number of failed extraction documents")
    low_confidence_count: int = Field(default=0, description="Number of low confidence extraction documents")
    insufficient_data_count: int = Field(default=0, description="Number of documents with insufficient data")

    @field_serializer(
        "total_invoice_value",
        "total_subtotal",
        "total_discount",
        "total_shipping",
        "total_tax",
        "estimated_payable_amount",
        "auto_approved_value",
        "manual_review_value",
        "blocked_value",
        "duplicate_value",
        when_used="json",
    )
    def serialize_financial_decimal(self, v: Decimal) -> str:
        return str(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class InvoiceListItemResponse(BaseModel):
    """Summary representation of an invoice for listing and table views."""

    invoice_id: str
    invoice_number: str
    vendor_id: str
    vendor_name: str
    invoice_date: str
    currency: str
    total: Decimal | None
    processing_status: str
    decision: str | None
    risk_level: str | None
    risk_score: int | None
    created_at: str
    updated_at: str
    document_s3_key: str | None = None
    original_decision: str | None = None
    review_decision: str | None = None


class InvoiceListResponse(BaseModel):
    """Paginated collection of invoice list items."""

    items: list[InvoiceListItemResponse]
    total: int
    limit: int
    offset: int


class PolicyConfigResponse(BaseModel):
    """Corporate accounts payable policy configuration."""

    company_name: str
    company_id: str
    supported_currencies: list[str]
    default_currency: str
    auto_approval_limit: Decimal
    high_value_threshold: Decimal
    new_vendor_requires_review: bool
    duplicate_requires_block: bool
    possible_duplicate_requires_review: bool
    possible_duplicate_days: int
    recent_invoice_days: int
    missing_po_requires_review: bool
    tax_mismatch_requires_review: bool
    arithmetic_mismatch_requires_block: bool
    unsupported_currency_requires_review: bool
    maximum_discount_percent: Decimal
    large_discount_requires_review: bool
    required_fields: list[str]
    approval_matrix_tiers: list[dict[str, Any]]


class VendorRecordResponse(BaseModel):
    """Vendor master directory profile."""

    vendor_id: str
    legal_name: str
    status: str
    country: str
    approved_currencies: list[str]
    payment_terms: str
    po_required: bool
    onboarding_status: str
    bank_verification_status: str
    created_at: str
    historical_invoice_count: int
    historical_total_spend: Decimal
    historical_average_invoice: Decimal
    historical_largest_invoice: Decimal
    normal_invoice_min: Decimal
    normal_invoice_max: Decimal
    aliases: list[str]


class VendorListResponse(BaseModel):
    """List of registered vendors from vendor master."""

    items: list[VendorRecordResponse]
    total: int


# =============================================================================
# Phase 7: Bulk Ingestion Schemas
# =============================================================================

class BatchCreateRequest(BaseModel):
    """Request schema to initialize a bulk ingestion batch."""

    source: str = Field(default="API", description="Originating channel: UI_UPLOAD, CLI_FOLDER, API")
    document_count: int = Field(default=0, ge=0, description="Expected document count if known upfront")


class DocumentIngestionResponse(BaseModel):
    """Response schema for an individual ingested document in a batch."""

    document_id: str
    batch_id: str
    original_filename: str
    safe_filename: str
    content_type: str
    file_size: int
    document_hash: str
    s3_key: str | None = None
    status: str
    created_at: str
    updated_at: str
    error_code: str | None = None
    error_message: str | None = None
    matched_document_id: str | None = None
    matched_batch_id: str | None = None
    duplicate_reason: str | None = None
    idempotency_key: str | None = None
    extraction_status: str | None = None
    overall_confidence: float | None = None
    extractor_provider: str | None = None
    extractor_version: str | None = None
    extracted_invoice_id: str | None = None
    extraction_summary: dict[str, Any] | None = None


class BatchResponse(BaseModel):
    """Authoritative representation of an invoice ingestion batch."""

    batch_id: str
    status: str
    source: str
    created_at: str
    updated_at: str
    document_count: int
    received_count: int
    accepted_count: int
    rejected_count: int
    duplicate_count: int
    failed_count: int
    queued_count: int
    processing_count: int
    completed_count: int
    auto_approved_count: int
    manual_review_count: int
    blocked_count: int
    error_count: int
    extracted_count: int = Field(default=0, description="Extracted documents count")
    low_confidence_count: int = Field(default=0, description="Documents requiring review count")
    extraction_failed_count: int = Field(default=0, description="Extraction failed count")
    documents: list[DocumentIngestionResponse] = Field(default_factory=list)


class BatchListResponse(BaseModel):
    """Paginated list of bulk invoice ingestion batches."""

    items: list[BatchResponse]
    total: int
    limit: int
    offset: int


class BatchDocumentsResponse(BaseModel):
    """List of document records belonging to a batch."""

    batch_id: str
    items: list[DocumentIngestionResponse]
    total: int
    limit: int = 50
    offset: int = 0


class BatchProgressResponse(BaseModel):
    """Authoritative O(1) operational progress summary for a batch."""

    batch_id: str
    status: str
    total_documents: int
    extracted_count: int
    queued_count: int
    processing_count: int
    completed_count: int
    auto_approved_count: int
    manual_review_count: int
    blocked_count: int
    duplicate_count: int
    failed_count: int
    percent_complete: float
    documents_per_minute: float
    elapsed_seconds: int
    retry_count: int = 0


class BatchResumeResponse(BaseModel):
    """Response summary for batch resumption operation."""

    batch_id: str
    resumed_count: int
    status: str
    message: str


# =============================================================================
# Phase 8: Autonomous PDF Understanding & Extraction Schemas
# =============================================================================

class ExtractionFieldCorrection(BaseModel):
    """Field correction submitted by human reviewer."""

    field_name: str = Field(..., description="Target field name being corrected")
    new_value: Any = Field(..., description="Corrected value (Decimal string, date, or text)")
    reason: str | None = Field(default=None, description="Auditable justification for manual override")


class DocumentCorrectionRequest(BaseModel):
    """Request payload for manual AP correction of extracted fields."""

    reviewer_id: str = Field(default="ap_specialist_1", description="Identifier of human reviewer")
    corrections: list[ExtractionFieldCorrection] = Field(..., description="List of field corrections")
    re_verify: bool = Field(default=True, description="Whether to immediately trigger re-verification")


class ExtractionResponse(BaseModel):
    """Authoritative response payload for document extraction endpoint."""

    document_id: str
    batch_id: str | None = None
    status: str
    overall_confidence: float
    invoice_fields: dict[str, Any] = Field(default_factory=dict)
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    financials: dict[str, Any] = Field(default_factory=dict)
    computed_subtotal: str | None = None
    declared_total: str | None = None
    computed_total: str | None = None
    estimated_payable_amount: str | None = None
    discrepancy: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    extracted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extractor_provider: str = Field(default="CompositeDocumentExtractor")
    extractor_version: str = Field(default="1.0.0")
    reconstructed_invoice_id: str | None = None
