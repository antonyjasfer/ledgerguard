"""Policy configuration models for LedgerGuard.

Centralizes all business thresholds, tolerances, and rule toggles.
No magic numbers allowed across tool logic.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _reject_float(val: Any, field_name: str) -> Any:
    if isinstance(val, float):
        raise TypeError(f"Floating-point values are forbidden in '{field_name}'. Use Decimal.")
    return val


class PolicyConfig(BaseModel):
    """Centralized configuration for Accounts Payable policy evaluation."""

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

    @field_validator("auto_approval_limit", "high_value_threshold", "arithmetic_tolerance", mode="before")
    @classmethod
    def check_no_float(cls, v: Any, info: Any) -> Any:
        return _reject_float(v, info.field_name)
