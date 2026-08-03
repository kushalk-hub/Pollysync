from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "polisync",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "refresh-farm-data": {
            "task": "app.tasks.data_refresh.refresh_all_farms",
            "schedule": 1800.0,  # Every 30 minutes
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
