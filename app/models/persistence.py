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
    shipping: Decimal | None = Field(default=Decimal("0"))
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
    final_state: str | None = Field(
        default=None,
        description="Authoritative final business state (AUTO_APPROVED, MANUAL_REVIEW, HUMAN_APPROVED, HUMAN_REJECTED, BLOCKED)",
    )

    @property
    def automated_decision(self) -> AgentDecision | None:
        """Original automated verification decision."""
        return self.original_decision or self.decision

    @property
    def human_review_decision(self) -> str | None:
        """Verdict rendered by human reviewer."""
        return self.review_decision

    @property
    def human_review_comment(self) -> str | None:
        """Audit comment from human reviewer."""
        return self.review_comment

    @property
    def human_review_reviewer(self) -> str | None:
        """Identity of human reviewer."""
        return self.reviewer

    @property
    def human_review_timestamp(self) -> str | None:
        """Timestamp of human review."""
        return self.review_timestamp

    def get_final_state(self) -> str:
        """Compute authoritative final business state."""
        from app.models.state import derive_final_state
        return derive_final_state(
            automated_decision=self.original_decision or self.decision,
            human_review_decision=self.review_decision,
            processing_status=self.processing_status,
        ).value

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
        fstate = self.get_final_state()
        raw["final_state"] = fstate
        item = _serialize_for_dynamodb(raw)
        item["PK"] = self.partition_key
        item["SK"] = self.sort_key
        auto_dec = self.original_decision or self.decision
        item["automated_decision"] = auto_dec.value if hasattr(auto_dec, "value") else (str(auto_dec) if auto_dec else None)
        item["human_review_decision"] = self.review_decision
        item["human_review_comment"] = self.review_comment
        item["human_review_reviewer"] = self.reviewer
        item["human_review_timestamp"] = self.review_timestamp
        item["final_state"] = fstate
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "InvoiceRecord":
        """Deserialize a DynamoDB item back into an InvoiceRecord."""
        cleaned = dict(item)
        pk = item.get("PK", "")
        cleaned.pop("PK", None)
        cleaned.pop("SK", None)

        # Ensure required fields have valid fallbacks if item was partially updated
        if not cleaned.get("invoice_id"):
            cleaned["invoice_id"] = pk.replace("INVOICE#", "") if pk.startswith("INVOICE#") else "UNKNOWN"
        if not cleaned.get("invoice_number"):
            cleaned["invoice_number"] = cleaned["invoice_id"]
        if not cleaned.get("vendor_id"):
            cleaned["vendor_id"] = "UNKNOWN"
        if not cleaned.get("vendor_name"):
            cleaned["vendor_name"] = "Unknown Vendor"
        if not cleaned.get("invoice_date"):
            cleaned["invoice_date"] = cleaned.get("created_at", "2026-01-01")[:10]
        if not cleaned.get("currency"):
            cleaned["currency"] = "USD"
        if not cleaned.get("created_at"):
            cleaned["created_at"] = cleaned.get("updated_at", datetime.now(timezone.utc).isoformat())
        if not cleaned.get("updated_at"):
            cleaned["updated_at"] = cleaned.get("created_at", datetime.now(timezone.utc).isoformat())

        # Synchronize human review aliases
        if "human_review_decision" in cleaned and not cleaned.get("review_decision"):
            cleaned["review_decision"] = cleaned["human_review_decision"]
        if "human_review_comment" in cleaned and not cleaned.get("review_comment"):
            cleaned["review_comment"] = cleaned["human_review_comment"]
        if "human_review_reviewer" in cleaned and not cleaned.get("reviewer"):
            cleaned["reviewer"] = cleaned["human_review_reviewer"]
        if "human_review_timestamp" in cleaned and not cleaned.get("review_timestamp"):
            cleaned["review_timestamp"] = cleaned["human_review_timestamp"]
        if "automated_decision" in cleaned and not cleaned.get("original_decision") and cleaned["automated_decision"]:
            cleaned["original_decision"] = AgentDecision(cleaned["automated_decision"])

        # Backward compatibility for legacy reviewed records in DynamoDB
        rev_dec = str(cleaned.get("review_decision") or "").upper().strip()
        curr_stat = str(cleaned.get("processing_status") or "")
        if rev_dec == "APPROVE" and curr_stat in ("MANUAL_REVIEW", "ProcessingState.MANUAL_REVIEW"):
            cleaned["processing_status"] = ProcessingState.MANUAL_REVIEW
        elif rev_dec == "REJECT" and curr_stat in ("MANUAL_REVIEW", "ProcessingState.MANUAL_REVIEW"):
            cleaned["processing_status"] = ProcessingState.MANUAL_REVIEW

        # Parse status enum
        if "processing_status" in cleaned and isinstance(cleaned["processing_status"], str):
            try:
                cleaned["processing_status"] = ProcessingState(cleaned["processing_status"])
            except ValueError:
                cleaned["processing_status"] = ProcessingState.RECEIVED
        elif "processing_status" not in cleaned:
            cleaned["processing_status"] = ProcessingState.RECEIVED

        if "decision" in cleaned and cleaned["decision"] is not None:
            cleaned["decision"] = AgentDecision(cleaned["decision"])
        if "risk_level" in cleaned and cleaned["risk_level"] is not None:
            cleaned["risk_level"] = RiskLevel(cleaned["risk_level"])
        if "original_decision" in cleaned and cleaned["original_decision"] is not None:
            cleaned["original_decision"] = AgentDecision(cleaned["original_decision"])

        from app.models.state import derive_final_state
        cleaned["final_state"] = derive_final_state(
            automated_decision=cleaned.get("original_decision") or cleaned.get("decision"),
            human_review_decision=cleaned.get("review_decision"),
            processing_status=cleaned.get("processing_status"),
        ).value

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
            shipping=invoice.shipping,
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
            shipping=self.shipping,
            total=self.total,
            line_items=items,
        )

