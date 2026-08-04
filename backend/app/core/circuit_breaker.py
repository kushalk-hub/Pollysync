import time
import threading
import logging
from enum import Enum
from typing import Any, Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, max_failures: int = 3, window_seconds: int = 300):
        self.name = name
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_successes = 0
        self._lock = threading.RLock()

    def record_success(self):
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_successes += 1
                if self.half_open_successes >= 1:
                    logger.info(f"Circuit {self.name} closed - service recovered")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.half_open_successes = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self):
        now = time.time()
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit {self.name} reopened - trial call failed")
                self.state = CircuitState.OPEN
                self.last_failure_time = now
                self.half_open_successes = 0
            elif self.state == CircuitState.CLOSED:
                if now - self.last_failure_time > self.window_seconds:
                    self.failure_count = 1
                    self.last_failure_time = now
                else:
                    self.failure_count += 1

                if self.failure_count >= self.max_failures:
                    logger.warning(f"Circuit {self.name} opened - {self.failure_count} failures in {self.window_seconds}s")
                    self.state = CircuitState.OPEN
                    self.last_failure_time = now

    def should_allow_call(self) -> bool:
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.window_seconds:
                    logger.info(f"Circuit {self.name} half-open - allowing trial call")
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_successes = 0
                    return True
                return False

            return True  # HALF_OPEN allows one trial call


# Global circuit breakers registry
_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_breaker(name: str, max_failures: int = 3, window_seconds: int = 300) -> CircuitBreaker:
    with _registry_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name, max_failures, window_seconds)
    return _breakers[name]


def circuit_breaker(name: str, max_failures: int = 3, window_seconds: int = 300, fallback: Any = None):
    """Decorator that wraps a function with circuit breaker protection."""
    breaker = get_breaker(name, max_failures, window_seconds)
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not breaker.should_allow_call():
                logger.warning(f"Circuit {name} is OPEN - using fallback")
                if callable(fallback):
                    return fallback(*args, **kwargs)
                return fallback
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        return wrapper
    return decorator
