from __future__ import annotations

from koel.scraping.base import Scraper
from koel.scraping.sources.exchange_rates_org import ExchangeRatesOrgScraper
from koel.scraping.sources.floatrates import FloatRatesScraper
from koel.scraping.sources.forbes import ForbesScraper
from koel.scraping.sources.ft import FtScraper
from koel.scraping.sources.fx_empire import FxEmpireScraper
from koel.scraping.sources.hexarate import HexarateScraper
from koel.scraping.sources.investing import InvestingScraper
from koel.scraping.sources.markets_insider import MarketsInsiderScraper
from koel.scraping.sources.marketwatch import MarketWatchScraper
from koel.scraping.sources.oanda import OandaScraper
from koel.scraping.sources.trading_economics import TradingEconomicsScraper
from koel.scraping.sources.wise import WiseScraper
from koel.scraping.sources.xe import XeScraper
from koel.scraping.sources.xrates import XratesScraper
from koel.scraping.sources.yahoo_finance import YahooFinanceScraper

SCRAPERS: dict[str, type[Scraper]] = {
    ExchangeRatesOrgScraper.slug: ExchangeRatesOrgScraper,
    FloatRatesScraper.slug: FloatRatesScraper,
    ForbesScraper.slug: ForbesScraper,
    FtScraper.slug: FtScraper,
    FxEmpireScraper.slug: FxEmpireScraper,
    HexarateScraper.slug: HexarateScraper,
    InvestingScraper.slug: InvestingScraper,
    MarketsInsiderScraper.slug: MarketsInsiderScraper,
    MarketWatchScraper.slug: MarketWatchScraper,
    OandaScraper.slug: OandaScraper,
    TradingEconomicsScraper.slug: TradingEconomicsScraper,
    WiseScraper.slug: WiseScraper,
    XeScraper.slug: XeScraper,
    XratesScraper.slug: XratesScraper,
    YahooFinanceScraper.slug: YahooFinanceScraper,
}


def get_scraper_cls(slug: str) -> type[Scraper]:
    try:
        return SCRAPERS[slug]
    except KeyError as exc:
        raise KeyError(f"no scraper registered for slug {slug!r}") from exc
