import json
import redis
from datetime import datetime
from decimal import Decimal
from app.core.config import config
from app.utils.custom_logger import get_logger

logger = get_logger(__name__)

try:
    redis_client = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        password=config.REDIS_PASSWORD if config.REDIS_PASSWORD else None,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    redis_client.ping()
    logger.info("Redis connection established successfully")
except redis.RedisError as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

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
        if not redis_client:
            logger.warning("Redis client not available, skipping cache get")
            return None
        
        try:
            value = redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    @staticmethod
    def set(key: str, value, expire: int = 300):
        """
        Store a value in Redis as JSON.

        :param key: The cache key.
        :param value: The value to cache (must be JSON serializable or convertible).
        :param expire: Time-to-live in seconds (default is 5 minutes).
        """
        if not redis_client:
            logger.warning("Redis client not available, skipping cache set")
            return
        
        try:
            redis_client.setex(key, expire, json.dumps(value, default=default_converter))
        except (redis.RedisError, TypeError) as e:
            logger.error(f"Cache set error for key {key}: {e}")

    @staticmethod
    def delete(key: str):
        """Remove a key from Redis."""
        if not redis_client:
            logger.warning("Redis client not available, skipping cache delete")
            return
        
        try:
            redis_client.delete(key)
        except redis.RedisError as e:
            logger.error(f"Cache delete error for key {key}: {e}")
