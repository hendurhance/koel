import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
import re

from app.utils.custom_logger import get_logger

logger = get_logger(__name__)


class CurrencyConverterOrgUkScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str = None, base_name_plural: str = ""):
        super().__init__(base_currency, target_currency)
        self.base_name_plural = base_name_plural

        if not base_name_plural:
            raise ValueError(
                "base_name_plural cannot be empty for CurrencyConverterOrgUkScraper"
            )

        plural_name = base_name_plural.split()[-1].lower()
        self.url = f"https://www.currencyconverter.org.uk/convert-{base_currency}/convert-{plural_name}.html"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "currency-converter-org-uk"

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

            # Find all tables with class "currencies"
            tables = soup.find_all("table", class_="currencies")
            if not tables or len(tables) < 2:
                logger.error("Second table not found.")
                raise ValueError("Second table not found")

            # The second table (index 1) is the one we want (the "Remaining" rates)
            second_table = tables[1]

            # Get all rows from the table; assume the first row is header so skip it
            rows = second_table.find_all("tr")
            if not rows or len(rows) < 2:
                logger.error("No data rows found in the second table.")
                raise ValueError("No conversion data found in the second table")

            conversion_rates = (
                {}
            )  # dictionary to store: target currency -> conversion rate
            header_row = rows[0]  # header row; we skip it
            data_rows = rows[1:]

            # Process each data row
            # We expect rows to have at least 2 cells; the second cell holds text like
            # "1 Pound = 114.12 ALL" (with the number in a <b> tag)
            pattern = re.compile(r"1\s+\w+\s*=\s*([\d.,]+)\s*(\w+)")

            for row in data_rows:
                cols = row.find_all("td")
                if len(cols) < 2:
                    logger.warning(
                        "Row has an unexpected number of columns; skipping row."
                    )
                    continue

                # Get the full text from the second <td>
                # Using a space as a separator so that the bold text and following text are separated.
                text = cols[1].get_text(" ", strip=True)
                match = pattern.search(text)
                if not match:
                    logger.warning(f"Regex did not match for row text: {text}")
                    continue

                rate_str, target_code = match.groups()
                try:
                    rate = float(rate_str.replace(",", ""))
                except ValueError as ve:
                    logger.warning(
                        f"Failed to parse rate '{rate_str}' for {target_code}: {ve}"
                    )
                    continue

                conversion_rates[target_code] = rate

            return conversion_rates
        except Exception as e:
            logger.error(f"An unexpected error occurred during transformation: {e}")
            raise
        finally:
            logger.info(
                f"[{datetime.now()}] Finished transforming data from source: {self.get_source_name()}"
            )