import requests
from datetime import datetime, timedelta
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)


class OandaScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str):
        super().__init__(base_currency, target_currency)

        self.url = f"https://fxds-public-exchange-rates-api.oanda.com/cc-api/currencies"
        self.params = {
            "base": base_currency,
            "quote": target_currency,
            "data_type": "chart",
            "start_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d"),
        }
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "oanda"

    def extract(self) -> str:
        try:
            logger.info(f"[{datetime.now()}] Extracting from {self.url}")
            response = requests.get(
                self.url, params=self.params, headers=self.headers, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to extract from {self.url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to extract from {self.url}: {e}")
            raise

    def transform(self, raw_data) -> Dict[str, float]:
        try:
            responses = raw_data.get("responses", [])
            if not responses:
                logger.error("No responses found in the data.")
                raise ValueError("No responses found")

            # Initialize a variable to store the last mid value
            result = None

            for entry in responses:
                average_bid = float(entry.get("average_bid"))
                average_ask = float(entry.get("average_ask"))

                mid = (average_bid + average_ask) / 2
                result = {self.target_currency: mid}

            # Return the last processed entry
            return result
        except KeyError as e:
            logger.error(f"Failed to extract conversion rate: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise
        finally:
            logger.info(
                f"[{datetime.now()}] Transformation completed from source: {self.get_source_name()}"
            )