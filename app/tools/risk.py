"""Deterministic risk scoring engine for LedgerGuard invoices.

Calculates composite invoice risk score based on active risk factors.
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
    VendorHistoryResult,
    VerificationStatus,
)


class RiskWeights(BaseModel):
    """Centralized weights for deterministic risk factor scoring."""

    confirmed_duplicate: int = Field(default=100, description="Risk weight for confirmed duplicate")
    arithmetic_mismatch: int = Field(default=50, description="Risk weight for arithmetic calculation discrepancy")
    policy_violation: int = Field(default=30, description="Risk weight for corporate policy violations")
    new_vendor: int = Field(default=20, description="Risk weight for new/unrecognized vendor")
    high_value: int = Field(default=20, description="Risk weight for invoice meeting/exceeding high value threshold")
    possible_duplicate: int = Field(default=15, description="Risk weight for possible duplicate match")


def calculate_invoice_risk(
    arithmetic: ArithmeticVerificationResult,
    duplicate: DuplicateCheckResult,
    vendor_history: VendorHistoryResult,
    policy: PolicyVerificationResult,
    invoice: Invoice,
    weights: RiskWeights | None = None,
    high_value_threshold: Decimal = Decimal("5000.00"),
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
    if vendor_history.new_vendor:
        risk_factors.append("NEW_VENDOR")
        raw_score += cfg_weights.new_vendor

    # Factor 5: High value
    if invoice.total is not None and invoice.total >= high_value_threshold:
        risk_factors.append("HIGH_VALUE_INVOICE")
        raw_score += cfg_weights.high_value

    # Cap score at 100
    risk_score = min(raw_score, 100)

    # CRITICAL OVERRIDE: Confirmed duplicates MUST ALWAYS result in CRITICAL severity
    if duplicate.status == DuplicateStatus.CONFIRMED_DUPLICATE:
        risk_level = RiskLevel.CRITICAL
        risk_score = 100
    else:
        if risk_score >= 75:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 50:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 25:
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
