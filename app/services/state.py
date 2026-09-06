"""Invoice processing state machine for LedgerGuard.

Re-exports ProcessingState enum and transition rules from domain models.
"""

from app.models.state import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    ProcessingState,
    can_transition,
    validate_transition,
)

__all__ = [
    "TERMINAL_STATES",
    "VALID_TRANSITIONS",
    "ProcessingState",
    "can_transition",
    "validate_transition",
]
