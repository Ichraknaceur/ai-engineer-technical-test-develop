"""Celery task definitions for the quarry extraction pipeline."""

import logging

from backend.infrastructure.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="process_job", bind=True, max_retries=3)
def process_job(self, job_id: str) -> None:
    """Run the full extraction pipeline for a given job.

    Args:
        job_id: Unique identifier of the job to process.
    """
    logger.info("Task process_job received job_id=%s", job_id)
