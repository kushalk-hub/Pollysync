import logging
from app.celery_app import celery_app
from app.core.cache import cache_delete_group

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.data_refresh.refresh_all_farms", bind=True, max_retries=3)
def refresh_all_farms(self):
    """Refresh all farm data (weather, NDVI, bees) every 30 minutes."""
    try:
        refresh_weather_batch()
        refresh_ndvi_batch()
        refresh_bees_batch()
        logger.info("All farm data refreshed successfully")
    except Exception as exc:
        logger.error(f"Refresh failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


def refresh_weather_batch():
    """Refresh weather data for all active farms."""
    import asyncio
    from app.services.weather_service import fetch_weather, cache_weather
    from app.database import SessionLocal
    from app.models.farm import Farm

    db = SessionLocal()
    try:
        farms = db.query(Farm).all()

        async def _one(f):
            try:
                weather_data = await fetch_weather(f.location_lat, f.location_lng)
                return f, weather_data
            except Exception as e:
                logger.warning(f"Weather refresh failed for farm {f.id}: {e}")
                return f, None

        async def _run_all():
            return await asyncio.gather(*(_one(f) for f in farms))

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(_run_all())
        finally:
            loop.close()

        for f, weather_data in results:
            if weather_data is None:
                continue
            cache_weather(str(f.id), weather_data, db)
    finally:
        db.close()

    # Invalidate L1/L2 cache
    cache_delete_group("weather")


def refresh_ndvi_batch():
    """Refresh NDVI data for all active farms."""
    import asyncio
    from datetime import date
    from app.services.environment_service import fetch_ndvi
    from app.core.cache import cache_set
    from app.database import SessionLocal
    from app.models.farm import Farm

    db = SessionLocal()
    try:
        farms = db.query(Farm).all()

        async def _one(f):
            try:
                ndvi = await fetch_ndvi(f.location_lat, f.location_lng, date.today())
                return f, ndvi
            except Exception as e:
                logger.warning(f"NDVI refresh failed for farm {f.id}: {e}")
                return f, None

        async def _run_all():
            return await asyncio.gather(*(_one(f) for f in farms))

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(_run_all())
        finally:
            loop.close()

        for f, ndvi in results:
            if ndvi is None:
                continue
            cache_key = f"ndvi,{f.location_lat},{f.location_lng},{date.today()}"
            cache_set(cache_key, ndvi, ttl=300, group="ndvi")
    finally:
        db.close()

    cache_delete_group("ndvi")


def refresh_bees_batch():
    """Refresh bee data for all active farms."""
    import asyncio
    from app.services.bee_service import fetch_bees
    from app.core.cache import cache_set
    from app.database import SessionLocal
    from app.models.farm import Farm

    db = SessionLocal()
    try:
        farms = db.query(Farm).all()

        async def _one(f):
            try:
                occurrences = await fetch_bees(f.location_lat, f.location_lng)
                return f, occurrences
            except Exception as e:
                logger.warning(f"Bee refresh failed for farm {f.id}: {e}")
                return f, None

        async def _run_all():
            return await asyncio.gather(*(_one(f) for f in farms))

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(_run_all())
        finally:
            loop.close()

        for f, occurrences in results:
            if not occurrences:
                continue
            species = list({occ["species"] for occ in occurrences})
            result = {
                "species": species,
                "richness": len(species),
                "source": "refresh",
            }
            cache_key = f"{f.location_lat},{f.location_lng}"
            cache_set(cache_key, result, ttl=300, group="bees")
    finally:
        db.close()

    cache_delete_group("bees")
