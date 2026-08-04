import pytest
from datetime import date
from unittest.mock import patch

from app.services.environment_service import fetch_ndvi


@pytest.mark.asyncio
async def test_fetch_ndvi_returns_none_when_ee_unconfigured():
    with patch("app.core.config.settings") as s:
        s.ee_service_account = ""
        s.ee_private_key_file = ""
        with patch("anyio.to_thread.run_sync",
                   side_effect=RuntimeError("EE not initialized")):
            result = await fetch_ndvi(19.0, 73.0, date.today())
    assert result is None
