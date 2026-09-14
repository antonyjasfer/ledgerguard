"""Extraction domain models for LedgerGuard Phase 8.

Defines schemas, field confidence ratings, and extraction results for autonomous
PDF invoice understanding and structured extraction.
Guarantees Decimal precision for all financial values (zero floats allowed).
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.invoice import Invoice, MONEY_QUANTUM, ROUNDING_STRATEGY, quantize_money, _reject_float


class ExtractionStatus(str, Enum):
    """Lifecycle status of document extraction."""
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class FieldStatus(str, Enum):
    """Status of an individual extracted field."""
    VALID = "VALID"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NOT_STATED = "NOT_STATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID_FORMAT = "INVALID_FORMAT"


class ExtractionField(BaseModel):
    """Individual extracted field with confidence score and source evidence."""

    field_name: str = Field(..., description="Canonical field name")
    value: Any = Field(default=None, description="Normalized field value (Decimal for money, str, date, etc.)")
    raw_value: str | None = Field(default=None, description="Raw verbatim string extracted from document")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score 0.0-1.0")
    source_page: int | None = Field(default=1, description="1-indexed source document page number")
    source_text: str | None = Field(default=None, description="Source context snippet or anchor")
    status: FieldStatus = Field(default=FieldStatus.VALID, description="Field validation status")

    @field_validator("value", mode="before")
    @classmethod
    def check_no_float_value(cls, v: Any, info: Any) -> Any:
        # Floating-point values are strictly forbidden for monetary fields
        return _reject_float(v, "ExtractionField.value")

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to a safe, serializable summary."""
        val_str = str(self.value) if isinstance(self.value, Decimal) else self.value
        return {
            "field_name": self.field_name,
            "value": val_str,
            "raw_value": self.raw_value,
            "confidence": round(self.confidence, 4),
            "source_page": self.source_page,
            "source_text": self.source_text,
            "status": self.status.value,
        }


class ExtractionLineItem(BaseModel):
    """Structured line item extracted from invoice document."""

    description: ExtractionField
    quantity: ExtractionField
    unit_price: ExtractionField
    amount: ExtractionField
    sku: ExtractionField | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "description": self.description.to_summary_dict(),
            "quantity": self.quantity.to_summary_dict(),
            "unit_price": self.unit_price.to_summary_dict(),
            "amount": self.amount.to_summary_dict(),
            "sku": self.sku.to_summary_dict() if self.sku else None,
            "confidence": round(self.confidence, 4),
        }


class ExtractionResult(BaseModel):
    """Complete structured extraction result for a document."""

    document_id: str = Field(..., description="Document identifier")
    batch_id: str | None = Field(default=None, description="Batch identifier if ingested as batch")
    status: ExtractionStatus = Field(..., description="Overall extraction outcome")
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Aggregate confidence score")
    invoice_fields: dict[str, ExtractionField] = Field(default_factory=dict, description="Header & metadata fields")
    line_items: list[ExtractionLineItem] = Field(default_factory=list, description="Extracted line items")
    financials: dict[str, ExtractionField] = Field(default_factory=dict, description="Financial summary fields")

    # Authoritative financial comparisons (all strictly Decimal or None)
    computed_subtotal: Decimal | None = None
    declared_total: Decimal | None = None
    computed_total: Decimal | None = None
    estimated_payable_amount: Decimal | None = None
    discrepancy: Decimal | None = None

    warnings: list[str] = Field(default_factory=list, description="Non-fatal extraction warnings")
    errors: list[str] = Field(default_factory=list, description="Extraction or validation errors")
    extracted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 extraction timestamp",
    )
    extractor_provider: str = Field(default="PdfTextExtractor", description="Provider used for extraction")
    extractor_version: str = Field(default="1.0.0", description="Extractor implementation version")
    reconstructed_invoice: Invoice | None = Field(default=None, description="Normalized canonical invoice if valid")

    @field_validator(
        "computed_subtotal",
        "declared_total",
        "computed_total",
        "estimated_payable_amount",
        "discrepancy",
        mode="before",
    )
    @classmethod
    def check_no_float_results(cls, v: Any, info: Any) -> Any:
        return _reject_float(v, info.field_name)

    def to_dynamodb_summary(self) -> dict[str, Any]:
        """Generate a compact, safe representation suitable for DynamoDB single-table items."""
        return {
            "status": self.status.value,
            "overall_confidence": round(self.overall_confidence, 4),
            "extractor_provider": self.extractor_provider,
            "extractor_version": self.extractor_version,
            "extracted_at": self.extracted_at,
            "computed_subtotal": str(self.computed_subtotal) if self.computed_subtotal is not None else None,
            "declared_total": str(self.declared_total) if self.declared_total is not None else None,
            "computed_total": str(self.computed_total) if self.computed_total is not None else None,
            "estimated_payable_amount": str(self.estimated_payable_amount) if self.estimated_payable_amount is not None else None,
            "discrepancy": str(self.discrepancy) if self.discrepancy is not None else None,
            "warning_count": len(self.warnings),
            "error_count": len(self.errors),
            "warnings": self.warnings[:10],
            "errors": self.errors[:10],
            "invoice_number": self.invoice_fields.get("invoice_number", ExtractionField(field_name="invoice_number")).value,
            "vendor_name": self.invoice_fields.get("vendor_name", ExtractionField(field_name="vendor_name")).value,
            "invoice_date": str(self.invoice_fields.get("invoice_date", ExtractionField(field_name="invoice_date")).value or ""),
        }

    def to_dict_safe(self) -> dict[str, Any]:
        """Convert entire result to JSON-safe dictionary (converting Decimals to strings)."""
        return {
            "document_id": self.document_id,
            "batch_id": self.batch_id,
            "status": self.status.value,
            "overall_confidence": round(self.overall_confidence, 4),
            "invoice_fields": {k: f.to_summary_dict() for k, f in self.invoice_fields.items()},
            "line_items": [li.to_summary_dict() for li in self.line_items],
            "financials": {k: f.to_summary_dict() for k, f in self.financials.items()},
            "computed_subtotal": str(self.computed_subtotal) if self.computed_subtotal is not None else None,
            "declared_total": str(self.declared_total) if self.declared_total is not None else None,
            "computed_total": str(self.computed_total) if self.computed_total is not None else None,
            "estimated_payable_amount": str(self.estimated_payable_amount) if self.estimated_payable_amount is not None else None,
            "discrepancy": str(self.discrepancy) if self.discrepancy is not None else None,
            "warnings": self.warnings,
            "errors": self.errors,
            "extracted_at": self.extracted_at,
            "extractor_provider": self.extractor_provider,
            "extractor_version": self.extractor_version,
            "reconstructed_invoice": self.reconstructed_invoice.model_dump(mode="json") if self.reconstructed_invoice else None,
        }
