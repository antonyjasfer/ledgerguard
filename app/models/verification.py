"""Verification enums and result data models for LedgerGuard.

Provides stable, structured schemas for all verification tool outputs.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Status of an individual verification check."""
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DuplicateStatus(str, Enum):
    """Status classification for duplicate invoice detection."""
    NO_DUPLICATE = "NO_DUPLICATE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    CONFIRMED_DUPLICATE = "CONFIRMED_DUPLICATE"


class RiskLevel(str, Enum):
    """Risk severity classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendedAction(str, Enum):
    """Recommended business action resulting from verification."""
    AUTO_APPROVE = "AUTO_APPROVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"


class ArithmeticVerificationResult(BaseModel):
    """Result of deterministic arithmetic verification of an invoice."""
    passed: bool = Field(..., description="Whether arithmetic verification passed within tolerance")
    status: VerificationStatus = Field(..., description="Detailed verification status")
    expected_subtotal: Decimal | None = Field(default=None, description="Sum of line item subtotals")
    actual_subtotal: Decimal | None = Field(default=None, description="Invoice reported subtotal")
    expected_tax: Decimal | None = Field(default=None, description="Expected tax amount")
    actual_tax: Decimal | None = Field(default=None, description="Invoice reported tax amount")
    expected_discount: Decimal | None = Field(default=None, description="Expected discount amount")
    actual_discount: Decimal | None = Field(default=None, description="Invoice reported discount amount")
    expected_total: Decimal | None = Field(default=None, description="Calculated grand total")
    actual_total: Decimal | None = Field(default=None, description="Invoice reported grand total")
    difference: Decimal | None = Field(default=None, description="Absolute difference between expected and actual total")
    currency: str | None = Field(default=None, description="Currency of calculation")
    details: list[str] = Field(default_factory=list, description="Descriptive list of issues or calculation details")


class DuplicateCheckResult(BaseModel):
    """Result of duplicate invoice checking against historical records."""
    status: DuplicateStatus = Field(..., description="Duplicate status classification")
    matched_invoice_ids: list[str] = Field(default_factory=list, description="IDs of matching historical invoices")
    match_reasons: list[str] = Field(default_factory=list, description="Deterministic reasons for the match")
    details: list[str] = Field(default_factory=list, description="Additional context or notes")


class VendorHistoryResult(BaseModel):
    """Aggregated historical vendor profile and spend statistics."""
    vendor_id: str = Field(..., description="Vendor identifier")
    invoice_count: int = Field(default=0, ge=0, description="Total historical invoice count")
    total_spend: dict[str, Decimal] = Field(default_factory=dict, description="Total spend grouped by currency")
    average_invoice_amount: dict[str, Decimal] = Field(default_factory=dict, description="Average spend grouped by currency")
    largest_invoice_amount: dict[str, Decimal] = Field(default_factory=dict, description="Largest spend grouped by currency")
    first_invoice_date: date | None = Field(default=None, description="Date of first historical invoice")
    last_invoice_date: date | None = Field(default=None, description="Date of most recent historical invoice")
    currency_distribution: dict[str, Decimal] = Field(default_factory=dict, description="Spend per currency code")
    recent_invoice_count: int = Field(default=0, ge=0, description="Invoices within the configured recent window")
    new_vendor: bool = Field(default=True, description="True if no prior invoice history exists")


class PolicyViolation(BaseModel):
    """Individual policy rule evaluation failure or warning."""
    rule: str = Field(..., description="Identified policy rule name")
    observed_value: str = Field(..., description="Observed value from invoice or verification")
    threshold: str = Field(..., description="Configured rule threshold")
    action: str = Field(..., description="Action mandated by rule (e.g., MANUAL_REVIEW, BLOCK)")


class PolicyVerificationResult(BaseModel):
    """Result of evaluating invoice against corporate AP policies."""
    passed: bool = Field(..., description="True if no blocking violations or review triggers occurred")
    requires_review: bool = Field(default=False, description="True if manual human review is triggered")
    should_block: bool = Field(default=False, description="True if invoice should be blocked from payment")
    violations: list[PolicyViolation] = Field(default_factory=list, description="Triggered policy violations")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking policy warnings")
    rules_evaluated: list[str] = Field(default_factory=list, description="List of all evaluated policy rules")


class RiskResult(BaseModel):
    """Consolidated deterministic risk assessment for an invoice."""
    risk_score: int = Field(..., ge=0, le=100, description="Calculated risk score capped at 100")
    risk_level: RiskLevel = Field(..., description="Categorized risk severity level")
    risk_factors: list[str] = Field(default_factory=list, description="Active risk factor identifiers")
    recommended_action: RecommendedAction = Field(..., description="Recommended workflow action")
