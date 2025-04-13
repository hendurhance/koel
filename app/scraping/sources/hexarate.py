import requests
from datetime import datetime
from typing import Dict
from app.scraping.base import BaseScraper
from app.utils.user_agent_rotator import UserAgentRotator
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)

class HexaRateScraper(BaseScraper):
    def __init__(self, base_currency: str, target_currency: str):
        super().__init__(base_currency, target_currency)

        self.url = f"https://hexarate.paikama.co/api/rates/latest/{base_currency}?target={target_currency}"
        self.user_agent_rotator = UserAgentRotator()
        self.headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_source_name(self):
        return "hexarate"
    
    def extract(self) -> str:
        try:
            logger.info(f"[{datetime.now()}] Extracting from {self.url}")
            response = requests.get(self.url, headers=self.headers, timeout=10)
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
            # Extract the conversion rate from the JSON response
            conversion_rate = raw_data["data"]["mid"]
            return {self.target_currency: conversion_rate}
        except KeyError as e:
            logger.error(f"Failed to extract conversion rate: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise
        finally:
            logger.info(f"[{datetime.now()}] Transformation completed from source: {self.get_source_name()}")