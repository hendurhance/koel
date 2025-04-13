import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)

class WiseScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str):
        super().__init__(base_currency, target_currency)

        self.url = f"https://wise.com/currency-converter/{base_currency.lower()}-to-{target_currency.lower()}/chart"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "wise"
    
    def extract(self) -> str:
        try:
            logger.info(f"[{datetime.now()}] Extracting from {self.url}")
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to extract from {self.url}: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise

    def transform(self, raw_data: str) -> Dict[str, float]:
        try:
            soup = BeautifulSoup(raw_data, "html.parser")
            
            # Find the parent element that contains the exchange rate information.
            tapestry_element = soup.find("div", class_="tapestry-wrapper")

            if not tapestry_element:
                logger.error("Tapestry element not found.")
                raise ValueError("Tapestry element not found")
            
            exchange_rate_h3 = tapestry_element.find("h3", class_="cc__source-to-target")
            if not exchange_rate_h3:
                logger.error("Exchange rate element not found.")
                raise ValueError("Exchange rate element not found")

            rate_span = exchange_rate_h3.find("span", class_="text-success")
            if not rate_span:
                logger.error("Rate span element not found.")
                raise ValueError("Rate span element not found")
            
            # Extract the conversion rate from the span
            conversion_rate = rate_span.get_text(strip=True)

            return {self.target_currency: float(conversion_rate)}
        except ValueError as e:
            logger.error(f"Failed to extract conversion rate: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise
        finally:
            logger.info(f"Finished transforming data from {self.get_source_name()}")