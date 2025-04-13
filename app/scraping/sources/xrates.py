import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)

class XRatesScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str = None):
        super().__init__(base_currency, target_currency)
        self.url = f"https://www.x-rates.com/table/?from={base_currency}&amount=1"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "xrates"

    def extract(self) -> str:
        try:
            logger.info(f"[{datetime.now()}] Extracting from {self.url}")
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to extract from {self.url}: {e}")
            raise

    def transform(self, raw_data: str) -> Dict[str, float]:
        try:
            soup = BeautifulSoup(raw_data, "html.parser")
            table = soup.find("table", class_="tablesorter ratesTable")
            rows = table.find_all("tr") if table else []

            rates = {}

            for row in rows[1:]:  # skip table header
                cols = row.find_all("td")
                if len(cols) >= 2:
                    rate_link = cols[1].find("a")

                    if rate_link and "href" in rate_link.attrs:
                        href = rate_link["href"]
                        to_param = (
                            href.split("to=")[1].split("&")[0]
                            if "to=" in href
                            else None
                        )

                        if to_param:
                            try:
                                rate = float(rate_link.text.strip().replace(",", ""))
                                rates[to_param] = rate
                            except ValueError:
                                continue
            return rates
        except Exception as e:
            logger.error(f"Failed to transform data: {e} from source {self.url}")
            raise
        finally:
            logger.info(f"[{datetime.now()}] Transformation completed with {len(rates)} rates found from source: {self.get_source_name()}")
