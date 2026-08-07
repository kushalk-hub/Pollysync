import asyncio
import logging
import traceback
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.weather_cache import WeatherCache
from app.core.cache import cache_get, cache_set
from app.core.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lng}"
    "&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
    "&timezone=auto"
)

_FALLBACK_CURRENT = {
    "temperature_2m": 28,
    "relative_humidity_2m": 62,
    "precipitation": 1.2,
    "wind_speed_10m": 9.5,
}

_COORD_TOLERANCE = 0.001  # ~100m: only rows fetched for essentially this exact spot


async def fetch_weather(lat: float, lng: float) -> dict:
    """Fetch Open-Meteo weather with bounded retry on 429 rate-limiting."""
    url = OPEN_METEO_URL.format(lat=lat, lng=lng)
    max_attempts = 3
    async with httpx.AsyncClient() as client:
        for attempt in range(max_attempts):
            resp = await client.get(url, timeout=10)
            if resp.status_code == 429 and attempt < max_attempts - 1:
                logger.warning(
                    f"open-meteo 429 (attempt {attempt + 1}/{max_attempts}) for ({lat},{lng})"
                )
                await asyncio.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
    raise RuntimeError("open-meteo fetch exhausted retries")


def get_fallback_weather(lat: float, lng: float) -> dict:
    # Last-resort constant fallback; kept location-shaped but constant so the
    # callers always receive a weather-shaped dict even when every upstream is
    # down. Tagged "fallback" so it is never persisted or mistaken for real data.
    return {
        "current": dict(_FALLBACK_CURRENT),
        "daily": {
            "time": [],
            "temperature_2m_max": [],
            "temperature_2m_min": [],
            "precipitation_sum": [],
        },
        "fallback": True,
        "source": "fallback",
        "source_location": {"lat": lat, "lng": lng},
    }


async def get_location_aware_fallback(lat: float, lng: float) -> dict:
    """Location-aware fallback weather when Open-Meteo is unavailable.

    Uses NASA POWER's historical 7-day means for the exact (lat, lng) so the
    PSI model still gets place-specific temperature/humidity/rain/wind instead
    of a planet-wide constant. Falls back to get_fallback_weather() only if
    NASA POWER also fails.
    """
    try:
        from datetime import date

        from app.services.environment_service import fetch_nasa_power_7d_protected

        env = await fetch_nasa_power_7d_protected(lat, lng, date.today())
        temp = env.get("temp_7d_mean")
        humidity = env.get("humidity")
        rain_7d = env.get("rainfall_7d")
        wind = env.get("wind_speed")
        if temp is None or humidity is None:
            return get_fallback_weather(lat, lng)
        return {
            "current": {
                "temperature_2m": temp,
                "relative_humidity_2m": humidity,
                "precipitation": round((rain_7d or 0) / 7, 2),
                "wind_speed_10m": wind if wind is not None else _FALLBACK_CURRENT["wind_speed_10m"],
            },
            "daily": {
                "time": [],
                "temperature_2m_max": [],
                "temperature_2m_min": [],
                "precipitation_sum": [],
            },
            "fallback": True,
            "source": "nasa_fallback",
            "source_location": {"lat": lat, "lng": lng},
        }
    except Exception:
        logger.warning("NASA POWER fallback failed for (%s,%s)", lat, lng, exc_info=True)
        return get_fallback_weather(lat, lng)


@circuit_breaker("open-meteo", max_failures=3, window_seconds=300, fallback=get_location_aware_fallback)
async def fetch_weather_protected(lat: float, lng: float) -> dict:
    """Fetch weather with circuit breaker protection."""
    return await fetch_weather(lat, lng)


def get_cached_weather(
    farm_id: str,
    db: Session,
    lat: float | None = None,
    lng: float | None = None,
) -> WeatherCache | None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    query = db.query(WeatherCache).filter(
        WeatherCache.farm_id == farm_id,
        WeatherCache.timestamp > cutoff,
    )
    if lat is not None and lng is not None:
        query = query.filter(
            WeatherCache.latitude.isnot(None),
            func.abs(WeatherCache.latitude - lat) < _COORD_TOLERANCE,
            func.abs(WeatherCache.longitude - lng) < _COORD_TOLERANCE,
        )
    return (
        query.order_by(WeatherCache.timestamp.desc())
        .first()
    )


def cache_weather(
    farm_id: str,
    data: dict,
    db: Session,
    lat: float | None = None,
    lng: float | None = None,
) -> WeatherCache:
    current = data.get("current", {})
    record = WeatherCache(
        farm_id=farm_id,
        temperature=current.get("temperature_2m", 0),
        humidity=current.get("relative_humidity_2m", 0),
        rainfall=current.get("precipitation", 0),
        wind_speed=current.get("wind_speed_10m", 0),
        latitude=lat,
        longitude=lng,
        payload=data,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def parse_forecast(raw: dict) -> list[dict]:
    daily = raw.get("daily", {})
    dates = daily.get("time", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    rain = daily.get("precipitation_sum", [])
    return [
        {"date": d, "temp_max": t_max[i], "temp_min": t_min[i], "rainfall": rain[i]}
        for i, d in enumerate(dates)
    ]


def _has_daily_forecast(data: dict | None) -> bool:
    """A cached weather entry only counts as valid if it carries daily data.
    Entries cached by older code (or a fallback) may have empty `daily`."""
    return bool(data and data.get("daily", {}).get("time"))


def get_latest_forecast_row(
    farm_id: str,
    db: Session,
    lat: float | None = None,
    lng: float | None = None,
) -> WeatherCache | None:
    """Most recent DB row that still carries a real daily forecast, regardless
    of age. Used as a stale fallback so an outage never returns an empty array
    when real forecast data was captured at some point. Filtered to the farm's
    current coordinates so moving a farm never serves another place's weather."""
    query = db.query(WeatherCache).filter(WeatherCache.farm_id == farm_id)
    if lat is not None and lng is not None:
        query = query.filter(
            WeatherCache.latitude.isnot(None),
            func.abs(WeatherCache.latitude - lat) < _COORD_TOLERANCE,
            func.abs(WeatherCache.longitude - lng) < _COORD_TOLERANCE,
        )
    rows = query.order_by(WeatherCache.timestamp.desc()).all()
    for row in rows:
        if _has_daily_forecast(row.payload):
            return row
    return None


async def get_weather_with_cache(farm_id: str, lat: float, lng: float, db: Session) -> dict:
    """Get weather data with L1/L2 cache layer."""
    cache_key = f"{lat},{lng}"

    # L1/L2 cache check -- ignore stale entries that lack the daily forecast
    cached = cache_get(cache_key, group="weather")
    if cached and _has_daily_forecast(cached):
        return cached

    # DB cache check -- only full-payload rows preserve the daily forecast.
    # Legacy rows (no payload, or empty daily) fall through to a live fetch.
    # Rows are matched to the farm's current coordinates so a relocated farm
    # never reuses weather captured for its previous location.
    db_weather = get_cached_weather(farm_id, db, lat, lng)
    if db_weather and _has_daily_forecast(db_weather.payload):
        result = {
            **db_weather.payload,
            "source": "db_cache",
        }
        cache_set(cache_key, result, ttl=300, group="weather")
        return result

    # Live fetch (circuit-breaker protected so repeated failures short-circuit)
    live_weather = None
    try:
        live_weather = await fetch_weather_protected(lat, lng)
        if not _has_daily_forecast(live_weather):
            logger.warning(
                "[weather] live fetch for farm %s (%s,%s) returned no daily data",
                farm_id, lat, lng,
            )
            live_weather = None
    except Exception:
        logger.warning(
            "[weather] live fetch failed for farm %s (%s,%s):\n%s",
            farm_id, lat, lng, traceback.format_exc(limit=3),
        )

    if live_weather is not None:
        live_weather["source"] = "live"
        try:
            cache_weather(farm_id, live_weather, db, lat, lng)
        except Exception:
            logger.warning("[weather] failed to persist live weather to DB", exc_info=True)
        cache_set(cache_key, live_weather, ttl=300, group="weather")
        return live_weather

    # Failure path -- stale real data for THIS farm's current coordinates
    # beats an empty forecast.
    stale = get_latest_forecast_row(farm_id, db, lat, lng)
    if stale:
        result = {
            **stale.payload,
            "source": "db_cache_stale",
        }
        cache_set(cache_key, result, ttl=300, group="weather")
        return result

    # Last resort: a legacy current-only DB row (no forecast), else a
    # location-aware fallback derived from NASA POWER for these coordinates.
    if db_weather and not db_weather.payload:
        result = {
            "current": {
                "temperature_2m": db_weather.temperature,
                "relative_humidity_2m": db_weather.humidity,
                "precipitation": db_weather.rainfall,
                "wind_speed_10m": db_weather.wind_speed,
            },
            "daily": {
                "time": [],
                "temperature_2m_max": [],
                "temperature_2m_min": [],
                "precipitation_sum": [],
            },
            "source": "db_cache",
            "fallback": True,
        }
        cache_set(cache_key, result, ttl=300, group="weather")
        return result
    fallback = await get_location_aware_fallback(lat, lng)
    cache_set(cache_key, fallback, ttl=300, group="weather")
    return fallback
