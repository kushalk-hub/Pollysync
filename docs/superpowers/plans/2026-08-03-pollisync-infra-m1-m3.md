# PolliSync Phase 2 — Infrastructure Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish Postgres database, two-level caching (L1 memory + L2 Redis), and background data refresh scheduler as the foundation for Phase 2.

**Architecture:** Migrate from SQLite to Supabase Postgres, add Redis-backed caching layer with in-memory L1 fallback, and deploy Celery Beat worker for 30-minute data refresh cycles.

**Tech Stack:** PostgreSQL (Supabase), Redis, SQLAlchemy, Celery, psycopg2-binary, redis-py

## Global Constraints

- Backend runs on Python 3.x with FastAPI
- All environment variables go in `backend/.env` and `.env.example`
- Each module must be tested and committed before starting the next
- Graceful degradation: if Redis unavailable, serve from L1/DB with warning
- Do NOT rebuild existing Supabase scaffolding — verify and configure only

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/core/config.py` | Add `REDIS_URL`, `SUPABASE_*` settings |
| `backend/app/core/cache.py` | **NEW** — L1/L2 cache implementation |
| `backend/app/celery_app.py` | **NEW** — Celery app + beat schedule |
| `backend/app/tasks/data_refresh.py` | **NEW** — batch refresh tasks |
| `backend/app/services/weather_service.py` | Wrap with cache layer |
| `backend/app/services/bee_service.py` | Wrap with cache layer |
| `backend/app/services/environment_service.py` | Wrap with cache layer |
| `backend/requirements.txt` | Add redis, celery[redis] |
| `backend/.env.example` | Document all new env vars |

---

## Task 1: Verify Supabase Postgres Connection (M1)

**Files:**
- Modify: `backend/.env`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_database.py`

**Interfaces:**
- Consumes: Existing `DATABASE_URL` env var
- Produces: Verified Postgres connection, all tables created

- [ ] **Step 1: Add Supabase connection string**

Add to `backend/.env`:
```
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_ANON_KEY=[anon-key]
SUPABASE_SERVICE_KEY=[service-key]
```

- [ ] **Step 2: Update .env.example with comments**

Add to `backend/.env.example`:
```env
# Supabase Postgres (use pooler URL with ?sslmode=require)
DATABASE_URL=postgresql://...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
```

- [ ] **Step 3: Run existing tests against Postgres**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest -v`
Expected: Identify any SQLite-specific test failures

- [ ] **Step 4: Fix SQLite-specific test failures**

Common fixes:
- `DATETIME` columns → use `TIMESTAMP` or handle timezone
- `JSON` → use `JSONB` for Postgres
- Boolean `""` → use `NULL` or `false`
- Geography empty strings → use `NULL`

- [ ] **Step 5: Verify init_db() seeds districts**

Run: `cd backend && ..\.venv\Scripts\python.exe -c "from app.database import init_db; init_db()"`
Expected: `districts` table populated with Maharashtra districts

- [ ] **Step 6: Run SQLite → Supabase migration**

Run: `cd backend && ..\.venv\Scripts\python.exe scripts/migrate_sqlite_to_supabase.py`
Expected: Users, farms, predictions, weather_cache, bee_occurrences migrated

- [ ] **Step 7: Verify health endpoint**

Run: `curl http://localhost:8000/api/health`
Expected: 200 OK with database connection status

- [ ] **Step 8: Verify farm/prediction round-trip**

Run:
```bash
curl http://localhost:8000/api/farms
curl -X POST http://localhost:8000/api/predictions -H "Content-Type: application/json" -d '{"farm_id": 1}'
```
Expected: 200 OK responses with data

- [ ] **Step 9: Commit M1**

```bash
git add backend/.env.example backend/tests/
git commit -m "feat(m1): verify supabase postgres connection and fix tests"
```

---

## Task 2: Implement Two-Level Cache Layer (M2)

**Files:**
- Create: `backend/app/core/cache.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_cache.py`

**Interfaces:**
- Consumes: `REDIS_URL` env var, `settings` config
- Produces: `get_value(key, group)`, `set_value(key, value, ttl)`, `delete_group(group)`

- [ ] **Step 1: Add redis dependency**

Add to `backend/requirements.txt`:
```
redis>=5.0.0
```

- [ ] **Step 2: Add REDIS_URL to config**

Add to `backend/app/core/config.py` Settings class:
```python
redis_url: str = "redis://localhost:6379/0"
```

Add to `backend/.env`:
```
REDIS_URL=redis://localhost:6379/0
```

Add to `backend/.env.example`:
```env
# Redis (local or Upstash)
REDIS_URL=redis://localhost:6379/0
```

- [ ] **Step 3: Write failing test for cache operations**

Create `backend/tests/test_cache.py`:
```python
import pytest
from app.core.cache import cache_get, cache_set, cache_delete_group

def test_cache_set_and_get():
    cache_set("test_key", {"data": "value"}, ttl=60, group="test")
    result = cache_get("test_key", group="test")
    assert result == {"data": "value"}

def test_cache_miss_returns_none():
    result = cache_get("nonexistent_key", group="test")
    assert result is None

def test_cache_delete_group():
    cache_set("key1", "val1", ttl=60, group="mygroup")
    cache_set("key2", "val2", ttl=60, group="mygroup")
    cache_delete_group("mygroup")
    assert cache_get("key1", group="mygroup") is None
    assert cache_get("key2", group="mygroup") is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_cache.py -v`
Expected: FAIL with ImportError (cache module doesn't exist)

- [ ] **Step 5: Implement cache.py**

Create `backend/app/core/cache.py`:
```python
import json
import time
import logging
from typing import Any, Optional
import redis

logger = logging.getLogger(__name__)

# L1 in-memory cache: {key: {"value": ..., "expires_at": ...}}
_l1_cache: dict = {}
L1_DEFAULT_TTL = 300  # 5 minutes

# Lazy Redis client
_redis_client: Optional[redis.Redis] = None

def _get_redis() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
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
                    "expires_at": now + L1_DEFAULT_TTL
                }
                return value
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
    
    return None

def cache_set(key: str, value: Any, ttl: int = L1_DEFAULT_TTL, group: str = "default"):
    full_key = f"{group}:{key}"
    now = time.time()
    
    # L1 set
    _l1_cache[full_key] = {
        "value": value,
        "expires_at": now + ttl
    }
    
    # L2 Redis set
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_cache.py -v`
Expected: PASS

- [ ] **Step 7: Commit M2 cache layer**

```bash
git add backend/app/core/cache.py backend/requirements.txt backend/tests/test_cache.py
git commit -m "feat(m2): implement two-level L1/L2 cache layer"
```

---

## Task 3: Wrap Weather Service with Cache (M2)

**Files:**
- Modify: `backend/app/services/weather_service.py`
- Test: `backend/tests/test_weather_cache.py`

**Interfaces:**
- Consumes: `cache_get`, `cache_set` from `app.core.cache`
- Produces: Cached weather data with L1 → L2 → DB → live fetch fallback

- [ ] **Step 1: Write failing test for cached weather**

Create `backend/tests/test_weather_cache.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from app.services.weather_service import get_weather

@pytest.mark.asyncio
async def test_weather_returns_from_l1_cache():
    # Prime the cache
    with patch("app.core.cache.cache_get", return_value={"temp": 25, "source": "L1"}):
        result = await get_weather(farm_id=1, lat=19.07, lon=73.87)
        assert result["source"] == "L1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_weather_cache.py -v`
Expected: FAIL (weather service not using cache yet)

- [ ] **Step 3: Wrap weather_service with cache**

Add to `backend/app/services/weather_service.py`:
```python
from app.core.cache import cache_get, cache_set

async def get_weather(farm_id: int, lat: float, lon: float):
    cache_key = f"{lat},{lon}"
    
    # L1/L2 cache check
    cached = cache_get(cache_key, group="weather")
    if cached:
        logger.info(f"Weather cache hit for farm {farm_id}: L1/L2")
        return cached
    
    # DB cache check (existing weather_cache table)
    db_weather = await _get_weather_from_db(farm_id)
    if db_weather:
        cache_set(cache_key, db_weather, ttl=900, group="weather")
        return db_weather
    
    # Live fetch
    live_weather = await _fetch_weather_from_api(lat, lon)
    cache_set(cache_key, live_weather, ttl=900, group="weather")
    return live_weather
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_weather_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit weather cache integration**

```bash
git add backend/app/services/weather_service.py backend/tests/test_weather_cache.py
git commit -m "feat(m2): wrap weather service with L1/L2 cache"
```

---

## Task 4: Wrap Bee & Environment Services with Cache (M2)

**Files:**
- Modify: `backend/app/services/bee_service.py`
- Modify: `backend/app/services/environment_service.py`
- Test: `backend/tests/test_services_cache.py`

**Interfaces:**
- Consumes: `cache_get`, `cache_set` from `app.core.cache`
- Produces: Cached bee/NDVI data

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_services_cache.py`:
```python
import pytest
from unittest.mock import patch

@pytest.mark.asyncio
async def test_bee_cache_hit():
    with patch("app.core.cache.cache_get", return_value={"richness": 15, "source": "L1"}):
        from app.services.bee_service import get_bee_data
        result = await get_bee_data(farm_id=1, lat=19.07, lon=73.87)
        assert result["source"] == "L1"

@pytest.mark.asyncio
async def test_ndvi_cache_hit():
    with patch("app.core.cache.cache_get", return_value={"ndvi": 0.65, "source": "L1"}):
        from app.services.environment_service import get_ndvi
        result = await get_ndvi(lat=19.07, lon=73.87)
        assert result["source"] == "L1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_services_cache.py -v`
Expected: FAIL

- [ ] **Step 3: Wrap bee_service with cache**

Add cache layer to `backend/app/services/bee_service.py`:
```python
from app.core.cache import cache_get, cache_set

async def get_bee_data(farm_id: int, lat: float, lon: float):
    cache_key = f"{lat},{lon}"
    cached = cache_get(cache_key, group="bees")
    if cached:
        return cached
    
    bee_data = await _fetch_bee_from_gbif(lat, lon)
    cache_set(cache_key, bee_data, ttl=900, group="bees")
    return bee_data
```

- [ ] **Step 4: Wrap environment_service with cache**

Add cache layer to `backend/app/services/environment_service.py`:
```python
from app.core.cache import cache_get, cache_set

async def get_ndvi(lat: float, lon: float):
    cache_key = f"{lat},{lon}"
    cached = cache_get(cache_key, group="ndvi")
    if cached:
        return cached
    
    ndvi_data = await _fetch_ndvi_from_ee(lat, lon)
    cache_set(cache_key, ndvi_data, ttl=900, group="ndvi")
    return ndvi_data
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_services_cache.py -v`
Expected: PASS

- [ ] **Step 6: Commit service cache wrappers**

```bash
git add backend/app/services/bee_service.py backend/app/services/environment_service.py backend/tests/test_services_cache.py
git commit -m "feat(m2): wrap bee and environment services with cache"
```

---

## Task 5: Install Celery & Create Worker (M3)

**Files:**
- Create: `backend/app/celery_app.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_celery.py`

**Interfaces:**
- Consumes: `REDIS_URL` as broker
- Produces: Celery app with 30-minute beat schedule

- [ ] **Step 1: Add celery dependency**

Add to `backend/requirements.txt`:
```
celery[redis]>=5.3.0
```

- [ ] **Step 2: Write failing test for celery app**

Create `backend/tests/test_celery.py`:
```python
def test_celery_app_exists():
    from app.celery_app import celery_app
    assert celery_app is not None
    assert celery_app.conf.broker_url is not None

def test_beat_schedule_has_refresh_task():
    from app.celery_app import celery_app
    assert "refresh-farm-data" in celery_app.conf.beat_schedule
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_celery.py -v`
Expected: FAIL (celery_app doesn't exist)

- [ ] **Step 4: Implement celery_app.py**

Create `backend/app/celery_app.py`:
```python
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "polisync",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "refresh-farm-data": {
            "task": "app.tasks.data_refresh.refresh_all_farms",
            "schedule": 1800.0,  # Every 30 minutes
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_celery.py -v`
Expected: PASS

- [ ] **Step 6: Commit celery setup**

```bash
git add backend/app/celery_app.py backend/requirements.txt backend/tests/test_celery.py
git commit -m "feat(m3): add celery app with 30-minute beat schedule"
```

---

## Task 6: Implement Data Refresh Tasks (M3)

**Files:**
- Create: `backend/app/tasks/__init__.py`
- Create: `backend/app/tasks/data_refresh.py`
- Test: `backend/tests/test_data_refresh.py`

**Interfaces:**
- Consumes: `weather_service`, `bee_service`, `environment_service`, `cache_delete_group`
- Produces: `refresh_all_farms()` task

- [ ] **Step 1: Write failing test for refresh task**

Create `backend/tests/test_data_refresh.py`:
```python
def test_refresh_task_registered():
    from app.celery_app import celery_app
    from app.tasks.data_refresh import refresh_all_farms
    assert celery_app.tasks.get("app.tasks.data_refresh.refresh_all_farms") is not None

def test_refresh_weather_batch():
    from app.tasks.data_refresh import refresh_weather_batch
    assert callable(refresh_weather_batch)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_data_refresh.py -v`
Expected: FAIL (data_refresh doesn't exist)

- [ ] **Step 3: Create tasks __init__.py**

Create `backend/app/tasks/__init__.py`:
```python
```

- [ ] **Step 4: Implement data_refresh.py**

Create `backend/app/tasks/data_refresh.py`:
```python
import logging
from app.celery_app import celery_app
from app.core.cache import cache_delete_group

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.data_refresh.refresh_all_farms", bind=True, max_retries=3)
def refresh_all_farms(self):
    try:
        refresh_weather_batch()
        refresh_ndvi_batch()
        refresh_bees_batch()
        logger.info("All farm data refreshed successfully")
    except Exception as exc:
        logger.error(f"Refresh failed: {exc}")
        raise self.retry(exc=exc, countdown=60)

def refresh_weather_batch():
    from app.services.weather_service import get_weather
    from app.database import SessionLocal
    from app.models import Farm
    
    db = SessionLocal()
    try:
        farms = db.query(Farm).all()
        for farm in farms:
            try:
                get_weather(farm_id=farm.id, lat=farm.latitude, lon=farm.longitude)
            except Exception as e:
                logger.warning(f"Weather refresh failed for farm {farm.id}: {e}")
    finally:
        db.close()
    cache_delete_group("weather")

def refresh_ndvi_batch():
    from app.services.environment_service import get_ndvi
    from app.database import SessionLocal
    from app.models import Farm
    
    db = SessionLocal()
    try:
        farms = db.query(Farm).all()
        for farm in farms:
            try:
                get_ndvi(lat=farm.latitude, lon=farm.longitude)
            except Exception as e:
                logger.warning(f"NDVI refresh failed for farm {farm.id}: {e}")
    finally:
        db.close()
    cache_delete_group("ndvi")

def refresh_bees_batch():
    from app.services.bee_service import get_bee_data
    from app.database import SessionLocal
    from app.models import Farm
    
    db = SessionLocal()
    try:
        farms = db.query(Farm).all()
        for farm in farms:
            try:
                get_bee_data(farm_id=farm.id, lat=farm.latitude, lon=farm.longitude)
            except Exception as e:
                logger.warning(f"Bee refresh failed for farm {farm.id}: {e}")
    finally:
        db.close()
    cache_delete_group("bees")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest tests/test_data_refresh.py -v`
Expected: PASS

- [ ] **Step 6: Commit data refresh tasks**

```bash
git add backend/app/tasks/ backend/tests/test_data_refresh.py
git commit -m "feat(m3): implement celery data refresh tasks"
```

---

## Task 7: Update Documentation & Verify (M1-M3)

**Files:**
- Modify: `README.md` or `SETUP.md`
- Modify: `backend/.env.example`

**Interfaces:**
- Consumes: All M1-M3 implementations
- Produces: Documented setup instructions

- [ ] **Step 1: Update .env.example with all new vars**

Add to `backend/.env.example`:
```env
# M1 — Supabase Postgres
DATABASE_URL=postgresql://...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# M2 — Redis
REDIS_URL=redis://localhost:6379/0

# M3 — Celery (uses REDIS_URL)
# Worker: celery -A app.celery_app.celery_app worker --loglevel=info
# Beat: celery -A app.celery_app.celery_app beat --loglevel=info
```

- [ ] **Step 2: Add worker start commands to README/SETUP**

Add to documentation:
```markdown
## Running Background Worker

### Development
```bash
# Terminal 1: Start worker
cd backend
celery -A app.celery_app.celery_app worker --loglevel=info

# Terminal 2: Start beat scheduler
cd backend
celery -A app.celery_app.celery_app beat --loglevel=info
```

### Production (Render)
Set start command: `celery -A app.celery_app.celery_app worker --beat --loglevel=info`
```

- [ ] **Step 3: Run full test suite**

Run: `cd backend && ..\.venv\Scripts\python.exe -m pytest -v`
Expected: All tests pass

- [ ] **Step 4: Commit documentation**

```bash
git add backend/.env.example README.md
git commit -m "docs: update setup instructions for M1-M3 infrastructure"
```

---

## Task 8: Integration Test — Full Flow (M1-M3)

**Files:**
- Test: Manual verification

**Interfaces:**
- Consumes: All M1-M3 implementations
- Produces: Verified working system

- [ ] **Step 1: Start backend server**

Run: `cd backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`

- [ ] **Step 2: Start Redis locally**

Run: `docker run -d -p 6379:6379 redis` or `redis-server`

- [ ] **Step 3: Start Celery worker + beat**

Run:
```bash
cd backend
celery -A app.celery_app.celery_app worker --loglevel=info
celery -A app.celery_app.celery_app beat --loglevel=info
```

- [ ] **Step 4: Verify cache hit on repeated request**

Run twice:
```bash
curl http://localhost:8000/api/weather/current?farm_id=1
```
Expected: Second request is faster, logs show "L1/L2 cache hit"

- [ ] **Step 5: Verify Redis failure graceful degradation**

Stop Redis, run weather endpoint again
Expected: Serves from L1/DB, logs warning "Redis unavailable, L1-only mode"

- [ ] **Step 6: Verify Celery beat triggers refresh**

Wait 30 minutes or manually trigger:
```bash
celery -A app.celery_app.celery_app call app.tasks.data_refresh.refresh_all_farms
```
Expected: Worker executes, logs show data refreshed

---

## Definition of Done — Plan A

- [ ] M1: Supabase Postgres verified, all tests pass against Postgres
- [ ] M2: L1/L2 cache working, weather/bee/NDVI cached, graceful Redis degradation
- [ ] M3: Celery worker + beat running, 30-minute refresh cycle active
- [ ] All code committed with descriptive messages
- [ ] Documentation updated with setup instructions
