from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from koel.scraping.exceptions import ParseError
from koel.scraping.sources.hexarate import HexarateScraper
from koel.scraping.types import RateReading


@dataclass
class StubClient:
    response: Any
    calls: list[str]

    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls = []

    async def get_json(self, url: str, *, impersonate: str | None = None) -> tuple[Any, int]:
        self.calls.append(url)
        return self.response, 42


CONFIG = {
    "path_template": "/api/rates/latest/{base}?target={target}",
    "impersonate": "chrome124",
    "response_type": "json",
    "json_path": "data.mid",
}


@pytest.mark.asyncio
async def test_fetch_happy_path():
    client = StubClient(response={"data": {"mid": 0.9123}})
    scraper = HexarateScraper(client, base_url="https://hexarate.example.co", config=CONFIG)

    reading = await scraper._fetch_one("USD", "EUR")

    assert isinstance(reading, RateReading)
    assert reading.source_slug == "hexarate"
    assert reading.base == "USD"
    assert reading.target == "EUR"
    assert reading.rate == Decimal("0.9123")
    assert reading.latency_ms == 42
    assert client.calls == ["https://hexarate.example.co/api/rates/latest/USD?target=EUR"]


@pytest.mark.asyncio
async def test_fetch_missing_path_raises_parse_error():
    client = StubClient(response={"data": {}})
    scraper = HexarateScraper(client, base_url="https://hexarate.example.co", config=CONFIG)

    with pytest.raises(ParseError):
        await scraper._fetch_one("USD", "EUR")


@pytest.mark.asyncio
async def test_fetch_strips_trailing_slash_from_base_url():
    client = StubClient(response={"data": {"mid": 1.0}})
    scraper = HexarateScraper(client, base_url="https://hexarate.example.co/", config=CONFIG)

    await scraper._fetch_one("USD", "EUR")
    assert client.calls[0] == "https://hexarate.example.co/api/rates/latest/USD?target=EUR"


@pytest.mark.asyncio
async def test_custom_json_path():
    client = StubClient(response={"quote": {"price": "1.2345"}})
    config = {**CONFIG, "json_path": "quote.price"}
    scraper = HexarateScraper(client, base_url="https://hexarate.example.co", config=config)

    reading = await scraper._fetch_one("USD", "EUR")
    assert reading.rate == Decimal("1.2345")
