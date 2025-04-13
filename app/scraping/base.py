from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseScraper(ABC):
    """
    Abstract base class defining the ETL pattern.
    """

    def __init__(self, base_currency: str, target_currency: str = None):
        """
        Initialize the scraper with a base currency code and optional base currency name.

        Args:
            base_currency: The currency code to convert from (e.g., 'USD')
            target_currency: The currency code to convert to (e.g., 'EUR'). This is used only in SINGLE_PAIR sources.
        """
        self.base_currency = base_currency
        self.target_currency = target_currency

    @abstractmethod
    def extract(self) -> str:
        """
        Extract raw HTML or data from source.
        """
        pass

    @abstractmethod
    def transform(self, raw_data: Any) -> Dict[str, float]:
        """
        Parse the raw data into { target_currency_code: rate }.
        The rate is the amount of 1 base_currency in each target_currency.
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """
        Return the name of the source (e.g., 'xrates').
        """
        pass

    def scrape(self) -> Dict[str, float]:
        """
        The full ETL process.
        """
        raw = self.extract()
        return self.transform(raw)
