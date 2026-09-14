"""Deterministic risk scoring engine for LedgerGuard invoices.

Calculates composite invoice risk score based on active deterministic risk factors.
Enforces explicit threshold tiers, a hard score cap of 100, and a mandatory
critical override for confirmed duplicates.
Precedence of recommended actions respects blocking policies first.
Zero LLM reliance, fully deterministic and reproducible.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.invoice import Invoice
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    RecommendedAction,
    RiskLevel,
    RiskResult,
    VendorContextResult,
    VendorHistoryResult,
    VerificationStatus,
)


class RiskWeights(BaseModel):
    """Centralized weights for deterministic risk factor scoring."""

    confirmed_duplicate: int = Field(default=100, description="Risk weight for confirmed duplicate (critical override)")
    arithmetic_mismatch: int = Field(default=50, description="Risk weight for arithmetic calculation discrepancy")
    possible_duplicate: int = Field(default=40, description="Risk weight for possible duplicate match")
    vendor_not_approved: int = Field(default=40, description="Risk weight for suspended/rejected/inactive vendor")
    high_value: int = Field(default=20, description="Risk weight for invoice meeting/exceeding high value threshold")
    new_vendor: int = Field(default=25, description="Risk weight for new/unrecognized vendor")
    policy_violation: int = Field(default=25, description="Risk weight for corporate policy violations")
    unsupported_currency: int = Field(default=25, description="Risk weight for unsupported or unapproved currency")
    amount_above_historical_range: int = Field(default=20, description="Risk weight for exceeding historical normal max")
    missing_required_field: int = Field(default=20, description="Risk weight for missing mandatory invoice field")
    large_discount: int = Field(default=15, description="Risk weight for discount exceeding policy ceiling")


def calculate_invoice_risk(
    arithmetic: ArithmeticVerificationResult,
    duplicate: DuplicateCheckResult,
    vendor_history: VendorHistoryResult,
    policy: PolicyVerificationResult,
    invoice: Invoice,
    weights: RiskWeights | None = None,
    high_value_threshold: Decimal = Decimal("5000.00"),
    vendor_context: VendorContextResult | None = None,
) -> RiskResult:
    """Compute deterministic risk score and recommended AP workflow action.

    Args:
        arithmetic: Result from arithmetic verification tool.
        duplicate: Result from duplicate detection tool.
        vendor_history: Historical vendor metrics.
        policy: Policy evaluation result.
        invoice: Candidate invoice.
        weights: Configured risk factor point allocations.
        high_value_threshold: Threshold to consider invoice high value for risk scoring.
        vendor_context: Optional vendor master context comparison.

    Returns:
        RiskResult with final score, risk level, active factors, and recommended action.
    """
    cfg_weights = weights or RiskWeights()
    risk_factors: list[str] = []
    raw_score: int = 0

    # Factor 1: Duplicate checks
    if duplicate.status == DuplicateStatus.CONFIRMED_DUPLICATE:
        risk_factors.append("CONFIRMED_DUPLICATE")
        raw_score += cfg_weights.confirmed_duplicate
    elif duplicate.status == DuplicateStatus.POSSIBLE_DUPLICATE:
        risk_factors.append("POSSIBLE_DUPLICATE")
        raw_score += cfg_weights.possible_duplicate

    # Factor 2: Arithmetic verification
    if not arithmetic.passed or arithmetic.status in (
        VerificationStatus.FAIL,
        VerificationStatus.INSUFFICIENT_DATA,
    ):
        risk_factors.append("ARITHMETIC_MISMATCH")
        raw_score += cfg_weights.arithmetic_mismatch

    # Factor 3: Policy violations
    if policy.violations:
        risk_factors.append("POLICY_VIOLATION")
        raw_score += cfg_weights.policy_violation

    # Factor 4: New vendor
    if vendor_context is not None:
        is_new = vendor_context.is_new_vendor
    else:
        is_new = vendor_history.new_vendor

    if is_new:
        risk_factors.append("NEW_VENDOR")
        raw_score += cfg_weights.new_vendor

    # Factor 5: High value
    if invoice.total is not None and invoice.total >= high_value_threshold:
        risk_factors.append("HIGH_VALUE_INVOICE")
        raw_score += cfg_weights.high_value

    # Factor 6: Amount above historical range
    if vendor_context is not None and vendor_context.is_above_normal_range:
        risk_factors.append("AMOUNT_ABOVE_HISTORICAL_RANGE")
        raw_score += cfg_weights.amount_above_historical_range

    # Factor 7: Unsupported currency
    if vendor_context is not None and not vendor_context.currency_supported:
        risk_factors.append("UNSUPPORTED_CURRENCY")
        raw_score += cfg_weights.unsupported_currency

    # Factor 8: Vendor suspended / rejected in master (not pending new vendor)
    if vendor_context is not None and vendor_context.vendor_exists:
        if (
            vendor_context.status in ("SUSPENDED", "INACTIVE")
            or vendor_context.onboarding_status == "REJECTED"
            or (not vendor_context.is_active and not vendor_context.is_new_vendor)
        ):
            risk_factors.append("VENDOR_NOT_APPROVED")
            raw_score += cfg_weights.vendor_not_approved

    # Factor 9: Missing required fields (identified via policy violations)
    if any(v.rule == "REQUIRED_FIELDS_CHECK" for v in policy.violations):
        risk_factors.append("MISSING_REQUIRED_FIELD")
        raw_score += cfg_weights.missing_required_field

    # Factor 10: Large discount
    if any(v.rule == "LARGE_DISCOUNT_REVIEW" for v in policy.violations):
        risk_factors.append("LARGE_DISCOUNT")
        raw_score += cfg_weights.large_discount

    # Cap score at 100
    risk_score = min(raw_score, 100)

    # CRITICAL OVERRIDE: Confirmed duplicates MUST ALWAYS result in CRITICAL severity
    if duplicate.status == DuplicateStatus.CONFIRMED_DUPLICATE:
        risk_level = RiskLevel.CRITICAL
        risk_score = 100
    else:
        # Configurable Risk Tiers:
        # 0–19: LOW
        # 20–49: MEDIUM
        # 50–74: HIGH
        # 75–100: CRITICAL
        if risk_score >= 75:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 50:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 20:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

    # Workflow Action Precedence:
    # 1. Blocking policy or CRITICAL risk -> BLOCK
    # 2. Review policy or HIGH / MEDIUM risk -> MANUAL_REVIEW
    # 3. Clean and LOW risk -> AUTO_APPROVE
    if policy.should_block or risk_level == RiskLevel.CRITICAL:
        recommended_action = RecommendedAction.BLOCK
    elif policy.requires_review or risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
        recommended_action = RecommendedAction.MANUAL_REVIEW
    else:
        recommended_action = RecommendedAction.AUTO_APPROVE

    return RiskResult(
        risk_score=risk_score,
        risk_level=risk_level,
        risk_factors=risk_factors,
        recommended_action=recommended_action,
    )
