"""Lifecycle states and transitions for invoice verification.

Pure domain model containing ProcessingState enum, FinalState enum,
and transition validation.
Contains no dependencies on services or external libraries.
"""

from enum import Enum
from typing import Any


class ProcessingState(str, Enum):
    """Lifecycle states of an invoice through the ingestion and verification pipeline."""

    RECEIVED = "RECEIVED"
    DOCUMENT_INGESTED = "DOCUMENT_INGESTED"
    AWAITING_EXTRACTION = "AWAITING_EXTRACTION"
    EXTRACTING = "EXTRACTING"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    EXTRACTION_VALIDATED = "EXTRACTION_VALIDATED"
    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    AUTO_APPROVED = "AUTO_APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"

class FinalState(str, Enum):
    """Authoritative business final states."""
    AUTO_APPROVED = "AUTO_APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    BLOCKED = "BLOCKED"
    PROCESSING = "PROCESSING"
    RECEIVED = "RECEIVED"
    FAILED = "FAILED"


VALID_TRANSITIONS: dict[ProcessingState, set[ProcessingState]] = {
    ProcessingState.RECEIVED: {
        ProcessingState.DOCUMENT_INGESTED,
        ProcessingState.AWAITING_EXTRACTION,
        ProcessingState.QUEUED,
        ProcessingState.PROCESSING,
        ProcessingState.FAILED,
    },
    ProcessingState.DOCUMENT_INGESTED: {
        ProcessingState.AWAITING_EXTRACTION,
        ProcessingState.EXTRACTING,
        ProcessingState.QUEUED,
        ProcessingState.FAILED,
    },
    ProcessingState.AWAITING_EXTRACTION: {
        ProcessingState.EXTRACTING,
        ProcessingState.EXTRACTION_COMPLETED,
        ProcessingState.EXTRACTION_VALIDATED,
        ProcessingState.INSUFFICIENT_CONFIDENCE,
        ProcessingState.QUEUED,
        ProcessingState.PROCESSING,
        ProcessingState.FAILED,
    },
    ProcessingState.EXTRACTING: {
        ProcessingState.EXTRACTION_COMPLETED,
        ProcessingState.EXTRACTION_VALIDATED,
        ProcessingState.INSUFFICIENT_CONFIDENCE,
        ProcessingState.MANUAL_REVIEW,
        ProcessingState.FAILED,
    },
    ProcessingState.EXTRACTION_COMPLETED: {
        ProcessingState.EXTRACTION_VALIDATED,
        ProcessingState.INSUFFICIENT_CONFIDENCE,
        ProcessingState.MANUAL_REVIEW,
        ProcessingState.QUEUED,
        ProcessingState.PROCESSING,
        ProcessingState.FAILED,
    },
    ProcessingState.EXTRACTION_VALIDATED: {
        ProcessingState.QUEUED,
        ProcessingState.PROCESSING,
        ProcessingState.FAILED,
    },
    ProcessingState.INSUFFICIENT_CONFIDENCE: {
        ProcessingState.MANUAL_REVIEW,
        ProcessingState.QUEUED,
        ProcessingState.PROCESSING,
        ProcessingState.FAILED,
    },
    ProcessingState.QUEUED: {
        ProcessingState.PROCESSING,
        ProcessingState.FAILED,
    },
    ProcessingState.PROCESSING: {
        ProcessingState.VERIFIED,
        ProcessingState.AUTO_APPROVED,
        ProcessingState.MANUAL_REVIEW,
        ProcessingState.BLOCKED,
        ProcessingState.FAILED,
    },
    ProcessingState.VERIFIED: {
        ProcessingState.AUTO_APPROVED,
        ProcessingState.MANUAL_REVIEW,
        ProcessingState.BLOCKED,
        ProcessingState.FAILED,
    },
    ProcessingState.AUTO_APPROVED: set(),
    ProcessingState.MANUAL_REVIEW: set(),
    ProcessingState.BLOCKED: set(),
    ProcessingState.FAILED: {
        ProcessingState.QUEUED,
        ProcessingState.PROCESSING,
        ProcessingState.AWAITING_EXTRACTION,
        ProcessingState.EXTRACTING,
    },
}

TERMINAL_STATES: set[ProcessingState] = {
    ProcessingState.AUTO_APPROVED,
    ProcessingState.MANUAL_REVIEW,
    ProcessingState.BLOCKED,
}


def can_transition(current: ProcessingState, target: ProcessingState) -> bool:
    """Check if transitioning from current state to target state is allowed."""
    return target in VALID_TRANSITIONS.get(current, set())


def validate_transition(current: ProcessingState, target: ProcessingState) -> None:
    """Validate that a state transition is legal, raising ValueError if invalid."""
    if not can_transition(current, target):
        allowed = [s.value for s in VALID_TRANSITIONS.get(current, set())]
        raise ValueError(
            f"Invalid state transition from {current.value} to {target.value}. Allowed transitions: {allowed}"
        )


def derive_final_state(
    automated_decision: Any,
    human_review_decision: str | None = None,
    processing_status: Any = None,
) -> FinalState:
    """
    Derive authoritative final business state without overwriting automated evidence.

    Authoritative Rules:
    - IF automated decision == BLOCK or processing_status == BLOCKED:
      FINAL = BLOCKED
      (Human APPROVE cannot bypass a hard safety BLOCK; Decision Guard is authoritative)

    - IF automated decision in (MANUAL_REVIEW, ESCALATE) or processing_status == MANUAL_REVIEW:
        - human decision == APPROVE or processing_status == HUMAN_APPROVED: FINAL = HUMAN_APPROVED
        - human decision == REJECT or processing_status == HUMAN_REJECTED:   FINAL = HUMAN_REJECTED
        - human decision is null:                                           FINAL = MANUAL_REVIEW

    - IF automated decision == AUTO_APPROVE or processing_status == AUTO_APPROVED:
      FINAL = AUTO_APPROVED

    - IF processing_status == FAILED:
      FINAL = FAILED

    - Non-terminal lifecycle states:
      return PROCESSING / RECEIVED
    """
    auto_dec_str = automated_decision.value if hasattr(automated_decision, "value") else str(automated_decision or "").upper().strip()
    human_dec_str = str(human_review_decision or "").upper().strip() if human_review_decision else None
    proc_stat_str = processing_status.value if hasattr(processing_status, "value") else str(processing_status or "").upper().strip()

    # Hard safety block: Decision Guard is authoritative
    if auto_dec_str == "BLOCK" or proc_stat_str == "BLOCKED":
        return FinalState.BLOCKED

    # Human approved or rejected
    if human_dec_str == "APPROVE" or proc_stat_str == "HUMAN_APPROVED":
        return FinalState.HUMAN_APPROVED
    if human_dec_str == "REJECT" or proc_stat_str == "HUMAN_REJECTED":
        return FinalState.HUMAN_REJECTED

    # Manual review routing awaiting action
    if auto_dec_str in ("MANUAL_REVIEW", "ESCALATE") or proc_stat_str == "MANUAL_REVIEW":
        return FinalState.MANUAL_REVIEW

    # Auto approved
    if auto_dec_str == "AUTO_APPROVE" or proc_stat_str == "AUTO_APPROVED":
        return FinalState.AUTO_APPROVED

    # Failed
    if proc_stat_str == "FAILED":
        return FinalState.FAILED

    # Active processing / non-terminal
    if proc_stat_str in (
        "QUEUED", "PROCESSING", "EXTRACTING", "AWAITING_EXTRACTION",
        "DOCUMENT_INGESTED", "EXTRACTION_COMPLETED", "EXTRACTION_VALIDATED",
        "INSUFFICIENT_CONFIDENCE", "VERIFIED"
    ):
        return FinalState.PROCESSING

    if proc_stat_str:
        try:
            return FinalState(proc_stat_str)
        except ValueError:
            pass

    return FinalState.RECEIVED
