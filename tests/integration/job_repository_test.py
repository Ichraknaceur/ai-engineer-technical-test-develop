"""Integration tests for PostgresJobRepository against a real PostgreSQL.

Verifies the full ORM round-trip: save → get → update → list.
"""

from datetime import UTC, datetime

import pytest

from backend.domain.entities.job import Job, JobStatus
from backend.infrastructure.db.repositories.job_repository import PostgresJobRepository

pytestmark = pytest.mark.integration


def _make_job(job_id: str = "j_int_1", **overrides) -> Job:
    defaults = dict(
        id=job_id,
        latitude=45.764,
        longitude=4.835,
        radius_km=30.0,
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    return Job(**{**defaults, **overrides})


async def test_save_and_get_round_trip(session):
    repo = PostgresJobRepository(session)
    job = _make_job()

    await repo.save(job)
    fetched = await repo.get(job.id)

    assert fetched is not None
    assert fetched.id == job.id
    assert fetched.latitude == pytest.approx(45.764)
    assert fetched.status == JobStatus.PENDING


async def test_get_returns_none_when_absent(session):
    repo = PostgresJobRepository(session)
    assert await repo.get("j_does_not_exist") is None


async def test_update_persists_status_and_progress(session):
    repo = PostgresJobRepository(session)
    job = _make_job()
    await repo.save(job)

    job.status = JobStatus.COMPLETED
    job.progress = 100
    job.sites_found = 7
    job.completed_at = datetime.now(UTC)
    await repo.update(job)

    fetched = await repo.get(job.id)
    assert fetched.status == JobStatus.COMPLETED
    assert fetched.progress == 100
    assert fetched.sites_found == 7
    assert fetched.completed_at is not None


async def test_list_returns_newest_first(session):
    repo = PostgresJobRepository(session)
    older = _make_job("j_old", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    newer = _make_job("j_new", created_at=datetime(2026, 6, 1, tzinfo=UTC))
    await repo.save(older)
    await repo.save(newer)

    jobs = await repo.list(limit=10)

    assert [j.id for j in jobs] == ["j_new", "j_old"]


async def test_list_respects_limit(session):
    repo = PostgresJobRepository(session)
    for i in range(5):
        await repo.save(_make_job(f"j_{i}", created_at=datetime(2026, 1, i + 1, tzinfo=UTC)))

    jobs = await repo.list(limit=2)
    assert len(jobs) == 2
