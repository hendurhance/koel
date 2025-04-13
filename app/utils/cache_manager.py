import json
import redis
from datetime import datetime
from decimal import Decimal
from app.core.config import config

redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    password=config.REDIS_PASSWORD,
    decode_responses=True
)

def default_converter(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

class CacheManager:
    @staticmethod
    def get(key: str):
        """Retrieve a value from Redis and convert it from JSON."""
        value = redis_client.get(key)
        if value:
            return json.loads(value)
        return None

    @staticmethod
    def set(key: str, value, expire: int = 300):
        """
        Store a value in Redis as JSON.

        :param key: The cache key.
        :param value: The value to cache (must be JSON serializable or convertible).
        :param expire: Time-to-live in seconds (default is 5 minutes).
        """
        redis_client.setex(key, expire, json.dumps(value, default=default_converter))

    @staticmethod
    def delete(key: str):
        """Remove a key from Redis."""
        redis_client.delete(key)
