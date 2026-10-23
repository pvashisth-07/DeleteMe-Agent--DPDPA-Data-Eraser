from enum import Enum
from typing import Any, Dict, Optional, Set, Tuple

from shared.clock import now_iso
from shared.db import BaseRepository
from shared.logging import setup_logger

logger = setup_logger("tracker_state_machine")


class TrackerState(str, Enum):
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    PARTIAL = "PARTIAL"
    REFUSED = "REFUSED"
    NEEDS_INFO = "NEEDS_INFO"
    OVERDUE = "OVERDUE"
    FOLLOWUP_SENT = "FOLLOWUP_SENT"
    ESCALATION_DRAFTED = "ESCALATION_DRAFTED"
    SEND_FAILED = "SEND_FAILED"


# Valid allowed transitions
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    TrackerState.SENT.value: {
        TrackerState.ACKNOWLEDGED.value,
        TrackerState.RESOLVED.value,
        TrackerState.PARTIAL.value,
        TrackerState.REFUSED.value,
        TrackerState.NEEDS_INFO.value,
        TrackerState.OVERDUE.value,
        TrackerState.SEND_FAILED.value,
    },
    TrackerState.ACKNOWLEDGED.value: {
        TrackerState.RESOLVED.value,
        TrackerState.PARTIAL.value,
        TrackerState.REFUSED.value,
        TrackerState.NEEDS_INFO.value,
        TrackerState.OVERDUE.value,
    },
    TrackerState.NEEDS_INFO.value: {
        TrackerState.RESOLVED.value,
        TrackerState.PARTIAL.value,
        TrackerState.REFUSED.value,
        TrackerState.OVERDUE.value,
    },
    TrackerState.OVERDUE.value: {
        TrackerState.FOLLOWUP_SENT.value,
        TrackerState.RESOLVED.value,
        TrackerState.PARTIAL.value,
        TrackerState.REFUSED.value,
    },
    TrackerState.FOLLOWUP_SENT.value: {
        TrackerState.RESOLVED.value,
        TrackerState.PARTIAL.value,
        TrackerState.REFUSED.value,
        TrackerState.ESCALATION_DRAFTED.value,
    },
    TrackerState.ESCALATION_DRAFTED.value: {
        TrackerState.RESOLVED.value,
    },
    TrackerState.SEND_FAILED.value: {
        TrackerState.SENT.value,
    },
    # Terminal states
    TrackerState.RESOLVED.value: set(),
    TrackerState.PARTIAL.value: set(),
    TrackerState.REFUSED.value: set(),
}

# Terminal states where the deadline timer is stopped
TERMINAL_STATES: Set[str] = {
    TrackerState.RESOLVED.value,
    TrackerState.PARTIAL.value,
    TrackerState.REFUSED.value,
    TrackerState.SEND_FAILED.value,
    TrackerState.ESCALATION_DRAFTED.value,
}


def can_transition(from_state: str, to_state: str) -> bool:
    allowed = VALID_TRANSITIONS.get(from_state, set())
    return to_state in allowed


def is_deadline_active(state: str) -> bool:
    """
    CRITICAL INVARIANT:
    An auto-acknowledgement (ACKNOWLEDGED) or NEEDS_INFO does NOT stop the deadline timer.
    Only terminal states (RESOLVED, PARTIAL, REFUSED) stop the timer.
    """
    return state in {
        TrackerState.SENT.value,
        TrackerState.ACKNOWLEDGED.value,
        TrackerState.NEEDS_INFO.value,
        TrackerState.FOLLOWUP_SENT.value,
    }


def transition_request(
    repo: BaseRepository,
    request_id: str,
    new_state: str,
    reason: str = "",
    ticket_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Executes a validated transition for a request and records the event in the database.
    """
    req = repo.get_request(request_id)
    if not req:
        return False, f"Request {request_id} not found"

    current_state = req.get("state", "UNKNOWN")
    if not can_transition(current_state, new_state):
        err = f"Invalid state transition: {current_state} -> {new_state} for request {request_id}"
        logger.warning(err)
        return False, err

    # Update request row
    repo.update_request_state(request_id, new_state, ticket_id=ticket_id, reason=reason)

    # Record structured event with payload
    batch_id = req.get("batch_id", "")
    session_id = req.get("session_id", "")
    repo.record_event(
        request_id=request_id,
        batch_id=batch_id,
        session_id=session_id,
        from_state=current_state,
        to_state=new_state,
        reason=reason,
        payload=payload or {},
    )

    logger.info(f"Request {request_id} transitioned: {current_state} -> {new_state} (Reason: {reason})")
    return True, f"Successfully transitioned to {new_state}"
