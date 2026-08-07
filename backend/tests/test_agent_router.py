import pytest
from unittest.mock import patch, AsyncMock

from app.models.farm import Farm


class _Q:
    def __init__(self, obj):
        self.obj = obj

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return self.obj


class _Session:
    def __init__(self, farm):
        self._farm = farm

    def query(self, model):
        if model is Farm:
            return _Q(self._farm)
        return _Q(None)


@pytest.mark.asyncio
async def test_assemble_farm_context_uses_location_lat_lng():
    from app.agent.router import assemble_farm_context

    farm = Farm(
        id="f1",
        user_id="u1",
        name="North Field",
        crop_type="Mustard",
        location_name="Niphad",
        location_lat=19.9975,
        location_lng=73.7898,
    )
    with patch("app.services.weather_service.get_weather_with_cache",
               new=AsyncMock(return_value={"current": {"temperature_2m": 27, "relative_humidity_2m": 55}})) as mw, \
         patch("app.services.bee_service.get_bee_data_with_cache",
               new=AsyncMock(return_value={"richness": 4})) as mb:
        ctx = await assemble_farm_context("f1", _Session(farm))

    mw.assert_awaited_once()
    assert mw.await_args.args[1] == 19.9975
    assert mw.await_args.args[2] == 73.7898
    mb.assert_awaited_once()
    assert mb.await_args.args[1] == 19.9975
    assert mb.await_args.args[2] == 73.7898
    assert "Temperature: 27°C" in ctx
    assert "Bee species richness: 4" in ctx


@pytest.mark.asyncio
async def test_assemble_farm_context_includes_seven_day_forecast():
    from app.agent.router import assemble_farm_context

    farm = Farm(
        id="f1",
        user_id="u1",
        name="North Field",
        crop_type="Mustard",
        location_name="Niphad",
        location_lat=19.9975,
        location_lng=73.7898,
    )
    weather = {
        "current": {"temperature_2m": 27, "relative_humidity_2m": 55},
        "daily": {
            "time": ["2026-08-08", "2026-08-09"],
            "temperature_2m_max": [29.0, 30.5],
            "temperature_2m_min": [18.0, 19.0],
            "precipitation_sum": [0.2, 1.1],
        },
    }
    with patch("app.services.weather_service.get_weather_with_cache",
               new=AsyncMock(return_value=weather)) as mw, \
         patch("app.services.bee_service.get_bee_data_with_cache",
               new=AsyncMock(return_value={"richness": 4})):
        ctx = await assemble_farm_context("f1", _Session(farm))

    mw.assert_awaited_once()
    assert "7-day forecast:" in ctx
    assert "2026-08-08: 29.0°C/18.0°C, rain 0.2mm" in ctx
    assert "2026-08-09: 30.5°C/19.0°C, rain 1.1mm" in ctx
