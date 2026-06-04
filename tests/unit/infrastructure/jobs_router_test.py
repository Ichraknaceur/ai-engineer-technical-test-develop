"""Unit tests for POST /api/jobs and GET /api/jobs/{job_id}.

The application service is replaced with an in-memory fake so these tests
run without a database or task queue.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.domain.entities.job import Job, JobStatus
from backend.infrastructure.api.dependencies.services import get_job_service
from backend.infrastructure.api.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_job(**overrides) -> Job:
    defaults = dict(
        id="j_abc123",
        latitude=45.75,
        longitude=4.83,
        radius_km=10.0,
        status=JobStatus.PENDING,
        progress=0,
        status_message="",
        sites_found=0,
        max_usd_cost=None,
        error=None,
        created_at=_NOW,
        completed_at=None,
    )
    return Job(**{**defaults, **overrides})


def _make_client(mock_service) -> TestClient:
    app.dependency_overrides[get_job_service] = lambda: mock_service
    client = TestClient(app, raise_server_exceptions=False)
    return client


# ---------------------------------------------------------------------------
# POST /api/jobs
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_returns_201_and_job_payload(self):
        job = _make_job()
        svc = AsyncMock()
        svc.submit = AsyncMock(return_value=job)
        client = _make_client(svc)

        resp = client.post(
            "/api/jobs",
            json={"latitude": 45.75, "longitude": 4.83, "radius_km": 10.0},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "j_abc123"
        assert data["status"] == "pending"
        assert data["progress"] == 0

    def test_passes_coordinates_and_budget_to_service(self):
        job = _make_job(max_usd_cost=5.0)
        svc = AsyncMock()
        svc.submit = AsyncMock(return_value=job)
        client = _make_client(svc)

        client.post(
            "/api/jobs",
            json={"latitude": 48.86, "longitude": 2.35, "radius_km": 25.0, "max_usd_cost": 5.0},
        )

        svc.submit.assert_awaited_once()
        coords, budget = svc.submit.call_args.args
        assert coords.latitude == pytest.approx(48.86)
        assert coords.longitude == pytest.approx(2.35)
        assert coords.radius_km == pytest.approx(25.0)
        assert budget == pytest.approx(5.0)

    def test_rejects_latitude_out_of_range(self):
        svc = AsyncMock()
        client = _make_client(svc)
        resp = client.post(
            "/api/jobs",
            json={"latitude": 200, "longitude": 0, "radius_km": 10},
        )
        assert resp.status_code == 422

    def test_rejects_negative_radius(self):
        svc = AsyncMock()
        client = _make_client(svc)
        resp = client.post(
            "/api/jobs",
            json={"latitude": 45.0, "longitude": 5.0, "radius_km": -5},
        )
        assert resp.status_code == 422

    def test_rejects_zero_radius(self):
        svc = AsyncMock()
        client = _make_client(svc)
        resp = client.post(
            "/api/jobs",
            json={"latitude": 45.0, "longitude": 5.0, "radius_km": 0},
        )
        assert resp.status_code == 422

    def test_rejects_radius_above_500(self):
        svc = AsyncMock()
        client = _make_client(svc)
        resp = client.post(
            "/api/jobs",
            json={"latitude": 45.0, "longitude": 5.0, "radius_km": 501},
        )
        assert resp.status_code == 422

    def test_max_usd_cost_is_optional(self):
        job = _make_job()
        svc = AsyncMock()
        svc.submit = AsyncMock(return_value=job)
        client = _make_client(svc)

        resp = client.post(
            "/api/jobs",
            json={"latitude": 45.0, "longitude": 5.0, "radius_km": 10},
        )

        assert resp.status_code == 201
        _, budget = svc.submit.call_args.args
        assert budget is None


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------


class TestGetJob:
    def test_returns_job_when_found(self):
        job = _make_job(status=JobStatus.RUNNING, progress=42, status_message="Scraping...")
        svc = AsyncMock()
        svc.get = AsyncMock(return_value=job)
        client = _make_client(svc)

        resp = client.get("/api/jobs/j_abc123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "j_abc123"
        assert data["status"] == "running"
        assert data["progress"] == 42
        assert data["status_message"] == "Scraping..."

    def test_returns_404_when_not_found(self):
        svc = AsyncMock()
        svc.get = AsyncMock(return_value=None)
        client = _make_client(svc)

        resp = client.get("/api/jobs/j_notexist")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Job not found"

    def test_completed_job_has_completed_at(self):
        completed = datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC)
        job = _make_job(
            status=JobStatus.COMPLETED,
            progress=100,
            sites_found=7,
            completed_at=completed,
        )
        svc = AsyncMock()
        svc.get = AsyncMock(return_value=job)
        client = _make_client(svc)

        resp = client.get("/api/jobs/j_abc123")

        data = resp.json()
        assert data["status"] == "completed"
        assert data["sites_found"] == 7
        assert data["completed_at"] is not None

    def test_failed_job_has_error(self):
        job = _make_job(status=JobStatus.FAILED, error="Overpass timeout")
        svc = AsyncMock()
        svc.get = AsyncMock(return_value=job)
        client = _make_client(svc)

        resp = client.get("/api/jobs/j_abc123")

        data = resp.json()
        assert data["status"] == "failed"
        assert data["error"] == "Overpass timeout"
