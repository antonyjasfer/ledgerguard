"""Lifecycle states and transitions for invoice verification.

Pure domain model containing ProcessingState enum and transition validation.
Contains no dependencies on services or external libraries.
"""

from enum import Enum


class ProcessingState(str, Enum):
    """Lifecycle states for invoice processing."""
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
        raise ValueError(
            f"Invalid state transition from {current.value} to {target.value}. "
            f"Allowed transitions from {current.value}: {[s.value for s in VALID_TRANSITIONS.get(current, set())]}"
        )
