"""Unit tests for invoice processing state machine."""

import pytest

from app.services.state import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    ProcessingState,
    can_transition,
    validate_transition,
)


def test_processing_state_members():
    """Verify all required lifecycle states are defined."""
    expected_states = {
        "RECEIVED",
        "QUEUED",
        "PROCESSING",
        "VERIFIED",
        "AUTO_APPROVED",
        "MANUAL_REVIEW",
        "BLOCKED",
        "FAILED",
    }
    actual_states = {s.value for s in ProcessingState}
    assert expected_states == actual_states


def test_valid_transitions():
    """Verify legal state progressions succeed."""
    assert can_transition(ProcessingState.RECEIVED, ProcessingState.QUEUED)
    assert can_transition(ProcessingState.RECEIVED, ProcessingState.PROCESSING)
    assert can_transition(ProcessingState.QUEUED, ProcessingState.PROCESSING)
    assert can_transition(ProcessingState.PROCESSING, ProcessingState.VERIFIED)
    assert can_transition(ProcessingState.PROCESSING, ProcessingState.AUTO_APPROVED)
    assert can_transition(ProcessingState.PROCESSING, ProcessingState.MANUAL_REVIEW)
    assert can_transition(ProcessingState.PROCESSING, ProcessingState.BLOCKED)
    assert can_transition(ProcessingState.PROCESSING, ProcessingState.FAILED)
    assert can_transition(ProcessingState.VERIFIED, ProcessingState.AUTO_APPROVED)
    assert can_transition(ProcessingState.VERIFIED, ProcessingState.MANUAL_REVIEW)
    assert can_transition(ProcessingState.VERIFIED, ProcessingState.BLOCKED)

    # Valid transitions should not raise
    validate_transition(ProcessingState.RECEIVED, ProcessingState.PROCESSING)
    validate_transition(ProcessingState.PROCESSING, ProcessingState.AUTO_APPROVED)


def test_invalid_transitions_raise_value_error():
    """Illegal state jumps must raise ValueError."""
    # Cannot jump directly from RECEIVED to AUTO_APPROVED
    assert not can_transition(ProcessingState.RECEIVED, ProcessingState.AUTO_APPROVED)
    with pytest.raises(ValueError, match="Invalid state transition"):
        validate_transition(ProcessingState.RECEIVED, ProcessingState.AUTO_APPROVED)

    # Cannot jump from QUEUED directly to AUTO_APPROVED
    assert not can_transition(ProcessingState.QUEUED, ProcessingState.AUTO_APPROVED)
    with pytest.raises(ValueError):
        validate_transition(ProcessingState.QUEUED, ProcessingState.AUTO_APPROVED)


def test_terminal_states_cannot_transition():
    """Completed terminal states must have no valid subsequent transitions."""
    for terminal in TERMINAL_STATES:
        for target in ProcessingState:
            assert not can_transition(terminal, target)
            with pytest.raises(ValueError):
                validate_transition(terminal, target)


def test_retry_from_failed_state():
    """Failed jobs can be retried by re-queuing or re-processing."""
    assert can_transition(ProcessingState.FAILED, ProcessingState.QUEUED)
    assert can_transition(ProcessingState.FAILED, ProcessingState.PROCESSING)
    assert not can_transition(ProcessingState.FAILED, ProcessingState.AUTO_APPROVED)
