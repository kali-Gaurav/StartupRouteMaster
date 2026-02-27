from celery import Celery
import os
from database.config import Config

# Initialize Celery with Redis broker and result backend
celery = Celery(
    "routemaster",
    broker=Config.REDIS_URL,
    backend=Config.REDIS_URL,
)

# Optional configuration settings for Celery
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.tasks.*": {"queue": "default"}
    }
)

# Discover tasks automatically if needed
celery.autodiscover_tasks(['tasks'])
