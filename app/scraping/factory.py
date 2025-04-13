from enum import Enum
from app.scraping.sources.trading_economics import TradingEconomicsScraper
from app.scraping.sources.xrates import XRatesScraper
from app.scraping.sources.exchange_rates_org import ExchangeRatesOrgUkScraper
from app.scraping.sources.currency_converter import CurrencyConverterOrgUkScraper
from app.scraping.sources.forbes import ForbesScraper
from app.scraping.sources.hexarate import HexaRateScraper
from app.scraping.sources.fx_empire import FxEmpireScraper
from app.scraping.sources.oanda import OandaScraper
from app.scraping.sources.wise import WiseScraper
from app.scraping.sources.xe import XeScraper

class ScraperCapability(Enum):
    SINGLE_PAIR = "single"
    MULTI_PAIR = "multi"


class ScraperSourceName(str, Enum):
    TRADING_ECONOMICS = "trading-economics"
    EXCHANGE_RATES_ORG_UK = "exchange-rates-org-uk"
    CURRENCY_CONVERTER_ORG_UK = "currency-converter-org-uk"
    X_RATES = "x-rates"
    FORBES = "forbes"
    HEXA_RATE = "hexa-rate"
    FX_EMPIRE = "fx-empire"
    OANDA = "oanda"
    WISE = "wise"
    XE = "xe"


class ScraperSource:
    def __init__(
        self,
        name: ScraperSourceName,
        scraper_cls: type,
        capability: ScraperCapability,
        needs_base_name: bool = False,
        needs_base_plural: bool = False,
    ):
        self.name = name
        self.scraper_cls = scraper_cls
        self.capability = capability
        self.needs_base_name = needs_base_name
        self.needs_base_plural = needs_base_plural


SCRAPER_SOURCES = {
    source.name: source
    for source in [
        ScraperSource(
            ScraperSourceName.TRADING_ECONOMICS,
            TradingEconomicsScraper,
            ScraperCapability.MULTI_PAIR,
        ),
        ScraperSource(
            ScraperSourceName.EXCHANGE_RATES_ORG_UK,
            ExchangeRatesOrgUkScraper,
            ScraperCapability.MULTI_PAIR,
            needs_base_name=True,
        ),
        ScraperSource(
            ScraperSourceName.CURRENCY_CONVERTER_ORG_UK,
            CurrencyConverterOrgUkScraper,
            ScraperCapability.MULTI_PAIR,
            needs_base_plural=True,
        ),
        ScraperSource(
            ScraperSourceName.X_RATES, XRatesScraper, ScraperCapability.MULTI_PAIR
        ),
        ScraperSource(
            ScraperSourceName.FORBES, ForbesScraper, ScraperCapability.SINGLE_PAIR
        ),
        ScraperSource(
            ScraperSourceName.HEXA_RATE,
            HexaRateScraper,
            ScraperCapability.SINGLE_PAIR,
        ),
        ScraperSource(
            ScraperSourceName.FX_EMPIRE,
            FxEmpireScraper,
            ScraperCapability.SINGLE_PAIR,
        ),
        ScraperSource(
            ScraperSourceName.OANDA,
            OandaScraper,
            ScraperCapability.SINGLE_PAIR,
        ),
        ScraperSource(
            ScraperSourceName.WISE,
            WiseScraper,
            ScraperCapability.SINGLE_PAIR,
        ),
        ScraperSource(
            ScraperSourceName.XE,
            XeScraper,
            ScraperCapability.SINGLE_PAIR,
        ),
    ]
}
