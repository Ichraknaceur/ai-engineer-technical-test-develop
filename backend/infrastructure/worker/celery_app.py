"""Celery application instance.

The broker and result backend are both Redis.
Tasks are imported via the `include` list so they are auto-discovered.
"""

from celery import Celery

from backend.config import settings

celery_app = Celery(
    "quarry",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["backend.infrastructure.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)
