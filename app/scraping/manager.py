import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.scraping.factory import SCRAPER_SOURCES, ScraperSourceName, ScraperCapability
from app.exceptions import ScrapingException
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)

class ScraperManager:
    """
    A manager class for handling scraper instances and implementing failsafe scraping.
    """

    def __init__(self, source_priority: List[str] = None, rate_limit_delay: float = 1.2):
        """
        Initialize the scraper manager.
        
        Args:
            source_priority: Ordered list of source names to try, in priority order
            rate_limit_delay: Delay in seconds between requests to respect rate limits (default: 1.2 seconds)
        """
        self.sources = SCRAPER_SOURCES
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0  # Track when the last request was made

        self.source_priority = source_priority or [
            ScraperSourceName.TRADING_ECONOMICS,
            ScraperSourceName.EXCHANGE_RATES_ORG_UK,
            ScraperSourceName.CURRENCY_CONVERTER_ORG_UK,
            ScraperSourceName.X_RATES,
            ScraperSourceName.FORBES,
            ScraperSourceName.HEXA_RATE,
            ScraperSourceName.FX_EMPIRE,
            ScraperSourceName.OANDA,
            ScraperSourceName.WISE,
            ScraperSourceName.XE,
        ]
        
    def _apply_rate_limit(self):
        """
        Apply rate limiting by waiting if necessary to maintain the desired request rate.
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.rate_limit_delay and self.last_request_time > 0:
            wait_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: Waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)
            
        self.last_request_time = time.time()

    def scrape_with_failsafe(
        self, 
        base_currency: str, 
        target_currencies: List[str] = None,
        base_name: Optional[str] = None, 
        base_name_plural: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Attempt to scrape from sources in priority order with failsafe mechanism.
        
        Args:
            base_currency: The base currency code (e.g. 'USD')
            target_currencies: List of target currencies for single-pair scrapers (default: None)
            base_name: The full name of the base currency (e.g. 'US Dollar')
            base_name_plural: The plural name of the base currency (e.g. 'US Dollars')
            
        Returns:
            Dict containing:
                - rates: Dictionary of target currency codes to rates
                - source: Name of the source used
                - timestamp: Time when scraping was performed
                
        Raises:
            ScrapingException: If all sources fail
        """
        errors = []

        # First try MULTI_PAIR scrapers
        for source_name in self.source_priority:
            if source_name not in self.sources:
                logger.warning(f"Source {source_name} not found in configured sources")
                continue

            source = self.sources[source_name]
            
            # Skip SINGLE_PAIR scrapers for the first pass
            if source.capability == ScraperCapability.SINGLE_PAIR:
                continue

            # Skip sources that need special parameters if we don't have them
            if (source.needs_base_name and not base_name) or (source.needs_base_plural and not base_name_plural):
                logger.warning(f"Skipping source {source_name} due to missing required parameters")
                continue

            try:
                # Apply rate limiting before each request
                self._apply_rate_limit()
                
                # Initialize the scraper with appropriate parameters
                scraper_params = {
                    "base_currency": base_currency,
                }

                if source.needs_base_name:
                    scraper_params["base_name"] = base_name
                if source.needs_base_plural:
                    scraper_params["base_name_plural"] = base_name_plural

                scraper_cls = source.scraper_cls(**scraper_params)
                raw_data = scraper_cls.extract()
                rates = scraper_cls.transform(raw_data)
                
                # Check if rates dictionary is empty, which indicates failure
                if not rates:
                    error_msg = f"Source {source_name} returned empty rates, considering as failure"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue

                return {
                    "rates": rates,
                    "source": source_name,
                    "timestamp": datetime.now(),
                }
            except Exception as e:
                error_msg = f"Failed to scrape from {source_name}: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                
        # If all MULTI_PAIR scrapers failed, try SINGLE_PAIR scrapers if target_currencies is provided
        if target_currencies:
            for source_name in self.source_priority:
                if source_name not in self.sources:
                    continue
                    
                source = self.sources[source_name]
                
                # Skip non-SINGLE_PAIR scrapers
                if source.capability != ScraperCapability.SINGLE_PAIR:
                    continue
                    
                # Skip sources that need special parameters if we don't have them
                if (source.needs_base_name and not base_name) or (source.needs_base_plural and not base_name_plural):
                    logger.warning(f"Skipping source {source_name} due to missing required parameters")
                    continue
                    
                try:
                    rates = {}
                    scrape_failed = False
                    
                    for target_currency in target_currencies:
                        # Apply rate limiting before each request
                        self._apply_rate_limit()
                        
                        # Initialize the scraper with appropriate parameters
                        scraper_params = {
                            "base_currency": base_currency,
                            "target_currency": target_currency
                        }
                        
                        if source.needs_base_name:
                            scraper_params["base_name"] = base_name
                        if source.needs_base_plural:
                            scraper_params["base_name_plural"] = base_name_plural
                            
                        scraper_cls = source.scraper_cls(**scraper_params)
                        raw_data = scraper_cls.extract()
                        result = scraper_cls.transform(raw_data)
                        
                        # SINGLE_PAIR scraper result should contain the target currency rate
                        if target_currency in result:
                            rates[target_currency] = result[target_currency]
                        else:
                            scrape_failed = True
                            logger.warning(f"Source {source_name} failed to return rate for {target_currency}")
                    
                    # If we got at least one rate and no failures, return the result
                    if rates and not scrape_failed:
                        return {
                            "rates": rates,
                            "source": source_name,
                            "timestamp": datetime.now(),
                        }
                    elif not rates:
                        error_msg = f"Source {source_name} returned empty rates for all target currencies"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                    else:
                        error_msg = f"Source {source_name} failed to return rates for some target currencies"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"Failed to scrape from {source_name}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

        # If we get here, all sources failed
        error_details = "\n".join(errors)
        raise ScrapingException(f"All sources failed for base currency {base_currency}. Details:\n{error_details}")