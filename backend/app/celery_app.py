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
    # A crashed/stuck ingestion task is killed and redelivered rather than
    # leaving a document wedged. (A periodic reaper for orphaned 'queued'
    # docs is a later operational add — see docs/step-06.)
    task_acks_late=True,
    task_time_limit=600,        # hard kill after 10 min
    task_soft_time_limit=540,   # raise SoftTimeLimitExceeded at 9 min
)

# Ensure task modules are imported so Celery registers them.
celery_app.autodiscover_tasks(["app.ingestion"])
