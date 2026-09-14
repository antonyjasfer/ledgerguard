"""Decision guard for LedgerGuard.

Final deterministic safety layer that validates the agent's decision against deterministic tool results.
The LLM's recommendation is advisory; deterministic safety rules have final authority.
"""

from app.models.decision import AgentDecision, VerificationDecision
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    RiskLevel,
    RiskResult,
    VerificationStatus,
)


class DecisionGuardResult:
    """Result of the decision guard validation."""

    def __init__(
        self,
        original_decision: AgentDecision,
        final_decision: AgentDecision,
        was_overridden: bool,
        override_reason: str | None = None,
    ):
        self.original_decision = original_decision
        self.final_decision = final_decision
        self.was_overridden = was_overridden
        self.override_reason = override_reason


def validate_agent_decision(
    agent_decision: AgentDecision,
    arithmetic: ArithmeticVerificationResult | None = None,
    duplicate: DuplicateCheckResult | None = None,
    policy: PolicyVerificationResult | None = None,
    risk: RiskResult | None = None,
) -> DecisionGuardResult:
    """Validate the agent's proposed decision against deterministic safety rules.

    Rules (in priority order):
    1. Confirmed duplicate -> MUST be BLOCK
    2. Policy block -> MUST be BLOCK
    3. Critical risk -> MUST be BLOCK
    4. Arithmetic FAIL -> MUST NOT be AUTO_APPROVE (BLOCK if policy blocks, else MANUAL_REVIEW)
    5. Policy requires review -> MUST NOT be AUTO_APPROVE (at minimum MANUAL_REVIEW)
    6. High or Medium risk -> MUST NOT be AUTO_APPROVE (at minimum MANUAL_REVIEW)
    7. Insufficient data -> MUST NOT be AUTO_APPROVE (at minimum MANUAL_REVIEW)

    The guard may escalate a decision but never downgrades safety.

    Args:
        agent_decision: The decision proposed by the LLM agent.
        arithmetic: Arithmetic verification result (if available).
        duplicate: Duplicate check result (if available).
        policy: Policy evaluation result (if available).
        risk: Risk scoring result (if available).

    Returns:
        DecisionGuardResult with original and final (possibly overridden) decisions.
    """

    # Rule 1: Confirmed duplicate -> BLOCK
    if duplicate is not None and duplicate.status == DuplicateStatus.CONFIRMED_DUPLICATE:
        if agent_decision != AgentDecision.BLOCK:
            return DecisionGuardResult(
                original_decision=agent_decision,
                final_decision=AgentDecision.BLOCK,
                was_overridden=True,
                override_reason="CONFIRMED_DUPLICATE requires BLOCK. Agent proposed: " + agent_decision.value,
            )

    # Rule 2: Policy block -> BLOCK
    if policy is not None and policy.should_block:
        if agent_decision != AgentDecision.BLOCK:
            return DecisionGuardResult(
                original_decision=agent_decision,
                final_decision=AgentDecision.BLOCK,
                was_overridden=True,
                override_reason="Policy mandates BLOCK. Agent proposed: " + agent_decision.value,
            )

    # Rule 3: Critical risk -> BLOCK
    if risk is not None and risk.risk_level == RiskLevel.CRITICAL:
        if agent_decision != AgentDecision.BLOCK:
            return DecisionGuardResult(
                original_decision=agent_decision,
                final_decision=AgentDecision.BLOCK,
                was_overridden=True,
                override_reason="CRITICAL risk requires BLOCK. Agent proposed: " + agent_decision.value,
            )

    # Rule 4: Arithmetic FAIL -> at minimum MANUAL_REVIEW (or BLOCK if policy dictated)
    if arithmetic is not None and arithmetic.status == VerificationStatus.FAIL:
        if agent_decision == AgentDecision.AUTO_APPROVE:
            return DecisionGuardResult(
                original_decision=agent_decision,
                final_decision=AgentDecision.MANUAL_REVIEW,
                was_overridden=True,
                override_reason="Arithmetic verification FAIL prevents AUTO_APPROVE.",
            )

    # Rule 5: Policy review required -> prevents AUTO_APPROVE
    if policy is not None and policy.requires_review:
        if agent_decision == AgentDecision.AUTO_APPROVE:
            return DecisionGuardResult(
                original_decision=agent_decision,
                final_decision=AgentDecision.MANUAL_REVIEW,
                was_overridden=True,
                override_reason="Policy review required prevents AUTO_APPROVE.",
            )

    # Rule 6: High/Medium risk -> prevents AUTO_APPROVE
    if risk is not None and risk.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
        if agent_decision == AgentDecision.AUTO_APPROVE:
            return DecisionGuardResult(
                original_decision=agent_decision,
                final_decision=AgentDecision.MANUAL_REVIEW,
                was_overridden=True,
                override_reason=f"{risk.risk_level.value} risk prevents AUTO_APPROVE.",
            )

    # Rule 7: Insufficient data -> at minimum MANUAL_REVIEW
    if arithmetic is not None and arithmetic.status == VerificationStatus.INSUFFICIENT_DATA:
        if agent_decision == AgentDecision.AUTO_APPROVE:
            return DecisionGuardResult(
                original_decision=agent_decision,
                final_decision=AgentDecision.MANUAL_REVIEW,
                was_overridden=True,
                override_reason="INSUFFICIENT_DATA prevents AUTO_APPROVE.",
            )

    # No override needed
    return DecisionGuardResult(
        original_decision=agent_decision,
        final_decision=agent_decision,
        was_overridden=False,
        override_reason=None,
    )
