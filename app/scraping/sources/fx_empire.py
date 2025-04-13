import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.custom_logger import get_logger
import json

logger = get_logger(__name__)


class FxEmpireScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str):
        super().__init__(base_currency, target_currency)

        if not target_currency:
            raise ValueError("target_currency cannot be empty for FxEmpireScraper")

        self.url = f"https://www.fxempire.com/currencies/{base_currency.lower()}-{target_currency.lower()}"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self) -> str:
        return "fx_empire"

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
            instrument_key = f"{self.base_currency.lower()}-{self.target_currency.lower()}"
            soup = BeautifulSoup(raw_data, "html.parser")

            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if next_data_script is None:
                logger.error("Could not find the __NEXT_DATA__ script in the HTML.")
                raise ValueError("Missing __NEXT_DATA__ script.")
            
            json_data = json.loads(next_data_script.string)
            conversion_rate = None
            queries = json_data["props"]["pageProps"]["dehydratedState"]["queries"]
            for query in queries:
                state_data = query.get("state", {}).get("data", {})
                # Check for successful response
                if state_data.get("statusCode") == 200:
                    data_field = state_data.get("data", {})
                    prices = data_field.get("prices", {})
                    # Look for our instrument key, e.g. "all-aed"
                    if instrument_key in prices:
                        conversion_rate = prices[instrument_key].get("last")
                        break
            if conversion_rate is None:
                logger.error(f"Conversion rate for {instrument_key} not found.")
                raise ValueError(f"Conversion rate for {instrument_key} not found.")
            
            return {self.target_currency: conversion_rate}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON data: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to transform data: {e}")
            raise
        finally:
            logger.info(f"[{datetime.now()}] Transformation completed from source: {self.get_source_name()}")
