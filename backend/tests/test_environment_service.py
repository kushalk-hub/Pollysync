import pytest
from datetime import date
from unittest.mock import patch, AsyncMock

from app.services.environment_service import fetch_ndvi, get_environment_features


@pytest.mark.asyncio
async def test_fetch_ndvi_returns_none_when_ee_unconfigured():
    with patch("app.core.config.settings") as s:
        s.ee_service_account = ""
        s.ee_private_key_file = ""
        with patch("anyio.to_thread.run_sync",
                   side_effect=RuntimeError("EE not initialized")):
            result = await fetch_ndvi(19.0, 73.0, date.today())
    assert result is None


@pytest.mark.asyncio
async def test_environment_features_not_cached_when_ndvi_is_none():
    with patch("app.services.environment_service.cache_get", return_value=None), \
         patch("app.services.environment_service.fetch_nasa_power_7d",
               new=AsyncMock(return_value={"temp_7d_mean": 24.0, "humidity": 80,
                                           "rainfall_7d": 5.0, "wind_speed": 10.0,
                                           "t_max_7d": 29.0, "t_min_7d": 19.0})), \
         patch("app.services.environment_service.fetch_ndvi",
               new=AsyncMock(return_value=None)), \
         patch("app.services.environment_service.fetch_bee_richness",
               new=AsyncMock(return_value=4)), \
         patch("app.services.environment_service.cache_set") as cache_set:
        result = await get_environment_features(lat=19.0, lon=73.0,
                                                crop_type="Mustard", as_of=date.today())

    assert result["ndvi"] is None
    cache_set.assert_not_called()


@pytest.mark.asyncio
async def test_environment_features_cached_when_ndvi_present():
    with patch("app.services.environment_service.cache_get", return_value=None), \
         patch("app.services.environment_service.fetch_nasa_power_7d",
               new=AsyncMock(return_value={"temp_7d_mean": 24.0, "humidity": 80,
                                           "rainfall_7d": 5.0, "wind_speed": 10.0,
                                           "t_max_7d": 29.0, "t_min_7d": 19.0})), \
         patch("app.services.environment_service.fetch_ndvi",
               new=AsyncMock(return_value=0.42)), \
         patch("app.services.environment_service.fetch_bee_richness",
               new=AsyncMock(return_value=4)), \
         patch("app.services.environment_service.cache_set") as cache_set:
        result = await get_environment_features(lat=19.0, lon=73.0,
                                                crop_type="Mustard", as_of=date.today())

    assert result["ndvi"] == 0.42
    cache_set.assert_called_once()
