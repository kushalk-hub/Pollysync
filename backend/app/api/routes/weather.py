from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.farm import Farm
from app.models.user import User
from app.models.weather_cache import WeatherCache
from app.schemas.weather import ForecastDay, WeatherCurrent, WeatherForecast
from app.services.weather_service import (
    fetch_weather,
    get_weather_with_cache,
    get_cached_weather,
    parse_forecast,
    cache_weather,
    get_location_aware_fallback,
)

router = APIRouter(prefix="/weather", tags=["weather"])


def _owned_farm_or_404(farm_id: str, user_id: str, db: Session) -> Farm:
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.user_id == user_id))
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


@router.get("/current", response_model=WeatherCurrent)
async def current_weather(
    farm_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeatherCurrent:
    farm = _owned_farm_or_404(farm_id, current_user.id, db)
    cached = get_cached_weather(farm_id, db, farm.location_lat, farm.location_lng)
    if cached:
        return WeatherCurrent(
            temperature=cached.temperature,
            humidity=cached.humidity,
            rainfall=cached.rainfall,
            wind_speed=cached.wind_speed,
            timestamp=cached.timestamp.isoformat() if cached.timestamp else None,
            source="db_cache",
        )
    try:
        raw = await fetch_weather(farm.location_lat, farm.location_lng)
    except Exception:
        raw = await get_location_aware_fallback(farm.location_lat, farm.location_lng)

    current = raw.get("current", {})
    if raw.get("fallback"):
        return WeatherCurrent(
            temperature=current.get("temperature_2m", 0),
            humidity=current.get("relative_humidity_2m", 0),
            rainfall=current.get("precipitation", 0),
            wind_speed=current.get("wind_speed_10m", 0),
            timestamp=None,
            source=raw.get("source", "fallback"),
        )
    record = cache_weather(
        farm_id, raw, db, farm.location_lat, farm.location_lng
    )
    return WeatherCurrent(
        temperature=record.temperature,
        humidity=record.humidity,
        rainfall=record.rainfall,
        wind_speed=record.wind_speed,
        timestamp=record.timestamp.isoformat() if record.timestamp else None,
        source="live",
    )


@router.get("/forecast", response_model=WeatherForecast)
async def forecast(
    farm_id: str = Query(...),
    days: int = Query(7, ge=1, le=16),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeatherForecast:
    farm = _owned_farm_or_404(farm_id, current_user.id, db)
    raw = await get_weather_with_cache(farm_id, farm.location_lat, farm.location_lng, db)
    forecast_data = parse_forecast(raw)[:days]
    return WeatherForecast(
        forecast=[ForecastDay(**d) for d in forecast_data],
        source=raw.get("source"),
    )
