"""Job entity representing a single quarry extraction request and its lifecycle."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class JobStatus(StrEnum):
    """Lifecycle states of an extraction job.

    Transitions: PENDING → RUNNING → COMPLETED
                                   ↘ FAILED
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """An extraction job submitted by a user.

    Tracks progress from submission through to completion or failure.
    The worker updates `status`, `progress`, and `status_message` as it runs.

    Attributes:
        id:             Unique job identifier (prefixed with "j_").
        latitude:       Centre latitude of the search area.
        longitude:      Centre longitude of the search area.
        radius_km:      Search radius in kilometres.
        status:         Current lifecycle state.
        progress:       Completion percentage in [0, 100].
        status_message: Human-readable description of the current pipeline stage.
        sites_found:    Number of quarry sites discovered so far.
        max_usd_cost:   Optional hard cap on total LLM spend for this job.
        error:          Error message populated when status is FAILED.
        created_at:     UTC timestamp when the job was created.
        completed_at:   UTC timestamp when the job reached COMPLETED or FAILED.
    """

    id: str
    latitude: float
    longitude: float
    radius_km: float
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    status_message: str = ""
    sites_found: int = 0
    max_usd_cost: float | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
