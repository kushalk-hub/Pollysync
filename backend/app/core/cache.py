import json
import time
import threading
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_l1_cache: dict = {}
L1_DEFAULT_TTL = 300
_L1_MAX_ENTRIES: Optional[int] = None
_lock = threading.RLock()

_redis_client = None
_redis_failed_at = 0.0
_REDIS_RETRY_SECONDS = 60


def set_max_entries(limit: Optional[int]):
    global _L1_MAX_ENTRIES
    with _lock:
        _L1_MAX_ENTRIES = limit
        _enforce_bound()


def get_cache_size() -> int:
    with _lock:
        return len(_l1_cache)


def _prune_expired():
    now = time.time()
    expired = [k for k, entry in _l1_cache.items() if entry["expires_at"] <= now]
    for k in expired:
        del _l1_cache[k]


def _enforce_bound():
    if _L1_MAX_ENTRIES is None:
        return
    while len(_l1_cache) > _L1_MAX_ENTRIES:
        oldest = min(_l1_cache.items(), key=lambda item: item[1]["expires_at"])
        del _l1_cache[oldest[0]]

def _get_redis():
    global _redis_client, _redis_failed_at
    from app.core.config import settings

    # Redis is opt-in: leave REDIS_URL empty (default) for pure L1 caching.
    if not settings.redis_url:
        return None

    if _redis_client is None:
        now = time.time()
        if now - _redis_failed_at < _REDIS_RETRY_SECONDS:
            return None
        try:
            import redis
            _redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
            _redis_failed_at = 0.0
        except Exception as e:
            _redis_failed_at = now
            logger.warning(f"Redis unavailable, L1-only mode: {e}")
            _redis_client = None
    return _redis_client


def cache_get(key: str, group: str = "default") -> Optional[Any]:
    full_key = f"{group}:{key}"
    now = time.time()

    with _lock:
        _prune_expired()

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
                with _lock:
                    _l1_cache[full_key] = {
                        "value": value,
                        "expires_at": now + L1_DEFAULT_TTL,
                    }
                    _enforce_bound()
                return value
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")

    return None


def cache_set(key: str, value: Any, ttl: int = L1_DEFAULT_TTL, group: str = "default"):
    full_key = f"{group}:{key}"
    now = time.time()

    with _lock:
        _prune_expired()
        _l1_cache[full_key] = {
            "value": value,
            "expires_at": now + ttl,
        }
        _enforce_bound()

    redis_client = _get_redis()
    if redis_client:
        try:
            redis_client.setex(full_key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")


def cache_delete_group(group: str):
    # L1 delete
    with _lock:
        _prune_expired()
        keys_to_delete = [k for k in _l1_cache if k.startswith(f"{group}:")]
        for k in keys_to_delete:
            del _l1_cache[k]

    # L2 Redis delete (non-blocking SCAN instead of KEYS to avoid stalling Redis)
    redis_client = _get_redis()
    if redis_client:
        try:
            batch = []
            for key in redis_client.scan_iter(match=f"{group}:*", count=100):
                batch.append(key)
                if len(batch) >= 500:
                    redis_client.delete(*batch)
                    batch = []
            if batch:
                redis_client.delete(*batch)
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")


def cache_clear_all():
    global _l1_cache
    with _lock:
        _l1_cache = {}

    redis_client = _get_redis()
    if redis_client:
        try:
            redis_client.flushdb()
        except Exception as e:
            logger.warning(f"Redis flushdb failed: {e}")


def cache_health() -> dict:
    """Return Redis status for health checks. Never raises.

    Returns one of: {"redis": "ok"} | {"redis": "disabled"} | {"redis": "unavailable"}.
    """
    from app.core.config import settings

    if not settings.redis_url:
        return {"redis": "disabled"}
    redis_client = _get_redis()
    if redis_client is None:
        return {"redis": "unavailable"}
    try:
        redis_client.ping()
        return {"redis": "ok"}
    except Exception as e:
        logger.warning(f"Redis health ping failed: {e}")
        return {"redis": "unavailable"}
