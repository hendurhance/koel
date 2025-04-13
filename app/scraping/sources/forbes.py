import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.custom_logger import get_logger
import re

logger = get_logger(__name__)


class ForbesScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str):
        super().__init__(base_currency, target_currency)

        if not target_currency:
            raise ValueError("target_currency cannot be empty for ForbesScraper")

        self.url = f"https://www.forbes.com/advisor/money-transfer/currency-converter/{base_currency.lower()}-{target_currency.lower()}/?amount=1"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "forbes"

    def extract(self) -> str:
        try:
            logger.info(f"[{datetime.now()}] Extracting from {self.url}")
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to extract from {self.url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to extract from {self.url}: {e}")
            raise

    def transform(self, raw_data) -> Dict[str, float]:
        try:
            soup = BeautifulSoup(raw_data, "html.parser")

            result_box = soup.find("div", class_="result-box")
            if not result_box:
                logger.error("Result box not found.")
                raise ValueError("Result box not found")

            # Within the result box, find the div that contains the conversion rows.
            # We rely on the "result-box-c1-c2" container.
            conversion_container = result_box.find("div", class_="result-box-c1-c2")
            if not conversion_container:
                logger.error(
                    "Conversion details container not found in the result box."
                )
                raise ValueError("Conversion details container not found")

            # Use the first row which should have the conversion from base_currency to target_currency.
            conversion_row = conversion_container.find("div")
            if not conversion_row:
                logger.error("No conversion row found in the conversion container.")
                raise ValueError("Conversion row not found")

            conversion_text = conversion_row.get_text(separator=" ", strip=True)

            pattern = re.compile(
                rf"1\s*{re.escape(self.base_currency)}\s*=\s*([\d,\.]+)\s*{re.escape(self.target_currency)}",
                re.IGNORECASE,
            )

            match = pattern.search(conversion_text)
            if not match:
                logger.error("Conversion rate not found in the conversion text.")
                raise ValueError("Conversion rate not found")

            try:
                conversion_rate = float(match.group(1).replace(",", ""))
            except ValueError as ve:
                logger.error(f"Failed to convert extracted rate to float: {ve}")
                raise
            return {self.target_currency: conversion_rate}
        except Exception as e:
            logger.error(f"An unexpected error occurred during transformation: {e}")
            raise
        finally:
            logger.info(
                f"[{datetime.now()}] Transformation completed with {self.target_currency} rate found from source: {self.get_source_name()}"
            )
