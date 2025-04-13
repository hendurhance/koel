import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.custom_logger import get_logger
import re

logger = get_logger(__name__)

class XeScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str):
        super().__init__(base_currency, target_currency)

        self.url = f"https://www.xe.com/currencyconverter/convert/?Amount=1&From={base_currency}&To={target_currency}"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "xe"
    
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

            # For XE.com, locate the element that contains the conversion result.
            # Here we look for the container that has data-testid="conversion".
            conversion_container = soup.find("div", attrs={"data-testid": "conversion"})

            if not conversion_container:
                logger.error("Conversion container not found.")
                raise ValueError("Conversion container not found")
            
            result_p = conversion_container.find("p", class_="sc-708e65be-1 chuBHG")
            if not result_p:
                logger.error("Result paragraph not found.")
                raise ValueError("Result paragraph not found")
            # The conversion amount is split into two parts:
            # one part in the main text and a fractional part inside a <span class="faded-digits">.
            # We use get_text(separator="") to merge without extra spaces.
            result_text = result_p.get_text(separator="", strip=True)
            rate_match = re.search(r"([\d\.]+)", result_text)
            if not rate_match:
                logger.error("Failed to extract a numeric exchange rate from the result text.")
                raise ValueError("Failed to extract a numeric exchange rate from the result text")
            
            exchange_rate_value = rate_match.group(1)
            return {self.target_currency: float(exchange_rate_value)}
        except KeyError as e:
            logger.error(f"Failed to extract conversion rate: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise
        finally:
            logger.info(f"[{datetime.now()}] Transformation completed from source: {self.get_source_name()}")