"""Application service for job lifecycle management.

JobService is the concrete implementation of the IJobService inbound port.
It orchestrates job creation, persistence, and queue dispatch without
knowing anything about HTTP, databases, or specific queue technologies.
"""

import uuid

from backend.domain.entities.job import Job
from backend.domain.value_objects.coordinates import Coordinates
from backend.ports.outbound.job_repository import IJobRepository
from backend.ports.outbound.task_queue import ITaskQueue


class JobService:
    """Handles the full lifecycle of an extraction job from submission to queuing.

    Dependencies are injected through the constructor so that any implementation
    satisfying IJobRepository and ITaskQueue can be swapped in (e.g. in tests).

    Args:
        job_repo: Adapter for persisting and retrieving Job entities.
        queue:    Adapter for dispatching jobs to the background worker.
    """

    def __init__(self, job_repo: IJobRepository, queue: ITaskQueue) -> None:
        self._job_repo = job_repo
        self._queue = queue

    async def submit(self, coordinates: Coordinates, max_usd_cost: float | None) -> Job:
        """Create a new job, persist it, and push it onto the task queue.

        Args:
            coordinates:  Geographic search area for the extraction.
            max_usd_cost: Hard cap on LLM spend. None means no limit.

        Returns:
            The newly created Job with status=PENDING.
        """
        job = Job(
            id=f"j_{uuid.uuid4().hex}",
            latitude=coordinates.latitude,
            longitude=coordinates.longitude,
            radius_km=coordinates.radius_km,
            max_usd_cost=max_usd_cost,
        )
        await self._job_repo.save(job)
        self._queue.enqueue(job.id)
        return job

    async def get(self, job_id: str) -> Job | None:
        """Retrieve the current state of a job by ID.

        Args:
            job_id: Unique identifier of the job.

        Returns:
            The Job if it exists, None otherwise.
        """
        return await self._job_repo.get(job_id)

    async def list(self, limit: int = 50) -> list[Job]:
        """Return the most recent jobs, newest first.

        Args:
            limit: Maximum number of jobs to return.

        Returns:
            A list of Job entities ordered by creation time descending.
        """
        return await self._job_repo.list(limit)
