import pytest
from unittest.mock import patch, AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.weather_cache import WeatherCache
from app.services.weather_service import get_weather_with_cache


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _payload(days: int = 7) -> dict:
    return {
        "current": {
            "temperature_2m": 28.0,
            "relative_humidity_2m": 62,
            "precipitation": 1.2,
            "wind_speed_10m": 9.5,
        },
        "daily": {
            "time": [f"2026-08-{i:02d}" for i in range(1, days + 1)],
            "temperature_2m_max": [29.0] * days,
            "temperature_2m_min": [18.0] * days,
            "precipitation_sum": [0.0] * days,
        },
    }


@pytest.mark.asyncio
async def test_db_cache_path_returns_full_forecast(db):
    db.add(WeatherCache(farm_id="wc-full", payload=_payload(7)))
    db.commit()

    with patch("app.services.weather_service.cache_get", return_value=None), \
         patch("app.services.weather_service.cache_set") as cache_set:
        result = await get_weather_with_cache("wc-full", 19.0, 73.0, db)

    assert result["source"] == "db_cache"
    assert len(result["daily"]["time"]) == 7
    assert len(result["daily"]["temperature_2m_max"]) == 7
    assert result["current"]["temperature_2m"] == 28.0
    cache_set.assert_called_once()


@pytest.mark.asyncio
async def test_db_cache_path_legacy_row_falls_through_to_live(db):
    db.add(WeatherCache(farm_id="wc-legacy", temperature=30.0, humidity=60))
    db.commit()

    live = {
        "current": {"temperature_2m": 28.0, "relative_humidity_2m": 62,
                    "precipitation": 1.2, "wind_speed_10m": 9.5},
        "daily": {
            "time": ["2026-08-01"],
            "temperature_2m_max": [29.0],
            "temperature_2m_min": [18.0],
            "precipitation_sum": [0.0],
        },
    }
    with patch("app.services.weather_service.cache_get", return_value=None), \
         patch("app.services.weather_service.cache_set"), \
         patch("app.services.weather_service.fetch_weather",
               new=AsyncMock(return_value=live)) as fetch:
        result = await get_weather_with_cache("wc-legacy", 19.0, 73.0, db)

    fetch.assert_awaited_once()
    assert result["source"] == "live"
    assert len(result["daily"]["time"]) == 1


@pytest.mark.asyncio
async def test_stale_empty_daily_cache_entry_is_ignored(db):
    stale = {
        "current": {"temperature_2m": 28.0, "relative_humidity_2m": 62,
                    "precipitation": 1.2, "wind_speed_10m": 9.5},
        "daily": {
            "time": [],
            "temperature_2m_max": [],
            "temperature_2m_min": [],
            "precipitation_sum": [],
        },
        "source": "db_cache",
    }
    live = {
        "current": {"temperature_2m": 27.0, "relative_humidity_2m": 60,
                    "precipitation": 0.5, "wind_speed_10m": 8.0},
        "daily": {
            "time": ["2026-08-01"],
            "temperature_2m_max": [30.0],
            "temperature_2m_min": [19.0],
            "precipitation_sum": [0.0],
        },
    }
    with patch("app.services.weather_service.cache_get", return_value=stale), \
         patch("app.services.weather_service.cache_set"), \
         patch("app.services.weather_service.fetch_weather",
               new=AsyncMock(return_value=live)) as fetch:
        result = await get_weather_with_cache("wc-stale", 19.0, 73.0, db)

    fetch.assert_awaited_once()
    assert result["source"] == "live"
    assert len(result["daily"]["time"]) == 1


def test_forecast_route_serves_from_cache():
    from fastapi.testclient import TestClient
    from app.main import app

    def _auth_headers(client: TestClient) -> dict[str, str]:
        email = "forecast-cache@example.com"
        password = "StrongPass1!"
        client.post("/api/auth/register", json={"email": email, "password": password, "full_name": "Cache Tester"})
        token = client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        headers = _auth_headers(client)
        farm_id = client.post(
            "/api/farms",
            json={"name": "Forecast Farm", "crop": "Mustard", "location": "Nashik, Maharashtra", "area_acres": 3.0},
            headers=headers,
        ).json()["id"]

        with patch(
            "app.api.routes.weather.get_weather_with_cache",
            new=AsyncMock(return_value=_payload(7)),
        ) as mw:
            response = client.get("/api/weather/forecast", params={"farm_id": farm_id, "days": 7}, headers=headers)

    assert response.status_code == 200
    mw.assert_awaited_once()
    assert len(response.json()["forecast"]) == 7
    assert response.json()["forecast"][0]["date"] == "2026-08-01"
