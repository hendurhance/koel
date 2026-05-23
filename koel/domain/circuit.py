from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

Status = Literal["closed", "open", "half_open"]

FAILURE_THRESHOLD = 5
COOLDOWN = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class CircuitState:
    status: Status
    consecutive_failures: int
    opened_at: datetime | None


def on_success(_state: CircuitState) -> CircuitState:
    """A successful call always closes the breaker and clears the failure count."""
    return CircuitState(status="closed", consecutive_failures=0, opened_at=None)


def on_failure(
    state: CircuitState,
    now: datetime,
    *,
    threshold: int = FAILURE_THRESHOLD,
) -> CircuitState:
    """Apply a failure to the current state."""
    new_fail = state.consecutive_failures + 1

    if state.status == "half_open":
        # Probe failed — reopen with a fresh cooldown.
        return CircuitState(status="open", consecutive_failures=new_fail, opened_at=now)

    if state.status == "open":
        # Shouldn't normally happen (open ⇒ we didn't call), but be safe.
        return CircuitState(status="open", consecutive_failures=new_fail, opened_at=state.opened_at)

    if new_fail >= threshold:
        return CircuitState(status="open", consecutive_failures=new_fail, opened_at=now)

    return CircuitState(
        status="closed",
        consecutive_failures=new_fail,
        opened_at=state.opened_at,
    )


def allow_call(
    state: CircuitState,
    now: datetime,
    *,
    cooldown: timedelta = COOLDOWN,
) -> tuple[bool, CircuitState]:
    """Decide whether the breaker permits a call right now.

    Transitions an expired ``open`` into ``half_open`` as a side-effect of the
    check — the caller should persist the returned state if it differs.
    """
    if state.status == "closed":
        return True, state
    if state.status == "half_open":
        return True, state

    # open: check whether cooldown has elapsed.
    if state.opened_at is None or now - state.opened_at >= cooldown:
        probe_state = CircuitState(
            status="half_open",
            consecutive_failures=state.consecutive_failures,
            opened_at=state.opened_at,
        )
        return True, probe_state
    return False, state
