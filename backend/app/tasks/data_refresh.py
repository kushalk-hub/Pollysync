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
        for farm in farms:
            try:
                # Use sync wrapper for async fetch
                loop = asyncio.new_event_loop()
                weather_data = loop.run_until_complete(
                    fetch_weather(farm.latitude, farm.longitude)
                )
                loop.close()
                
                # Cache in DB
                cache_weather(str(farm.id), weather_data, db)
            except Exception as e:
                logger.warning(f"Weather refresh failed for farm {farm.id}: {e}")
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
        for farm in farms:
            try:
                loop = asyncio.new_event_loop()
                ndvi = loop.run_until_complete(
                    fetch_ndvi(farm.latitude, farm.longitude, date.today())
                )
                loop.close()
                
                if ndvi is not None:
                    cache_key = f"ndvi,{farm.latitude},{farm.longitude},{date.today()}"
                    cache_set(cache_key, ndvi, ttl=900, group="ndvi")
            except Exception as e:
                logger.warning(f"NDVI refresh failed for farm {farm.id}: {e}")
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
        for farm in farms:
            try:
                loop = asyncio.new_event_loop()
                occurrences = loop.run_until_complete(
                    fetch_bees(farm.latitude, farm.longitude)
                )
                loop.close()
                
                species = list({occ["species"] for occ in occurrences})
                result = {
                    "species": species,
                    "richness": len(species),
                    "source": "refresh",
                }
                cache_key = f"{farm.latitude},{farm.longitude}"
                cache_set(cache_key, result, ttl=900, group="bees")
            except Exception as e:
                logger.warning(f"Bee refresh failed for farm {farm.id}: {e}")
    finally:
        db.close()
    
    cache_delete_group("bees")
