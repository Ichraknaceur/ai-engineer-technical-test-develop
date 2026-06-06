"""Celery-backed task queue adapter for ITaskQueue."""

import logging

from backend.infrastructure.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


class CeleryTaskQueue:
    """Dispatches jobs to the Celery worker via the process_job task."""

    def enqueue(self, job_id: str) -> None:
        """Send job_id to the Celery worker asynchronously.

        Args:
            job_id: Unique identifier of the job to process.
        """
        celery_app.send_task("process_job", args=[job_id])
        logger.info("Enqueued job %s to Celery", job_id)
