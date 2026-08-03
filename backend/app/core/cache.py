import json
import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_l1_cache: dict = {}
L1_DEFAULT_TTL = 300  

_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            from app.core.config import settings
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable, L1-only mode: {e}")
            _redis_client = None
    return _redis_client


def cache_get(key: str, group: str = "default") -> Optional[Any]:
    full_key = f"{group}:{key}"
    now = time.time()

    # L1 check
    if full_key in _l1_cache:
        entry = _l1_cache[full_key]
        if entry["expires_at"] > now:
            return entry["value"]
        del _l1_cache[full_key]

    # L2 Redis check
    redis_client = _get_redis()
    if redis_client:
        try:
            data = redis_client.get(full_key)
            if data:
                value = json.loads(data)
                # Backfill L1
                _l1_cache[full_key] = {
                    "value": value,
                    "expires_at": now + L1_DEFAULT_TTL,
                }
                return value
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")

    return None


def cache_set(key: str, value: Any, ttl: int = L1_DEFAULT_TTL, group: str = "default"):
    full_key = f"{group}:{key}"
    now = time.time()

    _l1_cache[full_key] = {
        "value": value,
        "expires_at": now + ttl,
    }

    redis_client = _get_redis()
    if redis_client:
        try:
            redis_client.setex(full_key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")


def cache_delete_group(group: str):
    # L1 delete
    keys_to_delete = [k for k in _l1_cache if k.startswith(f"{group}:")]
    for k in keys_to_delete:
        del _l1_cache[k]

    # L2 Redis delete
    redis_client = _get_redis()
    if redis_client:
        try:
            keys = redis_client.keys(f"{group}:*")
            if keys:
                redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")


def cache_clear_all():
    global _l1_cache
    _l1_cache = {}

    redis_client = _get_redis()
    if redis_client:
        try:
            redis_client.flushdb()
        except Exception as e:
            logger.warning(f"Redis flushdb failed: {e}")
