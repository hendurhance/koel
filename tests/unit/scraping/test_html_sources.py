from __future__ import annotations

import json
from decimal import Decimal
from importlib import resources
from typing import Any

import pytest
from koel.scraping.exceptions import ParseError
from koel.scraping.registry import SCRAPERS
from koel.scraping.sources.ft import FtScraper
from koel.scraping.sources.investing import InvestingScraper
from koel.scraping.sources.markets_insider import MarketsInsiderScraper
from koel.scraping.sources.marketwatch import MarketWatchScraper
from koel.scraping.sources.yahoo_finance import YahooFinanceScraper
from koel.scraping.types import RateReading

NEW_SLUGS = {"marketwatch", "markets_insider", "ft", "yahoo_finance", "investing"}


class StubClient:
    """Returns the same canned payload for both text and JSON fetches."""

    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: list[str] = []

    async def get_text(self, url: str, *, impersonate: str | None = None) -> tuple[Any, int]:
        self.calls.append(url)
        return self.payload, 42

    async def get_json(self, url: str, *, impersonate: str | None = None) -> tuple[Any, int]:
        self.calls.append(url)
        return self.payload, 42


@pytest.mark.asyncio
async def test_yahoo_finance_chart_api():
    payload = {"chart": {"result": [{"meta": {"regularMarketPrice": 0.8617}}]}}
    client = StubClient(payload)
    scraper = YahooFinanceScraper(client, base_url="https://query1.finance.yahoo.com", config={})
    reading = await scraper._fetch_one("USD", "EUR")
    assert isinstance(reading, RateReading)
    assert reading.source_slug == "yahoo_finance"
    assert reading.rate == Decimal("0.8617")
    assert client.calls == ["https://query1.finance.yahoo.com/v8/finance/chart/USDEUR=X"]


@pytest.mark.asyncio
async def test_yahoo_finance_missing_field_raises():
    scraper = YahooFinanceScraper(StubClient({"chart": {"result": [{}]}}), base_url="https://q", config={})
    with pytest.raises(ParseError):
        await scraper._fetch_one("USD", "EUR")


@pytest.mark.asyncio
async def test_investing_reads_data_test_last():
    html = '<div data-test="instrument-price-last">0.8619</div>'
    client = StubClient(html)
    scraper = InvestingScraper(client, base_url="https://www.investing.com", config={})
    reading = await scraper._fetch_one("USD", "EUR")
    assert reading.rate == Decimal("0.8619")
    assert client.calls == ["https://www.investing.com/currencies/usd-eur"]


@pytest.mark.asyncio
async def test_marketwatch_reads_meta_price_and_strips_symbol():
    # MarketWatch renders the live price into <meta name="price"> with a currency glyph.
    html = '<meta name="priceCurrency" content="EUR" /><meta name="price" content="€0.8618" />'
    client = StubClient(html)
    scraper = MarketWatchScraper(client, base_url="https://www.marketwatch.com", config={})
    reading = await scraper._fetch_one("USD", "EUR")
    assert reading.source_slug == "marketwatch"
    assert reading.rate == Decimal("0.8618")
    assert client.calls == ["https://www.marketwatch.com/investing/currency/usdeur"]


@pytest.mark.asyncio
async def test_markets_insider_strips_currency_suffix():
    html = '<span class="price-section__current-value">0.8619 EUR</span>'
    client = StubClient(html)
    scraper = MarketsInsiderScraper(client, base_url="https://markets.businessinsider.com", config={})
    reading = await scraper._fetch_one("USD", "EUR")
    assert reading.rate == Decimal("0.8619")
    assert client.calls == ["https://markets.businessinsider.com/currencies/usd-eur"]


@pytest.mark.asyncio
async def test_ft_reads_first_value():
    html = (
        '<span class="mod-ui-data-list__value">0.8618</span>'
        '<span class="mod-ui-data-list__value">0.8602</span>'
    )
    client = StubClient(html)
    scraper = FtScraper(client, base_url="https://markets.ft.com", config={})
    reading = await scraper._fetch_one("USD", "EUR")
    assert reading.rate == Decimal("0.8618")
    assert client.calls == ["https://markets.ft.com/data/currencies/tearsheet/summary?s=USDEUR"]


@pytest.mark.asyncio
async def test_missing_markup_raises_parse_error():
    scraper = FtScraper(StubClient("<html><body>nope</body></html>"), base_url="https://markets.ft.com", config={})
    with pytest.raises(ParseError):
        await scraper._fetch_one("USD", "EUR")


def _sources() -> list[dict[str, Any]]:
    raw = resources.files("koel.data").joinpath("sources.json").read_text(encoding="utf-8")
    return json.loads(raw)


def test_new_sources_are_shelved():
    by_slug = {s["slug"]: s for s in _sources()}
    for slug in NEW_SLUGS:
        assert by_slug[slug]["is_active"] is False, f"{slug} should be shelved"


def test_existing_sources_stay_active():
    for s in _sources():
        if s["slug"] not in NEW_SLUGS:
            assert s["is_active"] is True, f"{s['slug']} should stay active"


def test_every_seeded_source_has_a_registered_scraper():
    # Guards against adding a sources.json entry but forgetting to register it.
    for s in _sources():
        assert s["slug"] in SCRAPERS, f"no scraper registered for {s['slug']}"
