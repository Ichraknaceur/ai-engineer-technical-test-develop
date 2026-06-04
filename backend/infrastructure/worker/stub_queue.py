"""No-op task queue used until Celery is wired up in task #10.

The stub satisfies ITaskQueue so JobService can be exercised end-to-end
without a running Redis/Celery worker. Jobs are accepted but not processed.
"""

import logging

logger = logging.getLogger(__name__)


class StubTaskQueue:
    """Accepts enqueue calls and logs them; does not dispatch to any worker."""

    def enqueue(self, job_id: str) -> None:
        logger.info("StubTaskQueue: job %s accepted (not dispatched)", job_id)
