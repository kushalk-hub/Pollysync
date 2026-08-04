import inspect

import pytest
from unittest.mock import patch, AsyncMock, Mock

from app.services.bee_service import fetch_bees, get_bee_data_with_cache


@pytest.mark.asyncio
async def test_fetch_bees_parses_results():
    payload = {"results": [
        {"species": "Apis cerana", "decimalLatitude": 19.0,
         "decimalLongitude": 73.0, "eventDate": "2020-03-01"},
        {"species": None, "decimalLatitude": 19.0, "decimalLongitude": 73.0},
    ]}
    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        result = await fetch_bees(19.0, 73.0)
    assert result[0]["species"] == "Apis cerana"
    assert len(result) == 1


@pytest.mark.asyncio
async def test_fetch_bees_is_awaitable():
    coro = fetch_bees(19.0, 73.0)
    assert inspect.iscoroutine(coro)
    coro.close()


@pytest.mark.asyncio
async def test_get_bee_data_with_cache_uses_protected_fetch_when_cold():
    with patch("app.services.bee_service.cache_get", return_value=None), \
         patch("app.services.bee_service.get_bee_species_for_farm", return_value=[]), \
         patch("app.services.bee_service.fetch_bees", new=AsyncMock(return_value=[])), \
         patch("app.services.bee_service.fetch_bees_protected",
               new=AsyncMock(return_value=[{"species": "Apis dorsata"}])) as m:
        from app.database import SessionLocal
        result = await get_bee_data_with_cache("f1", 19.0, 73.0, SessionLocal())
        m.assert_awaited_once()
        assert result["richness"] == 1
