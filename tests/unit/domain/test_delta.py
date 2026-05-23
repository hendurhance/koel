from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from koel.domain.delta import Anchor, should_write_history


def _t(hours: float = 0) -> datetime:
    return datetime(2026, 4, 19, 12, 0, tzinfo=UTC) + timedelta(hours=hours)


class TestDelta:
    def test_no_anchor_always_writes(self):
        assert should_write_history(Decimal("0.85"), _t(), previous=None) is True

    def test_stable_rate_within_heartbeat_skips(self):
        anchor = Anchor(rate=Decimal("0.8500"), observed_at=_t(0))
        # 30 minutes later, rate moved 1bp — below threshold.
        new_rate = Decimal("0.85001")
        assert should_write_history(new_rate, _t(0.5), previous=anchor) is False

    def test_rate_moved_over_threshold_writes(self):
        anchor = Anchor(rate=Decimal("0.8500"), observed_at=_t(0))
        # 5 minutes later, rate moved 10bp.
        new_rate = Decimal("0.8509")
        assert should_write_history(new_rate, _t(5 / 60), previous=anchor) is True

    def test_rate_moved_exactly_at_threshold_writes(self):
        anchor = Anchor(rate=Decimal("0.8500"), observed_at=_t(0))
        # Move of exactly 5bp (0.05%) = 0.8500 * 0.0005 = 0.000425
        new_rate = anchor.rate + Decimal("0.000425")
        assert should_write_history(new_rate, _t(0.1), previous=anchor) is True

    def test_heartbeat_elapsed_writes_even_if_stable(self):
        anchor = Anchor(rate=Decimal("0.8500"), observed_at=_t(0))
        # 1.5 hours later, rate didn't move at all.
        assert should_write_history(anchor.rate, _t(1.5), previous=anchor) is True

    def test_negative_move_treated_same_as_positive(self):
        anchor = Anchor(rate=Decimal("0.8500"), observed_at=_t(0))
        new_rate = Decimal("0.8490")  # down 12bp
        assert should_write_history(new_rate, _t(0.1), previous=anchor) is True

    def test_zero_rate_raises(self):
        anchor = Anchor(rate=Decimal("0.85"), observed_at=_t(0))
        with pytest.raises(ValueError):
            should_write_history(Decimal("0"), _t(0.1), previous=anchor)

    def test_custom_threshold(self):
        anchor = Anchor(rate=Decimal("0.8500"), observed_at=_t(0))
        # 10bp move — above 5bp default but below a custom 20bp threshold.
        new_rate = Decimal("0.8509")
        assert (
            should_write_history(
                new_rate, _t(0.1), previous=anchor, move_threshold_bp=Decimal("20")
            )
            is False
        )

    def test_custom_heartbeat(self):
        anchor = Anchor(rate=Decimal("0.8500"), observed_at=_t(0))
        # 45min elapsed, stable rate — default hbeat(60m) skips, custom(30m) writes.
        assert (
            should_write_history(
                anchor.rate, _t(0.75), previous=anchor, heartbeat=timedelta(minutes=30)
            )
            is True
        )
