import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from koel.scraping.base import Scraper
from koel.scraping.exceptions import BlockedError, NetworkError
from koel.scraping.service import SourceSpec, scrape_pair
from koel.scraping.types import RateReading


class _FakeScraper(Scraper):
    """Test double. Subclasses set a class-level rate or exception."""

    slug = "fake"
    rate: Decimal | None = None
    raise_exc: Exception | None = None
    latency_ms: int = 42

    def _url_for(self, base: str, target: str | None = None) -> str:
        return f"fake://{base}/{target}"

    async def _fetch_one(self, base: str, target: str) -> RateReading:
        if self.raise_exc is not None:
            raise self.raise_exc
        assert self.rate is not None
        return RateReading(
            source_slug=self.slug,
            base=base,
            target=target,
            rate=self.rate,
            fetched_at=datetime.now(tz=UTC),
            latency_ms=self.latency_ms,
        )


def _make_scraper_cls(
    slug: str,
    *,
    rate: Decimal | None = None,
    exc: Exception | None = None,
) -> type[Scraper]:
    return type(
        f"Scraper_{slug}",
        (_FakeScraper,),
        {"slug": slug, "rate": rate, "raise_exc": exc},
    )


def _spec(slug: str, weight: str = "1") -> SourceSpec:
    return SourceSpec(
        id=uuid.uuid4(),
        slug=slug,
        base_url="https://example.invalid",
        weight=Decimal(weight),
        config={},
    )


class TestScrapePair:
    async def test_empty_sources_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            await scrape_pair("USD", "EUR", [], client=None)  # type: ignore[arg-type]

    async def test_single_success_produces_consensus(self):
        factory = {"alpha": _make_scraper_cls("alpha", rate=Decimal("0.85"))}.__getitem__
        outcome = await scrape_pair(
            "USD", "EUR", [_spec("alpha")], client=None, scraper_factory=factory
        )
        assert outcome.consensus is not None
        assert outcome.consensus.rate == Decimal("0.85")
        assert outcome.outcomes[0].success is True

    async def test_all_failures_yields_no_consensus(self):
        factory = {
            "alpha": _make_scraper_cls("alpha", exc=BlockedError("blocked")),
            "beta": _make_scraper_cls("beta", exc=NetworkError("down")),
        }.__getitem__
        outcome = await scrape_pair(
            "USD", "EUR", [_spec("alpha"), _spec("beta")], client=None, scraper_factory=factory
        )
        assert outcome.consensus is None
        assert all(o.success is False for o in outcome.outcomes)
        assert "BlockedError" in outcome.outcomes[0].error
        assert "NetworkError" in outcome.outcomes[1].error

    async def test_mixed_results_consensus_uses_only_successes(self):
        factory = {
            "alpha": _make_scraper_cls("alpha", rate=Decimal("0.85")),
            "beta": _make_scraper_cls("beta", exc=NetworkError("down")),
            "gamma": _make_scraper_cls("gamma", rate=Decimal("0.86")),
        }.__getitem__
        sources = [_spec("alpha"), _spec("beta"), _spec("gamma")]
        outcome = await scrape_pair("USD", "EUR", sources, client=None, scraper_factory=factory)
        assert outcome.consensus is not None
        assert outcome.consensus.sources_count == 2
        assert set(outcome.consensus.sources_used) == {"alpha", "gamma"}

    async def test_weights_passed_to_consensus(self):
        # Two "low" readings, one "high". Heavy weight on the high one shifts median.
        factory = {
            "alpha": _make_scraper_cls("alpha", rate=Decimal("0.80")),
            "beta": _make_scraper_cls("beta", rate=Decimal("0.80")),
            "gamma": _make_scraper_cls("gamma", rate=Decimal("0.90")),
        }.__getitem__
        sources = [
            _spec("alpha", "1"),
            _spec("beta", "1"),
            _spec("gamma", "10"),
        ]
        outcome = await scrape_pair("USD", "EUR", sources, client=None, scraper_factory=factory)
        assert outcome.consensus is not None
        assert outcome.consensus.rate == Decimal("0.90")

    async def test_unknown_slug_is_recorded_not_raised(self):
        def factory(slug: str) -> type[Scraper]:
            raise KeyError(f"no scraper {slug}")

        outcome = await scrape_pair(
            "USD", "EUR", [_spec("ghost")], client=None, scraper_factory=factory
        )
        assert outcome.consensus is None
        assert outcome.outcomes[0].success is False
        assert "ghost" in outcome.outcomes[0].error

    async def test_unexpected_exception_is_captured(self):
        factory = {
            "alpha": _make_scraper_cls("alpha", exc=RuntimeError("boom")),
        }.__getitem__
        outcome = await scrape_pair(
            "USD", "EUR", [_spec("alpha")], client=None, scraper_factory=factory
        )
        assert outcome.consensus is None
        assert "RuntimeError" in outcome.outcomes[0].error
