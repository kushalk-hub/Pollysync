import logging
from datetime import date
from typing import Optional

import httpx

from app.core.config import settings
from app.services.feature_engineering import get_pollen_for_month

logger = logging.getLogger(__name__)

POLLEN_API_KEY = settings.pollen_api_key
POLLEN_API_URL = "https://pollen.googleapis.com/v1/forecast:lookup"


async def fetch_pollen(lat: float, lon: float, as_of: Optional[date] = None) -> Optional[dict]:
    """Fetch live pollen data from Google Pollen API."""
    if not POLLEN_API_KEY:
        return None
    
    as_of = as_of or date.today()
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                POLLEN_API_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "days": 1,
                    "key": POLLEN_API_KEY,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        
        # Parse response - adjust based on actual API response format
        daily = data.get("daily", [{}])[0] if data.get("daily") else {}
        pollen_info = daily.get("pollen", {})
        
        return {
            "tree": pollen_info.get("tree", 0),
            "grass": pollen_info.get("grass", 0),
            "weed": pollen_info.get("weed", 0),
            "source": "live",
        }
    except Exception as e:
        logger.warning(f"Pollen API fetch failed: {e}")
        return None


async def fetch_pollen_with_fallback(lat: float, lon: float, as_of: Optional[date] = None) -> dict:
    """Fetch pollen with seasonal fallback."""
    as_of = as_of or date.today()
    
    # Try live API first
    live_pollen = await fetch_pollen(lat, lon, as_of)
    if live_pollen:
        return live_pollen
    
    # Fallback to seasonal data
    seasonal = get_pollen_for_month(as_of.month)
    seasonal["source"] = "seasonal"
    return seasonal
