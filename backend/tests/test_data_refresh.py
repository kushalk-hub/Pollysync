from unittest.mock import patch
import asyncio

import app.tasks.data_refresh as dr


class _FakeFarm:
    def __init__(self, i):
        self.id = f"farm-{i}"
        self.location_lat = 19.0 + i
        self.location_lng = 73.0 + i


class _FakeQuery:
    def __init__(self, count):
        self._farms = [_FakeFarm(i) for i in range(count)]

    def all(self):
        return self._farms


class _FakeSession:
    def query(self, model):
        return _FakeQuery(5)

    def close(self):
        pass


def test_refresh_bees_batch_uses_one_event_loop():
    calls = []
    async def fake_fetch(lat, lng, radius_km=10):
        calls.append(asyncio.get_running_loop())
        return []
    with patch("app.services.bee_service.fetch_bees", side_effect=fake_fetch), \
         patch("app.database.SessionLocal", return_value=_FakeSession()):
        dr.refresh_bees_batch()
    assert len(calls) >= 2
    assert len(set(calls)) == 1


def test_refresh_weather_batch_uses_one_event_loop():
    calls = []
    async def fake_fetch(lat, lng):
        calls.append(asyncio.get_running_loop())
        return {"temp_7d_mean": 1.0}
    with patch("app.services.weather_service.fetch_weather", side_effect=fake_fetch), \
         patch("app.services.weather_service.cache_weather"), \
         patch("app.database.SessionLocal", return_value=_FakeSession()):
        dr.refresh_weather_batch()
    assert len(calls) >= 2
    assert len(set(calls)) == 1


def test_refresh_ndvi_batch_uses_one_event_loop():
    calls = []
    async def fake_fetch(lat, lng, as_of, window_days=20):
        calls.append(asyncio.get_running_loop())
        return 0.5
    with patch("app.services.environment_service.fetch_ndvi", side_effect=fake_fetch), \
         patch("app.database.SessionLocal", return_value=_FakeSession()):
        dr.refresh_ndvi_batch()
    assert len(calls) >= 2
    assert len(set(calls)) == 1
