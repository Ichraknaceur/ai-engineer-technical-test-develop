"""Inbound port exposing job management operations to the API layer.

The FastAPI routers depend on this protocol, not on the concrete JobService,
keeping the infrastructure layer decoupled from the application layer.
"""

from typing import Protocol

from backend.domain.entities.job import Job
from backend.domain.value_objects.coordinates import Coordinates


class IJobService(Protocol):
    """Contract for submitting and querying extraction jobs."""

    async def submit(self, coordinates: Coordinates, max_usd_cost: float | None) -> Job:
        """Create a new job, persist it, and enqueue it for processing.

        Args:
            coordinates:  Geographic search area.
            max_usd_cost: Optional cap on total LLM spend. None means no limit.

        Returns:
            The newly created Job with status=PENDING.
        """
        ...

    async def get(self, job_id: str) -> Job | None:
        """Retrieve the current state of a job.

        Args:
            job_id: The job's unique identifier.

        Returns:
            The Job if found, None otherwise.
        """
        ...

    async def list(self, limit: int = 50) -> list[Job]:
        """Return the most recent jobs, newest first.

        Args:
            limit: Maximum number of jobs to return.

        Returns:
            A list of Job entities ordered by creation time descending.
        """
        ...
