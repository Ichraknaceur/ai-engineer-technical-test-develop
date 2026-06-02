"""Outbound port for the background task queue.

Any adapter that enqueues extraction jobs for async processing must satisfy
this protocol. Current implementation: CeleryTaskQueue (Celery + Redis).
"""

from typing import Protocol


class ITaskQueue(Protocol):
    """Contract for pushing extraction jobs onto the background queue."""

    def enqueue(self, job_id: str) -> None:
        """Push a job onto the queue so a worker picks it up asynchronously.

        The job must already be persisted (status=PENDING) before calling
        this method, so the worker can load it from the repository.

        Args:
            job_id: The unique identifier of the job to enqueue.
        """
        ...
