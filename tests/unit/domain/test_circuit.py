from datetime import UTC, datetime, timedelta

from koel.domain.circuit import (
    COOLDOWN,
    FAILURE_THRESHOLD,
    CircuitState,
    allow_call,
    on_failure,
    on_success,
)


def _t(seconds: float = 0) -> datetime:
    return datetime(2026, 4, 19, 12, 0, tzinfo=UTC) + timedelta(seconds=seconds)


def _closed(failures: int = 0) -> CircuitState:
    return CircuitState(status="closed", consecutive_failures=failures, opened_at=None)


class TestOnSuccess:
    def test_closed_stays_closed_and_resets_count(self):
        result = on_success(_closed(failures=3))
        assert result.status == "closed"
        assert result.consecutive_failures == 0
        assert result.opened_at is None

    def test_half_open_closes_on_success(self):
        state = CircuitState(status="half_open", consecutive_failures=5, opened_at=_t(0))
        result = on_success(state)
        assert result.status == "closed"
        assert result.consecutive_failures == 0


class TestOnFailure:
    def test_closed_below_threshold_stays_closed(self):
        result = on_failure(_closed(failures=FAILURE_THRESHOLD - 2), _t())
        assert result.status == "closed"
        assert result.consecutive_failures == FAILURE_THRESHOLD - 1

    def test_closed_at_threshold_opens(self):
        result = on_failure(_closed(failures=FAILURE_THRESHOLD - 1), _t(100))
        assert result.status == "open"
        assert result.consecutive_failures == FAILURE_THRESHOLD
        assert result.opened_at == _t(100)

    def test_half_open_failure_reopens_with_fresh_cooldown(self):
        state = CircuitState(status="half_open", consecutive_failures=5, opened_at=_t(0))
        result = on_failure(state, _t(600))
        assert result.status == "open"
        assert result.opened_at == _t(600)
        assert result.consecutive_failures == 6

    def test_custom_threshold(self):
        result = on_failure(_closed(failures=1), _t(), threshold=2)
        assert result.status == "open"


class TestAllowCall:
    def test_closed_always_allows(self):
        ok, state = allow_call(_closed(), _t())
        assert ok is True
        assert state.status == "closed"

    def test_half_open_allows_probe(self):
        s = CircuitState(status="half_open", consecutive_failures=5, opened_at=_t(0))
        ok, state = allow_call(s, _t(60))
        assert ok is True
        assert state.status == "half_open"

    def test_open_within_cooldown_denies(self):
        opened = _t(0)
        s = CircuitState(status="open", consecutive_failures=5, opened_at=opened)
        ok, state = allow_call(s, opened + COOLDOWN - timedelta(seconds=1))
        assert ok is False
        assert state.status == "open"

    def test_open_after_cooldown_transitions_to_half_open(self):
        opened = _t(0)
        s = CircuitState(status="open", consecutive_failures=5, opened_at=opened)
        ok, state = allow_call(s, opened + COOLDOWN)
        assert ok is True
        assert state.status == "half_open"
        # Failure count is preserved until a success actually closes it.
        assert state.consecutive_failures == 5

    def test_open_with_null_opened_at_allows(self):
        # Defensive: a malformed row shouldn't trap the source forever.
        s = CircuitState(status="open", consecutive_failures=5, opened_at=None)
        ok, state = allow_call(s, _t())
        assert ok is True
        assert state.status == "half_open"


class TestLifecycle:
    def test_full_trip_and_recover(self):
        """Walk a source through closed → open → half_open → closed."""
        state = _closed()
        start = _t(0)
        # Accumulate failures to trip.
        for i in range(FAILURE_THRESHOLD):
            state = on_failure(state, start + timedelta(seconds=i))
        assert state.status == "open"

        # Denied during cooldown.
        ok, state = allow_call(state, start + timedelta(seconds=1))
        assert ok is False

        # After cooldown → probe allowed.
        probe_time = state.opened_at + COOLDOWN
        ok, state = allow_call(state, probe_time)
        assert ok is True
        assert state.status == "half_open"

        # Probe succeeds → closed.
        state = on_success(state)
        assert state.status == "closed"
        assert state.consecutive_failures == 0
