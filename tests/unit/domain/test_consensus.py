from datetime import UTC, datetime
from decimal import Decimal

import pytest
from koel.domain.consensus import DIVERSITY_TARGET, consensus
from koel.scraping.types import RateReading


def _reading(slug: str, rate: str) -> RateReading:
    return RateReading(
        source_slug=slug,
        base="USD",
        target="EUR",
        rate=Decimal(rate),
        fetched_at=datetime(2026, 4, 19, tzinfo=UTC),
        latency_ms=100,
    )


class TestConsensus:
    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            consensus([])

    def test_single_reading_rate_is_that_reading(self):
        result = consensus([_reading("xe", "0.85")])
        assert result.rate == Decimal("0.85")
        assert result.sources_count == 1

    def test_single_reading_confidence_is_capped_by_diversity(self):
        # Only 1/3 of diversity target -> confidence = agreement(1.0) * (1/3)
        result = consensus([_reading("xe", "0.85")])
        assert result.confidence == Decimal("0.333")

    def test_three_agreeing_sources_full_confidence(self):
        readings = [
            _reading("xe", "0.8500"),
            _reading("wise", "0.8501"),
            _reading("hexarate", "0.8499"),
        ]
        result = consensus(readings)
        # All within 50bp → agreement = 1.0; 3/3 diversity → full.
        assert result.confidence == Decimal("1.000")
        assert result.sources_count == 3

    def test_outlier_drops_agreement(self):
        readings = [
            _reading("xe", "0.8500"),
            _reading("wise", "0.8501"),
            _reading("hexarate", "0.8499"),
            _reading("forbes", "0.9500"),  # ~10% off — outlier
        ]
        result = consensus(readings)
        # Agreement = 3/4, diversity = full → 0.75
        assert result.confidence == Decimal("0.750")

    def test_median_robust_to_outlier(self):
        readings = [
            _reading("xe", "0.8500"),
            _reading("wise", "0.8501"),
            _reading("hexarate", "0.8499"),
            _reading("forbes", "999.0"),  # extreme outlier
        ]
        result = consensus(readings)
        # Median of 4 sorted [0.8499, 0.85, 0.8501, 999] pulls to 0.85 or 0.8501.
        assert result.rate <= Decimal("0.86")

    def test_weights_pull_median(self):
        # Two low readings, one high reading — unweighted median picks low.
        # Weight the high source by 10x and the median shifts upward.
        readings = [
            _reading("xe", "0.80"),
            _reading("wise", "0.80"),
            _reading("hexarate", "0.90"),
        ]
        unweighted = consensus(readings)
        assert unweighted.rate == Decimal("0.80")

        weighted = consensus(readings, weights={"hexarate": Decimal("10")})
        assert weighted.rate == Decimal("0.90")

    def test_sources_used_preserves_order(self):
        readings = [
            _reading("xe", "0.85"),
            _reading("wise", "0.86"),
            _reading("oanda", "0.84"),
        ]
        result = consensus(readings)
        assert result.sources_used == ("xe", "wise", "oanda")

    def test_diversity_at_target_is_full(self):
        readings = [_reading(f"s{i}", "0.85") for i in range(DIVERSITY_TARGET)]
        result = consensus(readings)
        assert result.confidence == Decimal("1.000")

    def test_diversity_above_target_stays_full(self):
        readings = [_reading(f"s{i}", "0.85") for i in range(DIVERSITY_TARGET + 2)]
        result = consensus(readings)
        assert result.confidence == Decimal("1.000")
