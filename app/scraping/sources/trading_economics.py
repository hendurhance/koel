import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)


class TradingEconomicsScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str = None):
        super().__init__(base_currency, target_currency)

        self.url = f"https://tradingeconomics.com/currencies?base={base_currency}"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "trading-economics"
    
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
            table = soup.find("table", class_="table-heatmap")

            if not table:
                logger.error("Could not find the table containing the exchange rates.")
                raise ValueError("Table not found")
            
            # Get all rows from the tbody
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else []

            rates = {}

            for row in rows:
                # Use the data-symbol attribute from the <tr> (e.g., "GBPUSD:CUR")
                symbol_attr = row.get("data-symbol")
                if not symbol_attr:
                    continue

                # Split out the pair from the data-symbol attribute
                pair = symbol_attr.split(":")[0]  # e.g., "GBPUSD"
                # If the pair starts with our base_currency, remove it to get the target currency code.
                if pair.startswith(self.base_currency):
                    target_currency = pair[len(self.base_currency):]
                else:
                    target_currency = pair

                # Get all the cells in the row
                cols = row.find_all("td")
                if len(cols) >= 2:
                    # In this table the current exchange rate is in the second column
                    rate_text = cols[1].text.strip()
                    try:
                        rate = float(rate_text.replace(",", ""))
                        rates[target_currency] = rate
                    except ValueError as ve:
                        logger.warning(f"Failed to parse rate '{rate_text}' for {target_currency}: {ve}")
                        continue
            return rates
        except Exception as e:
            logger.error(f"Failed to transform data: {e} from source {self.url}")
            raise
        finally:
            logger.info(f"[{datetime.now()}] Transformation completed with {len(rates)} rates found from source: {self.get_source_name()}")