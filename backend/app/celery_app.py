"""Celery application for async ingestion jobs."""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "rag",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

# Ensure task modules are imported so Celery registers them.
celery_app.autodiscover_tasks(["app.ingestion"])
