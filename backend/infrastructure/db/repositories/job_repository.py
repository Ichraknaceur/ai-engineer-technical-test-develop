"""PostgreSQL implementation of IJobRepository using SQLAlchemy async."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.job import Job, JobStatus
from backend.infrastructure.db.models import JobModel


class PostgresJobRepository:
    """Reads and writes Job entities to the PostgreSQL jobs table.

    Args:
        session: An active async SQLAlchemy session (injected per-request).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: Job) -> None:
        """Insert a new job row."""
        model = JobModel(
            id=job.id,
            latitude=job.latitude,
            longitude=job.longitude,
            radius_km=job.radius_km,
            status=job.status,
            progress=job.progress,
            status_message=job.status_message,
            sites_found=job.sites_found,
            max_usd_cost=job.max_usd_cost,
            error=job.error,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )
        self._session.add(model)
        await self._session.commit()

    async def get(self, job_id: str) -> Job | None:
        """Return the Job for job_id, or None if not found."""
        result = await self._session.execute(select(JobModel).where(JobModel.id == job_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def update(self, job: Job) -> None:
        """Overwrite all mutable fields on an existing job row."""
        result = await self._session.execute(select(JobModel).where(JobModel.id == job.id))
        model = result.scalar_one_or_none()
        if model is None:
            return
        model.status = job.status
        model.progress = job.progress
        model.status_message = job.status_message
        model.sites_found = job.sites_found
        model.error = job.error
        model.completed_at = job.completed_at
        await self._session.commit()

    @staticmethod
    def _to_entity(model: JobModel) -> Job:
        return Job(
            id=model.id,
            latitude=model.latitude,
            longitude=model.longitude,
            radius_km=model.radius_km,
            status=JobStatus(model.status),
            progress=model.progress,
            status_message=model.status_message,
            sites_found=model.sites_found,
            max_usd_cost=model.max_usd_cost,
            error=model.error,
            created_at=model.created_at,
            completed_at=model.completed_at,
        )
