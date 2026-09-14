"""Policy configuration models for LedgerGuard.

Centralizes all corporate business thresholds, tolerances, approval matrix rules, and rule toggles.
No magic numbers allowed across tool logic.
"""

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _reject_float(val: Any, field_name: str) -> Any:
    if isinstance(val, float):
        raise TypeError(f"Floating-point values are forbidden in '{field_name}'. Use Decimal.")
    return val


class ApprovalRoutingTier(str, Enum):
    """Routing level designated by the corporate approval matrix."""
    AUTO_APPROVAL_ALLOWED = "AUTO_APPROVAL_ALLOWED"
    MANAGER_REVIEW = "MANAGER_REVIEW"
    FINANCE_DIRECTOR_REVIEW = "FINANCE_DIRECTOR_REVIEW"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCK = "BLOCK"


class ApprovalMatrixResult(BaseModel):
    """Result of evaluating an invoice against corporate approval thresholds."""
    tier: ApprovalRoutingTier = Field(..., description="Designated approval tier")
    reason: str = Field(..., description="Deterministic explanation for the assigned tier")
    threshold_applied: Decimal | None = Field(default=None, description="Specific threshold boundary applied")


class PolicyConfig(BaseModel):
    """Centralized configuration for Accounts Payable policy evaluation."""

    company_name: str = Field(
        default="LedgerGuard Demo Corporation",
        description="Corporate entity name associated with this policy",
    )
    company_id: str = Field(
        default="LEDGERGUARD-DEMO",
        description="Unique corporate organization identifier",
    )
    supported_currencies: list[str] = Field(
        default_factory=lambda: ["USD", "EUR", "GBP"],
        description="Currencies officially supported by company AP processing",
    )
    default_currency: str = Field(
        default="USD",
        description="Base operational currency",
    )
    auto_approval_limit: Decimal = Field(
        default=Decimal("1000.00"),
        ge=Decimal("0.00"),
        description="Maximum invoice total eligible for automated approval without human review",
    )
    high_value_threshold: Decimal = Field(
        default=Decimal("5000.00"),
        ge=Decimal("0.00"),
        description="Invoice total at or above which an invoice is classified as high-value",
    )
    new_vendor_requires_review: bool = Field(
        default=True,
        description="Whether an invoice from a vendor with no prior history requires human review",
    )
    duplicate_requires_block: bool = Field(
        default=True,
        description="Whether a confirmed duplicate invoice triggers an immediate payment block",
    )
    possible_duplicate_requires_review: bool = Field(
        default=True,
        description="Whether a possible duplicate invoice triggers manual review",
    )
    possible_duplicate_days: int = Field(
        default=7,
        ge=0,
        description="Maximum day proximity threshold between invoices to flag possible duplicate",
    )
    recent_invoice_days: int = Field(
        default=30,
        ge=0,
        description="Number of days from reference date to classify historical invoices as recent",
    )
    arithmetic_tolerance: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Allowed absolute discrepancy between expected and reported totals",
    )
    missing_po_requires_review: bool = Field(
        default=True,
        description="Whether a missing PO when required by vendor/policy triggers manual review",
    )
    tax_mismatch_requires_review: bool = Field(
        default=True,
        description="Whether unverified or mismatching tax amounts trigger manual review",
    )
    arithmetic_mismatch_requires_block: bool = Field(
        default=False,
        description="Whether arithmetic calculation discrepancies trigger an immediate BLOCK",
    )
    unsupported_currency_requires_review: bool = Field(
        default=True,
        description="Whether invoices in currencies outside supported_currencies trigger manual review",
    )
    maximum_discount_percent: Decimal = Field(
        default=Decimal("20.00"),
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
        description="Discount percentage ceiling above which review is mandated",
    )
    large_discount_requires_review: bool = Field(
        default=True,
        description="Whether discounts exceeding maximum_discount_percent trigger manual review",
    )
    required_fields: list[str] = Field(
        default_factory=list,
        description="Fields strictly required for an invoice to be considered valid (empty by default for backward compatibility)",
    )

    @field_validator(
        "auto_approval_limit",
        "high_value_threshold",
        "arithmetic_tolerance",
        "maximum_discount_percent",
        mode="before",
    )
    @classmethod
    def check_no_float(cls, v: Any, info: Any) -> Any:
        return _reject_float(v, info.field_name)

    @classmethod
    def get_demo_enterprise_policy(cls) -> "PolicyConfig":
        """Factory returning the authoritative LedgerGuard Demo Corporation enterprise policy."""
        return cls(
            company_name="LedgerGuard Demo Corporation",
            company_id="LEDGERGUARD-DEMO",
            supported_currencies=["USD", "EUR", "GBP"],
            default_currency="USD",
            auto_approval_limit=Decimal("5000.00"),
            high_value_threshold=Decimal("25000.00"),
            new_vendor_requires_review=True,
            duplicate_requires_block=True,
            possible_duplicate_requires_review=True,
            possible_duplicate_days=7,
            recent_invoice_days=30,
            arithmetic_tolerance=Decimal("0.00"),
            missing_po_requires_review=True,
            tax_mismatch_requires_review=True,
            arithmetic_mismatch_requires_block=True,
            unsupported_currency_requires_review=True,
            maximum_discount_percent=Decimal("20.00"),
            large_discount_requires_review=True,
            required_fields=[
                "invoice_number",
                "vendor_id",
                "vendor_name",
                "invoice_date",
                "currency",
                "line_items",
                "subtotal",
                "total",
            ],
        )


def evaluate_approval_matrix(
    invoice_total: Decimal | None,
    config: PolicyConfig | None = None,
    is_new_vendor: bool = False,
    is_duplicate: bool = False,
    has_arithmetic_mismatch: bool = False,
) -> ApprovalMatrixResult:
    """Determine required approval authority level based on policy rules and total amount."""
    cfg = config or PolicyConfig()

    if is_duplicate and cfg.duplicate_requires_block:
        return ApprovalMatrixResult(
            tier=ApprovalRoutingTier.BLOCK,
            reason="Confirmed duplicate invoice triggers mandatory BLOCK",
            threshold_applied=None,
        )

    if has_arithmetic_mismatch and cfg.arithmetic_mismatch_requires_block:
        return ApprovalMatrixResult(
            tier=ApprovalRoutingTier.BLOCK,
            reason="Arithmetic calculation discrepancy triggers corporate policy BLOCK",
            threshold_applied=None,
        )

    if is_new_vendor and cfg.new_vendor_requires_review:
        return ApprovalMatrixResult(
            tier=ApprovalRoutingTier.MANUAL_REVIEW,
            reason="New vendor without prior transactional history requires manual onboarding review",
            threshold_applied=None,
        )

    if invoice_total is None:
        return ApprovalMatrixResult(
            tier=ApprovalRoutingTier.MANUAL_REVIEW,
            reason="Invoice total is missing or undetermined; manual review required",
            threshold_applied=None,
        )

    if invoice_total <= cfg.auto_approval_limit:
        return ApprovalMatrixResult(
            tier=ApprovalRoutingTier.AUTO_APPROVAL_ALLOWED,
            reason=f"Invoice total {invoice_total} is within auto-approval limit ({cfg.auto_approval_limit})",
            threshold_applied=cfg.auto_approval_limit,
        )

    if invoice_total <= cfg.high_value_threshold:
        return ApprovalMatrixResult(
            tier=ApprovalRoutingTier.MANAGER_REVIEW,
            reason=f"Invoice total {invoice_total} exceeds auto-approval limit ({cfg.auto_approval_limit}); requires Manager Review",
            threshold_applied=cfg.high_value_threshold,
        )

    return ApprovalMatrixResult(
        tier=ApprovalRoutingTier.FINANCE_DIRECTOR_REVIEW,
        reason=f"Invoice total {invoice_total} exceeds high-value threshold ({cfg.high_value_threshold}); requires Finance Director Review",
        threshold_applied=cfg.high_value_threshold,
    )
