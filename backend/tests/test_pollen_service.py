import pytest
from unittest.mock import patch, AsyncMock
from app.services.pollen_service import fetch_pollen_with_fallback


def test_pollen_returns_seasonal_fallback_without_key():
    with patch("app.services.pollen_service.POLLEN_API_KEY", ""):
        import asyncio
        result = asyncio.run(fetch_pollen_with_fallback(19.07, 73.87))
        assert "tree" in result
        assert "grass" in result
        assert "weed" in result
        assert result["source"] == "seasonal"


def test_pollen_returns_seasonal_fallback_on_api_error():
    with patch("app.services.pollen_service.POLLEN_API_KEY", "test-key"):
        with patch("app.services.pollen_service.fetch_pollen", new_callable=AsyncMock, return_value=None):
            import asyncio
            result = asyncio.run(fetch_pollen_with_fallback(19.07, 73.87))
            assert "tree" in result
            assert result["source"] == "seasonal"
