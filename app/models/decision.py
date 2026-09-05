"""Structured decision output model for LedgerGuard Agent.

Defines the final structured verdict produced by the autonomous verification agent,
including the decision, evidence trail, and human-review rationale.
"""

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.verification import RecommendedAction, RiskLevel


class AgentDecision(str, Enum):
    """Final verification decision categories."""
    AUTO_APPROVE = "AUTO_APPROVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class EvidenceItem(BaseModel):
    """Single piece of deterministic evidence from a verification tool."""
    source: str = Field(..., description="Name of the verification tool that produced this evidence")
    finding: str = Field(..., description="Primary finding or status from the tool")
    details: dict[str, Any] = Field(default_factory=dict, description="Structured detail payload from the tool")


class VerificationDecision(BaseModel):
    """Final structured decision from the LedgerGuard verification agent."""
    decision: AgentDecision = Field(..., description="Final verification decision")
    confidence: str = Field(
        default="EVIDENCE_BASED",
        description="Confidence qualifier (EVIDENCE_BASED, PARTIAL_EVIDENCE, INSUFFICIENT_EVIDENCE)"
    )
    summary: str = Field(..., description="Human-readable summary of the decision rationale")
    evidence: list[EvidenceItem] = Field(default_factory=list, description="Ordered list of evidence from tool invocations")
    risk_level: RiskLevel | None = Field(default=None, description="Final risk level from the risk engine")
    risk_score: int | None = Field(default=None, ge=0, le=100, description="Numeric risk score (0-100)")
    tools_called: list[str] = Field(default_factory=list, description="Ordered list of tool names actually invoked")
    requires_human: bool = Field(default=False, description="Whether the decision requires human review")
    human_review_reason: str | None = Field(default=None, description="Explanation of why human review is needed")
