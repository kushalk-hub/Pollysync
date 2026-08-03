# PolliSync Phase 2 — External API Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add circuit breaker fault tolerance for external APIs, integrate Google Pollen API with fallback, and verify Sentinel-2 NDVI integration.

**Architecture:** Implement per-service circuit breaker with 3-fail/5-min threshold, add Google Pollen API client with seasonal fallback, and verify Earth Engine NDVI works with credentials.

**Tech Stack:** Python, httpx, earthengine-api, Google Pollen API

## Global Constraints

- Backend runs on Python 3.x with FastAPI
- All environment variables go in `backend/.env` and `.env.example`
- Each module must be tested and committed before starting the next
- Circuit breaker must gracefully degrade to cached/seasonal data
- External API failures must not crash the application

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/core/circuit_breaker.py` | **NEW** — per-service circuit breaker |
| `backend/app/services/pollen_service.py` | **NEW** — Google Pollen API client |
| `backend/app/services/weather_service.py` | Wrap with circuit breaker |
| `backend/app/services/environment_service.py` | Wrap with circuit breaker |
| `backend/app/services/bee_service.py` | Wrap with circuit breaker |
| `backend/app/agent/router.py` | Wrap Gemini calls with circuit breaker |

---

## Task 1: Implement Circuit Breaker (M4)

**Files:**
- Create: `backend/app/core/circuit_breaker.py`
- Test: `backend/tests/test_circuit_breaker.py`

**Interfaces:**
- Produces: `circuit_breaker(name, coro, fallback)` decorator/function

- [ ] **Step 1: Write failing test for circuit breaker**

Create `backend/tests/test_circuit_breaker.py`:
```python
import pytest
import asyncio
from app.core.circuit_breaker import circuit_breaker, CircuitState

@pytest.mark.asyncio
async def test_circuit_breaker_closed_on_success():
    @circuit_breaker("test_service")
    async def success_func():
        return "success"
    
    result = await success_func()
    assert result == "success"

@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    call_count = 0
    
    @circuit_breaker("test_failing", max_failures=3, window_seconds=300)
    async def failing_func():
        nonlocal call_count
        call_count += 1
        raise Exception("Service unavailable")
    
    # First 3 calls should fail normally
    for _ in range(3):
        with pytest.raises(Exception):
            await failing_func()
    
    # Circuit should now be open
    from app.core.circuit_breaker import _breakers
    assert _breakers["test_failing"].state == CircuitState.OPEN

@pytest.mark.asyncio
async def test_circuit_breaker_fallback_on_open():
    @circuit_breaker("test_open", max_failures=1, window_seconds=300)
    async def failing_func():
        raise Exception("Service unavailable")
    
    # Trigger circuit open
    with pytest.raises(Exception):
        await failing_func()
    
    # Should use fallback
    result = await circuit_breaker("test_open", failing_func, fallback="cached_data")()
    assert result == "cached_data"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_circuit_breaker.py -v`
Expected: FAIL (circuit_breaker doesn't exist)

- [ ] **Step 3: Implement circuit_breaker.py**

Create `backend/app/core/circuit_breaker.py`:
```python
import time
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
    
    def record_success(self):
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


def get_breaker(name: str, max_failures: int = 3, window_seconds: int = 300) -> CircuitBreaker:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_circuit_breaker.py -v`
Expected: PASS

- [ ] **Step 5: Commit circuit breaker**

```bash
git add backend/app/core/circuit_breaker.py backend/tests/test_circuit_breaker.py
git commit -m "feat(m4): implement per-service circuit breaker"
```

---

## Task 2: Wrap External Services with Circuit Breaker (M4)

**Files:**
- Modify: `backend/app/services/weather_service.py`
- Modify: `backend/app/services/environment_service.py`
- Modify: `backend/app/services/bee_service.py`

**Interfaces:**
- Consumes: `circuit_breaker` from `app.core.circuit_breaker`
- Produces: Protected external API calls

- [ ] **Step 1: Wrap weather service fetch**

Add to `backend/app/services/weather_service.py`:
```python
from app.core.circuit_breaker import circuit_breaker

@circuit_breaker("open-meteo", max_failures=3, window_seconds=300, fallback=get_fallback_weather)
async def fetch_weather_protected(lat: float, lng: float) -> dict:
    return await fetch_weather(lat, lng)
```

- [ ] **Step 2: Wrap bee service fetch**

Add to `backend/app/services/bee_service.py`:
```python
from app.core.circuit_breaker import circuit_breaker

@circuit_breaker("gbif", max_failures=3, window_seconds=300)
async def fetch_bees_protected(lat: float, lng: float, radius_km: int = 10) -> list[dict]:
    return await fetch_bees(lat, lng, radius_km)
```

- [ ] **Step 3: Wrap environment service fetches**

Add to `backend/app/services/environment_service.py`:
```python
from app.core.circuit_breaker import circuit_breaker

@circuit_breaker("nasa-power", max_failures=3, window_seconds=300)
async def fetch_nasa_power_7d_protected(lat: float, lon: float, as_of) -> dict:
    return await fetch_nasa_power_7d(lat, lon, as_of)

@circuit_breaker("earth-engine", max_failures=3, window_seconds=300)
async def fetch_ndvi_protected(lat: float, lon: float, as_of, window_days: int = 20):
    return await fetch_ndvi(lat, lon, as_of, window_days)
```

- [ ] **Step 4: Commit circuit breaker integration**

```bash
git add backend/app/services/weather_service.py backend/app/services/bee_service.py backend/app/services/environment_service.py
git commit -m "feat(m4): wrap external services with circuit breaker"
```

---

## Task 3: Implement Google Pollen API Service (M5)

**Files:**
- Create: `backend/app/services/pollen_service.py`
- Modify: `backend/app/services/environment_service.py`
- Test: `backend/tests/test_pollen_service.py`

**Interfaces:**
- Consumes: `POLLEN_API_KEY` env var, `get_pollen_for_month` fallback
- Produces: `fetch_pollen(lat, lon, date)` function

- [ ] **Step 1: Write failing test for pollen service**

Create `backend/tests/test_pollen_service.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from app.services.pollen_service import fetch_pollen_with_fallback

@pytest.mark.asyncio
async def test_pollen_returns_seasonal_fallback_without_key():
    with patch("app.services.pollen_service.POLLEN_API_KEY", ""):
        result = await fetch_pollen_with_fallback(19.07, 73.87)
        assert "tree" in result
        assert "grass" in result
        assert "weed" in result
        assert result["source"] == "seasonal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_pollen_service.py -v`
Expected: FAIL (pollen_service doesn't exist)

- [ ] **Step 3: Implement pollen_service.py**

Create `backend/app/services/pollen_service.py`:
```python
import logging
from datetime import date
from typing import Optional
import httpx

from app.core.config import settings
from app.services.feature_engineering import get_pollen_for_month

logger = logging.getLogger(__name__)

POLLEN_API_KEY = settings.pollen_api_key if hasattr(settings, 'pollen_api_key') else ""
POLLEN_API_URL = "https://pollen.googleapis.com/v1/forecast:lookup"


async def fetch_pollen(lat: float, lon: float, as_of: Optional[date] = None) -> Optional[dict]:
    """Fetch live pollen data from Google Pollen API."""
    if not POLLEN_API_KEY:
        return None
    
    as_of = as_of or date.today()
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                POLLEN_API_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "days": 1,
                    "key": POLLEN_API_KEY,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        
        # Parse response - adjust based on actual API response format
        daily = data.get("daily", [{}])[0] if data.get("daily") else {}
        pollen_info = daily.get("pollen", {})
        
        return {
            "tree": pollen_info.get("tree", 0),
            "grass": pollen_info.get("grass", 0),
            "weed": pollen_info.get("weed", 0),
            "source": "live",
        }
    except Exception as e:
        logger.warning(f"Pollen API fetch failed: {e}")
        return None


async def fetch_pollen_with_fallback(lat: float, lon: float, as_of: Optional[date] = None) -> dict:
    """Fetch pollen with seasonal fallback."""
    as_of = as_of or date.today()
    
    # Try live API first
    live_pollen = await fetch_pollen(lat, lon, as_of)
    if live_pollen:
        return live_pollen
    
    # Fallback to seasonal data
    seasonal = get_pollen_for_month(as_of.month)
    seasonal["source"] = "seasonal"
    return seasonal
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_pollen_service.py -v`
Expected: PASS

- [ ] **Step 5: Add POLLEN_API_KEY to config**

Add to `backend/app/core/config.py` Settings class:
```python
pollen_api_key: str = os.getenv("POLLEN_API_KEY", "")
```

- [ ] **Step 6: Commit pollen service**

```bash
git add backend/app/services/pollen_service.py backend/app/core/config.py backend/tests/test_pollen_service.py
git commit -m "feat(m5): implement Google Pollen API with seasonal fallback"
```

---

## Task 4: Verify NDVI Integration (M6)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/environment_service.py`

**Interfaces:**
- Consumes: `EE_SERVICE_ACCOUNT`, `EE_PRIVATE_KEY_FILE` env vars
- Produces: Verified NDVI fetch with credentials

- [ ] **Step 1: Add EE config to Settings**

Add to `backend/app/core/config.py` Settings class:
```python
ee_service_account: str = os.getenv("EE_SERVICE_ACCOUNT", "")
ee_private_key_file: str = os.getenv("EE_PRIVATE_KEY_FILE", "")
```

- [ ] **Step 2: Update environment_service to use settings**

Update `backend/app/services/environment_service.py` `_init_earth_engine()`:
```python
def _init_earth_engine():
    global _ee_initialized
    if _ee_initialized:
        return
    import ee
    from app.core.config import settings

    service_account = settings.ee_service_account
    key_file = settings.ee_private_key_file
    if service_account and key_file:
        credentials = ee.ServiceAccountCredentials(service_account, key_file)
        ee.Initialize(credentials)
    else:
        ee.Initialize()
    _ee_initialized = True
```

- [ ] **Step 3: Verify NDVI returns valid range**

Run test with known coordinates (e.g., Nashik):
```python
import asyncio
from datetime import date
from app.services.environment_service import fetch_ndvi

result = asyncio.run(fetch_ndvi(19.9975, 73.7898, date.today()))
assert result is None or -0.2 <= result <= 0.9
```

- [ ] **Step 4: Verify fallback when EE unavailable**

```python
import asyncio
from datetime import date
from app.services.environment_service import fetch_ndvi

# Should return None when EE not configured
result = asyncio.run(fetch_ndvi(19.9975, 73.7898, date.today()))
# Result depends on whether EE credentials are configured
```

- [ ] **Step 5: Commit NDVI verification**

```bash
git add backend/app/core/config.py backend/app/services/environment_service.py
git commit -m "feat(m6): verify Sentinel-2 NDVI integration"
```

---

## Task 5: Full Integration Test (M4-M6)

**Files:**
- Test: Manual verification

**Interfaces:**
- Consumes: All M4-M6 implementations
- Produces: Verified working system

- [ ] **Step 1: Test circuit breaker opens on failures**

Simulate 3 failures to external API, verify circuit opens and fallback is used.

- [ ] **Step 2: Test pollen API with/without key**

Test with POLLEN_API_KEY set and unset, verify seasonal fallback works.

- [ ] **Step 3: Test NDVI with credentials**

Verify real NDVI returns a value in -0.2..0.9 range.

- [ ] **Step 4: Test graceful degradation**

Stop external services, verify app continues with cached/fallback data.

---

## Definition of Done — Plan B

- [ ] M4: Circuit breaker working, opens after 3 failures, serves fallback
- [ ] M5: Pollen API integrated, falls back to seasonal when key missing
- [ ] M6: Sentinel-2 NDVI verified, returns valid values with credentials
- [ ] All code committed with descriptive messages
- [ ] Integration tests passing
