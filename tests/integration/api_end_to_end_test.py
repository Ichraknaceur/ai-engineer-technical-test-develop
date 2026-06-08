"""End-to-end API integration tests: FastAPI + real PostgreSQL.

The HTTP layer, application services, repositories, and database all run for
real. Only the task queue is replaced with a no-op so jobs are not dispatched
to a Celery worker during the test.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.services.job_service import JobService
from backend.infrastructure.api.dependencies.db import get_session
from backend.infrastructure.api.dependencies.services import get_job_service
from backend.infrastructure.api.main import app
from backend.infrastructure.db.repositories.job_repository import PostgresJobRepository

pytestmark = pytest.mark.integration


class _NoopQueue:
    """Task queue stub — accepts enqueue calls without dispatching."""

    def enqueue(self, job_id: str) -> None:
        pass


@pytest.fixture
def client(engine, session):
    """An httpx client wired to the app with the test DB session injected."""
    factory_session = session

    async def _override_session():
        yield factory_session

    def _override_job_service():
        return JobService(job_repo=PostgresJobRepository(factory_session), queue=_NoopQueue())

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_job_service] = _override_job_service

    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")

    app.dependency_overrides.clear()


async def test_create_then_get_job(client):
    async with client:
        resp = await client.post(
            "/api/jobs",
            json={"latitude": 45.764, "longitude": 4.835, "radius_km": 30},
        )
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        got = await client.get(f"/api/jobs/{job_id}")
        assert got.status_code == 200
        assert got.json()["id"] == job_id
        assert got.json()["status"] == "pending"


async def test_job_appears_in_list(client):
    async with client:
        await client.post(
            "/api/jobs",
            json={"latitude": 48.85, "longitude": 2.35, "radius_km": 10},
        )
        listed = await client.get("/api/jobs")
        assert listed.status_code == 200
        assert len(listed.json()) >= 1


async def test_get_missing_job_returns_404(client):
    async with client:
        resp = await client.get("/api/jobs/j_nope")
        assert resp.status_code == 404


async def test_create_job_validation_error(client):
    async with client:
        resp = await client.post(
            "/api/jobs",
            json={"latitude": 999, "longitude": 2.35, "radius_km": 10},
        )
        assert resp.status_code == 422


async def test_sites_list_empty_initially(client):
    async with client:
        resp = await client.get("/api/sites")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []
