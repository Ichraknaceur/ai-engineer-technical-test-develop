"""Celery task definitions for the quarry extraction pipeline."""

import asyncio
import logging

from backend.infrastructure.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="process_job", bind=True, max_retries=3)
def process_job(self, job_id: str) -> None:
    """Run the full extraction pipeline for a given job.

    Bridges Celery's synchronous interface to the async pipeline via
    asyncio.run(). Creates a fresh DB engine per invocation to avoid
    event-loop conflicts after Celery's prefork worker forks.

    Args:
        job_id: Unique identifier of the job to process.
    """
    logger.info("Task process_job started for job_id=%s", job_id)
    try:
        asyncio.run(_run_pipeline(job_id))
    except Exception as exc:
        logger.exception("Task process_job failed for job_id=%s: %s", job_id, exc)
        raise self.retry(exc=exc, countdown=60) from exc


async def _run_pipeline(job_id: str) -> None:
    """Async pipeline entry point — creates a fresh DB engine to avoid loop conflicts."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.application.pipeline.pipeline import ExtractionPipeline
    from backend.config import settings
    from backend.infrastructure.db.repositories.job_repository import PostgresJobRepository
    from backend.infrastructure.db.repositories.site_repository import PostgresSiteRepository

    # Create a fresh engine — never reuse the module-level engine after a fork
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=5,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    try:
        async with session_factory() as session:
            pipeline = ExtractionPipeline(
                job_repo=PostgresJobRepository(session),
                site_repo=PostgresSiteRepository(session),
            )
            await pipeline.run(job_id)
    finally:
        await engine.dispose()
