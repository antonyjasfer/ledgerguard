"""Persistence data models and DynamoDB serialization for LedgerGuard.

Enforces clean translation between domain models, Decimal-based financial precision,
and DynamoDB storage requirements. Floating-point values are strictly prohibited.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.decision import AgentDecision
from app.models.invoice import Invoice
from app.models.verification import RiskLevel
from app.models.state import ProcessingState


def _serialize_for_dynamodb(val: Any) -> Any:
    """Recursively convert Python values into DynamoDB Table-compatible types.

    - Enum -> enum.value (str)
    - date / datetime -> ISO format string
    - BaseModel -> dict then sanitized
    - Decimal -> preserved as Decimal (DynamoDB Table native type)
    - float -> converted to Decimal or string
    - dict -> recursively processed
    - list / tuple / set -> recursively processed
    - None -> None
    """
    if val is None:
        return None
    if hasattr(val, "value"):  # Enum
        return str(val.value)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, BaseModel):
        return _serialize_for_dynamodb(val.model_dump())
    if isinstance(val, float):
        return Decimal(str(val))
    if isinstance(val, Decimal):
        return val
    if isinstance(val, dict):
        return {str(k): _serialize_for_dynamodb(v) for k, v in val.items() if v is not None}
    if isinstance(val, (list, tuple)):
        return [_serialize_for_dynamodb(x) for x in val]
    if isinstance(val, set):
        return {_serialize_for_dynamodb(x) for x in val}
    return val


class InvoiceRecord(BaseModel):
    """Persisted representation of an invoice, its lifecycle state, and verification verdict."""

    invoice_id: str = Field(..., min_length=1, description="Unique internal invoice identifier")
    invoice_number: str = Field(..., min_length=1, description="Vendor-supplied invoice identifier")
    vendor_id: str = Field(..., min_length=1, description="Vendor identifier")
    vendor_name: str = Field(..., min_length=1, description="Vendor legal entity name")
    invoice_date: str = Field(..., description="ISO invoice date string (YYYY-MM-DD)")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    subtotal: Decimal | None = Field(default=None)
    tax: Decimal | None = Field(default=None)
    discount: Decimal | None = Field(default=None)
    total: Decimal | None = Field(default=None)
    document_s3_key: str | None = Field(default=None, description="S3 storage key for raw source document")
    processing_status: ProcessingState = Field(
        default=ProcessingState.RECEIVED,
        description="Current lifecycle state",
    )
    decision: AgentDecision | None = Field(
        default=None,
        description="Final verification decision (AUTO_APPROVE, MANUAL_REVIEW, BLOCK, ESCALATE)",
    )
    risk_level: RiskLevel | None = Field(default=None, description="Assigned risk tier")
    risk_score: int | None = Field(default=None, ge=0, le=100, description="Risk score (0-100)")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Record creation timestamp",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Last updated timestamp",
    )
    agent_run_id: str | None = Field(default=None, description="Associated Strands Agent run ID")
    verification_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of tool evidence and reasoning",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Unique idempotency token (e.g., job_id or invoice_id+version)",
    )
    customer_name: str | None = Field(
        default=None,
        description="Bill-to customer name",
    )
    line_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Serialized line items",
    )
    original_decision: AgentDecision | None = Field(
        default=None,
        description="Original automated decision before human review",
    )
    review_decision: str | None = Field(
        default=None,
        description="Human review verdict (APPROVE, REJECT, REQUEST_INFORMATION)",
    )
    reviewer: str | None = Field(
        default=None,
        description="Identity of human reviewer",
    )
    review_timestamp: str | None = Field(
        default=None,
        description="ISO timestamp when human review occurred",
    )
    review_comment: str | None = Field(
        default=None,
        description="Reviewer rationale or audit comment",
    )

    @property
    def partition_key(self) -> str:
        """DynamoDB partition key (PK)."""
        return f"INVOICE#{self.invoice_id}"

    @property
    def sort_key(self) -> str:
        """DynamoDB sort key (SK) for metadata entity."""
        return "METADATA"

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Serialize into a DynamoDB item dict with primary keys and clean types."""
        raw = self.model_dump()
        item = _serialize_for_dynamodb(raw)
        item["PK"] = self.partition_key
        item["SK"] = self.sort_key
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "InvoiceRecord":
        """Deserialize a DynamoDB item back into an InvoiceRecord."""
        cleaned = dict(item)
        cleaned.pop("PK", None)
        cleaned.pop("SK", None)
        # Parse status enum
        if "processing_status" in cleaned and isinstance(cleaned["processing_status"], str):
            cleaned["processing_status"] = ProcessingState(cleaned["processing_status"])
        if "decision" in cleaned and cleaned["decision"] is not None:
            cleaned["decision"] = AgentDecision(cleaned["decision"])
        if "risk_level" in cleaned and cleaned["risk_level"] is not None:
            cleaned["risk_level"] = RiskLevel(cleaned["risk_level"])
        if "original_decision" in cleaned and cleaned["original_decision"] is not None:
            cleaned["original_decision"] = AgentDecision(cleaned["original_decision"])
        return cls(**cleaned)

    @classmethod
    def from_invoice(
        cls,
        invoice: Invoice,
        document_s3_key: str | None = None,
        status: ProcessingState = ProcessingState.RECEIVED,
        idempotency_key: str | None = None,
    ) -> "InvoiceRecord":
        """Factory method to construct an InvoiceRecord from an Invoice domain model."""
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            invoice_id=invoice.invoice_id,
            invoice_number=invoice.invoice_number,
            vendor_id=invoice.vendor_id,
            vendor_name=invoice.vendor_name,
            invoice_date=invoice.invoice_date.isoformat() if hasattr(invoice.invoice_date, "isoformat") else str(invoice.invoice_date),
            currency=invoice.currency,
            subtotal=invoice.subtotal,
            tax=invoice.tax,
            discount=invoice.discount,
            total=invoice.total,
            customer_name=invoice.customer_name,
            line_items=[item.model_dump() for item in invoice.line_items],
            document_s3_key=document_s3_key,
            processing_status=status,
            created_at=now,
            updated_at=now,
            idempotency_key=idempotency_key,
        )

    def to_invoice(self) -> Invoice:
        """Reconstruct Invoice domain model from InvoiceRecord."""
        from datetime import date
        from app.models.invoice import LineItem
        items = []
        for it in self.line_items:
            try:
                items.append(LineItem(**it))
            except Exception:
                pass
        inv_date = self.invoice_date
        if isinstance(inv_date, str):
            try:
                inv_date = date.fromisoformat(inv_date.split("T")[0])
            except Exception:
                inv_date = date.today()
        return Invoice(
            invoice_id=self.invoice_id,
            invoice_number=self.invoice_number,
            vendor_id=self.vendor_id,
            vendor_name=self.vendor_name,
            customer_name=self.customer_name or "Global Enterprise Inc",
            invoice_date=inv_date,
            currency=self.currency,
            subtotal=self.subtotal,
            tax=self.tax,
            discount=self.discount,
            total=self.total,
            line_items=items,
        )
