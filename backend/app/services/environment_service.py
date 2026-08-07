"""
app/services/environment_service.py

Pulls every real environment parameter PolliSync's ML models need, for a
given (lat, lon, date). Output dict matches FEATURE_COLS in train_model.py
exactly, so it can be used for both:
  - live prediction (call get_environment_features() with today's date)
  - batch training-data generation (loop over many lat/lon/date combos and
    write rows to a CSV instead of flowering_data.csv's synthetic values)

Sources used (all free):
  - NASA POWER          -> temp_7d_mean, humidity, rainfall_7d, wind_speed
  - Google Earth Engine  -> ndvi (Sentinel-2)
  - GBIF                -> bee_richness
  - Static seasonal table -> pollen_tree/grass/weed (no live India API exists)

Install: pip install httpx earthengine-api
Auth (Earth Engine): create a free account at earthengine.google.com/signup,
then either run `earthengine authenticate` once locally, OR (for servers)
create a service account, download its JSON key, and set:
  EE_SERVICE_ACCOUNT=xxx@xxx.iam.gserviceaccount.com
  EE_PRIVATE_KEY_FILE=/path/to/key.json
in your .env. No key needed for NASA POWER or GBIF.
"""

from __future__ import annotations

import os
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import httpx

from app.core.cache import cache_get, cache_set
from app.core.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# 1. WEATHER (NASA POWER) -> temp_7d_mean, humidity, rainfall_7d, wind_speed
# --------------------------------------------------------------------------

NASA_POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
    "?parameters=T2M_MAX,T2M_MIN,RH2M,PRECTOTCORR,WS2M"
    "&community=AG"
    "&longitude={lon}&latitude={lat}"
    "&start={start}&end={end}"
    "&format=JSON"
)


async def fetch_nasa_power_7d(lat: float, lon: float, as_of: date) -> dict:
    """Returns the 7-day-mean weather ending on `as_of`, in the units the
    GDD/feature pipeline expects. Works for any date (past or recent),
    which is what makes it usable for training-data generation, unlike
    Open-Meteo's forecast-only current/daily endpoint."""
    start = (as_of - timedelta(days=7)).strftime("%Y%m%d")
    end = as_of.strftime("%Y%m%d")
    url = NASA_POWER_URL.format(lat=lat, lon=lon, start=start, end=end)

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    params = data["properties"]["parameter"]
    t_max = [v for v in params["T2M_MAX"].values() if v not in (-999, None)]
    t_min = [v for v in params["T2M_MIN"].values() if v not in (-999, None)]
    rh = [v for v in params["RH2M"].values() if v not in (-999, None)]
    rain = [v for v in params["PRECTOTCORR"].values() if v not in (-999, None)]
    wind = [v for v in params["WS2M"].values() if v not in (-999, None)]

    daily_mean_temp = [(mx + mn) / 2 for mx, mn in zip(t_max, t_min)]

    return {
        "temp_7d_mean": round(sum(daily_mean_temp) / len(daily_mean_temp), 2) if daily_mean_temp else None,
        "humidity": round(sum(rh) / len(rh), 2) if rh else None,
        "rainfall_7d": round(sum(rain), 2) if rain else None,          # total over 7d, not mean
        "wind_speed": round((sum(wind) / len(wind)) * 3.6, 2) if wind else None,  # m/s -> km/h
        "t_max_7d": t_max,   # kept for GDD calc (gdd_model.py needs daily max/min)
        "t_min_7d": t_min,
    }


@circuit_breaker("nasa-power", max_failures=3, window_seconds=300)
async def fetch_nasa_power_7d_protected(lat: float, lon: float, as_of: date) -> dict:
    """Fetch NASA POWER data with circuit breaker protection."""
    return await fetch_nasa_power_7d(lat, lon, as_of)


# --------------------------------------------------------------------------
# 2. NDVI (Google Earth Engine, Sentinel-2) -> ndvi
# --------------------------------------------------------------------------

_ee_initialized = False
_ee_failed = False


def _write_key_json_to_temp(key_json: str) -> Path:
    """Write an EE service-account JSON (from env var) to a temp file so
    ee.ServiceAccountCredentials can read it as a path."""
    import json
    import tempfile

    data = json.loads(key_json)
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return Path(path)


def _init_earth_engine():
    global _ee_initialized, _ee_failed
    if _ee_initialized or _ee_failed:
        return
    try:
        import ee  # imported lazily so the rest of the module works without it installed
        from app.core.config import settings

        service_account = settings.ee_service_account
        key_file = settings.ee_private_key_file
        key_json = settings.ee_private_key_json
        if service_account and key_json:
            key_path = _write_key_json_to_temp(key_json)
            credentials = ee.ServiceAccountCredentials(service_account, str(key_path))
            ee.Initialize(credentials)
        elif service_account and key_file:
            key_path = Path(key_file)
            if not key_path.is_absolute():
                backend_dir = Path(__file__).resolve().parent.parent.parent
                if key_path.parts and key_path.parts[0] == "backend":
                    key_path = backend_dir.parent / key_path
                else:
                    key_path = backend_dir / key_path
            credentials = ee.ServiceAccountCredentials(service_account, str(key_path))
            ee.Initialize(credentials)
        else:
            # falls back to local `earthengine authenticate` token for dev use
            ee.Initialize()
        _ee_initialized = True
    except Exception as e:
        _ee_failed = True
        logger.warning(f"Earth Engine initialization failed: {e}")


_NDVI_MAX_CLOUD = 20
_NDVI_FALLBACK_WINDOWS = (60, 90, 180)


async def fetch_ndvi(lat: float, lon: float, as_of: date, window_days: int = 20) -> Optional[float]:
    """Mean NDVI from the least-cloudy Sentinel-2 scenes in a window ending
    on `as_of`. When no <20%-cloud scene exists in `window_days` (common
    during the monsoon), the search widens progressively up to 180 days.
    Earth Engine's Python client is synchronous, so this runs it in a thread
    to avoid blocking the FastAPI event loop."""
    import anyio
    import ee

    def _query():
        _init_earth_engine()
        point = ee.Geometry.Point([lon, lat])
        end = as_of.isoformat()
        for days in (window_days,) + _NDVI_FALLBACK_WINDOWS:
            start = (as_of - timedelta(days=days)).isoformat()

            collection = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(point)
                .filterDate(start, end)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", _NDVI_MAX_CLOUD))
            )
            if collection.size().getInfo() == 0:
                continue

            def add_ndvi(img):
                return img.addBands(img.normalizedDifference(["B8", "B4"]).rename("ndvi"))

            with_ndvi = collection.map(add_ndvi)
            mean_ndvi_img = with_ndvi.select("ndvi").mean()
            value = mean_ndvi_img.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=point, scale=10
            ).get("ndvi")
            result = value.getInfo()
            return round(result, 4) if result is not None else None
        return None

    try:
        return await anyio.to_thread.run_sync(_query)
    except Exception as e:
        logger.warning(f"NDVI fetch failed for ({lat}, {lon}): {e}")
        return None


@circuit_breaker("earth-engine", max_failures=3, window_seconds=300)
async def fetch_ndvi_protected(lat: float, lon: float, as_of: date, window_days: int = 20) -> Optional[float]:
    """Fetch NDVI with circuit breaker protection."""
    return await fetch_ndvi(lat, lon, as_of, window_days)


# --------------------------------------------------------------------------
# 3. BEE RICHNESS (GBIF) -> bee_richness
# --------------------------------------------------------------------------

GBIF_URL = (
    "https://api.gbif.org/v1/occurrence/search"
    "?taxonKey=4334"  # Apidae (bees)
    "&decimalLatitude={lat_min},{lat_max}"
    "&decimalLongitude={lon_min},{lon_max}"
    "&limit=300"
)


async def fetch_bee_richness(lat: float, lon: float, radius_km: float = 25) -> int:
    """Distinct bee species recorded within radius_km. India's GBIF density
    is sparse (see project README) so treat this as a lower-bound signal,
    not a precise count -- it's a proxy feature, same caveat as pollinator_proxy_v2."""
    deg = radius_km / 111  # rough km->degree conversion
    url = GBIF_URL.format(
        lat_min=lat - deg, lat_max=lat + deg,
        lon_min=lon - deg, lon_max=lon + deg,
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15)
        if resp.status_code != 200:
            return 0
        results = resp.json().get("results", [])

    species = {r.get("species") for r in results if r.get("species")}
    return len(species)


# --------------------------------------------------------------------------
# 4. POLLEN (static seasonal proxy -- no live India API exists)
# --------------------------------------------------------------------------

from app.services.feature_engineering import get_pollen_for_month  # noqa: E402


# --------------------------------------------------------------------------
# Combined fetch -> ready-to-train/predict feature dict
# --------------------------------------------------------------------------

async def get_environment_features(
    lat: float,
    lon: float,
    crop_type: str,
    as_of: Optional[date] = None,
) -> dict:
    """Single entry point. Returns a dict matching FEATURE_COLS in
    train_model.py / _build_feature_dict() in predict.py.

    Use this both in the live /predictions endpoint AND in a standalone
    script that loops over real district coordinates + dates to build a
    *real* flowering_data.csv (replacing generate_data.py's synthetic data)."""
    as_of = as_of or date.today()
    
    # Check cache first
    cache_key = f"{lat},{lon},{crop_type},{as_of}"
    cached = cache_get(cache_key, group="environment")
    if cached:
        return cached

    weather = await fetch_nasa_power_7d(lat, lon, as_of)
    try:
        ndvi = await fetch_ndvi(lat, lon, as_of)
    except Exception:
        ndvi = None  # EE not configured / no clear scenes in window -- caller should fallback
    bee_richness = await fetch_bee_richness(lat, lon)
    pollen = get_pollen_for_month(as_of.month)

    crop = crop_type.lower()
    result = {
        "temp_7d_mean": weather["temp_7d_mean"],
        "humidity": weather["humidity"],
        "rainfall_7d": weather["rainfall_7d"],
        "wind_speed": weather["wind_speed"],
        "ndvi": ndvi,
        "day_of_year": as_of.timetuple().tm_yday,
        "month": as_of.month,
        "crop_mustard": int(crop == "mustard"),
        "crop_sunflower": int(crop == "sunflower"),
        "crop_cotton": int(crop == "cotton"),
        "bee_richness": bee_richness,
        "pollen_tree": pollen["tree"],
        "pollen_grass": pollen["grass"],
        "pollen_weed": pollen["weed"],
        # extra, not a model feature but needed by gdd_model.py downstream
        "_t_max_7d": weather["t_max_7d"],
        "_t_min_7d": weather["t_min_7d"],
    }
    
    # Cache the result -- but only if NDVI succeeded. Caching a failed
    # (None) NDVI would poison the entry for its whole TTL and force the
    # caller's 0.65-style fallback even after Earth Engine recovers.
    if result["ndvi"] is not None:
        cache_set(cache_key, result, ttl=900, group="environment")

    return result


async def get_ndvi_with_cache(lat: float, lon: float, as_of: Optional[date] = None) -> Optional[float]:
    """Get NDVI with L1/L2 cache layer."""
    as_of = as_of or date.today()
    cache_key = f"ndvi,{lat},{lon},{as_of}"
    
    # L1/L2 cache check
    cached = cache_get(cache_key, group="ndvi")
    if cached is not None:
        return cached
    
    # Live fetch
    try:
        ndvi = await fetch_ndvi(lat, lon, as_of)
        if ndvi is not None:
            cache_set(cache_key, ndvi, ttl=900, group="ndvi")
        return ndvi
    except Exception:
        return None


async def get_bee_richness_with_cache(lat: float, lon: float, radius_km: float = 25) -> int:
    """Get bee richness with L1/L2 cache layer."""
    cache_key = f"bee_richness,{lat},{lon},{radius_km}"
    
    # L1/L2 cache check
    cached = cache_get(cache_key, group="bee_richness")
    if cached is not None:
        return cached
    
    # Live fetch
    try:
        richness = await fetch_bee_richness(lat, lon, radius_km)
        cache_set(cache_key, richness, ttl=900, group="bee_richness")
        return richness
    except Exception:
        return 0


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Check Earth Engine / NDVI connectivity for a coordinate."
    )
    parser.add_argument("--lat", type=float, default=19.9975)
    parser.add_argument("--lon", type=float, default=73.7898)
    parser.add_argument("--crop", type=str, default="Mustard")
    parser.add_argument("--force", action="store_true",
                        help="Bypass the EE init failure flag (retry after fixing auth)")
    args = parser.parse_args()

    async def _selfcheck():
        if args.force:
            global _ee_failed, _ee_initialized
            _ee_failed = False
            _ee_initialized = False
        from app.core.cache import cache_clear_all
        cache_clear_all()
        ndvi = await fetch_ndvi(args.lat, args.lon, date.today())
        print(f"NDVI for ({args.lat}, {args.lon}): {ndvi}")
        if ndvi is None:
            print("NDVI is None -> Earth Engine still not working (check auth / roles).")
        else:
            print("NDVI OK -> Earth Engine is configured and returning real data.")
        features = await get_environment_features(args.lat, args.lon, args.crop, as_of=date.today())
        print(f"ndvi in full feature dict: {features.get('ndvi')}")

    asyncio.run(_selfcheck())
