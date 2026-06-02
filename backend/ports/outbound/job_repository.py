"""Outbound port for job persistence.

Any adapter that stores and retrieves Job entities must satisfy this protocol.
Current implementation: PostgresJobRepository (SQLAlchemy + asyncpg).
"""

from typing import Protocol

from backend.domain.entities.job import Job


class IJobRepository(Protocol):
    """Contract for persisting and retrieving extraction jobs."""

    async def save(self, job: Job) -> None:
        """Persist a new job for the first time.

        Args:
            job: The job to insert. Raises if a job with the same id already exists.
        """
        ...

    async def get(self, job_id: str) -> Job | None:
        """Retrieve a job by its ID.

        Args:
            job_id: The job's unique identifier.

        Returns:
            The Job if found, None otherwise.
        """
        ...

    async def update(self, job: Job) -> None:
        """Persist changes to an existing job (status, progress, error, etc.).

        Args:
            job: The job with updated fields. Must already exist in the store.
        """
        ...
