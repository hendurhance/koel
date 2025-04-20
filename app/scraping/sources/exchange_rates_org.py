import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.helpers import extract_target_code
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)


class ExchangeRatesOrgUkScraper(BaseScraper):
    def __init__(
       self, base_currency: str, target_currency: str = None, base_name: str = ""):
        super().__init__(base_currency, target_currency)
        self.base_name = base_name

        if not base_name:
            raise ValueError("base_name cannot be empty for ExchangeRatesOrgUkScraper")

        formatted_base_name = "-".join(word.capitalize() for word in base_name.split())
        self.url = f"https://www.exchangerates.org.uk/{formatted_base_name}-{base_currency}-currency-table.html"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "exchange-rates-org-uk"

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

    def transform(self, raw_data) -> Dict[str, float]:
        try:
            soup = BeautifulSoup(raw_data, "html.parser")

            # Find all divs with class "mobilescrollbars"
            mobilescroll_divs = soup.find_all("div", class_="mobilescrollbars")
            if not mobilescroll_divs:
                logger.error("No divs with class 'mobilescrollbars' found.")
                raise ValueError("mobilescrollbars div not found")

            conversion_rates = {}
            # Loop through all mobilescrollbars divs
            for div in mobilescroll_divs:
                table = div.find("table", class_="currencypage-mini")
                if not table:
                    continue

                # Instead of relying on tbody, directly gather rows that carry conversion info.
                # The conversion rows have class "colone" or "coltwo".
                rows = table.find_all(
                    "tr", class_=lambda cls: cls in ("colone", "coltwo")
                )
                if not rows:
                    continue

                # Process each conversion row
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 5:
                        logger.warning(
                            "Row has an unexpected number of columns; skipping row."
                        )
                        continue

                    # We assume here that:
                    # - Column 3 (index 2 or 3 depending on the structure) holds the target currency link.
                    # - Column 4 (index 4) contains the conversion rate (in a <b> tag).
                    #
                    # In our sample HTML these rows follow this order:
                    #    col0: Flag for AED, col1: Text ("United Arab Emirates Dirham")
                    #    col2: Flag for target currency,
                    #    col3: <a> tag with target currency name; its href helps extract the ISO code,
                    #    col4: <b> tag with AED -> target conversion rate.
                    a_tag = cols[3].find("a")
                    if not a_tag:
                        logger.warning(
                            "No anchor tag found in expected column; skipping row."
                        )
                        continue

                    href = a_tag.get("href", "")
                    target_code = extract_target_code(href)
                    if not target_code:
                        # Fall back on the link text if extraction fails.
                        target_code = a_tag.text.strip().upper()
                        logger.warning(
                            f"Could not extract target ISO code from URL '{href}', using link text: {target_code}"
                        )

                    rate_text = cols[4].get_text(strip=True)
                    try:
                        rate_value = float(rate_text.replace(",", ""))
                    except ValueError as ve:
                        logger.warning(
                            f"Failed to parse rate '{rate_text}' for {target_code}: {ve}"
                        )
                        continue

                    conversion_rates[target_code] = rate_value
            return conversion_rates
        except Exception as e:
            logger.error(f"An unexpected error occurred during transformation: {e}")
            raise
        finally:
            logger.info(
                f"[{datetime.now()}] Finished transforming data from {self.url} with {len(conversion_rates)} rates found from source: {self.get_source_name()}"
            )
