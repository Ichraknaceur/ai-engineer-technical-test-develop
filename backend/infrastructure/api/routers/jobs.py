"""Jobs router — submit extraction jobs and poll their status."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.domain.entities.job import JobStatus
from backend.domain.value_objects.coordinates import Coordinates
from backend.infrastructure.api.dependencies.services import JobServiceDep

router = APIRouter(tags=["jobs"])


class JobCreateRequest(BaseModel):
    """Body for POST /api/jobs."""

    latitude: float = Field(..., ge=-90, le=90, description="Centre latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Centre longitude")
    radius_km: float = Field(..., gt=0, le=500, description="Search radius in km")
    max_usd_cost: float | None = Field(None, gt=0, description="Optional LLM spend cap in USD")


class JobResponse(BaseModel):
    """Representation of a job returned by the API."""

    id: str
    latitude: float
    longitude: float
    radius_km: float
    status: JobStatus
    progress: int
    status_message: str
    sites_found: int
    max_usd_cost: float | None
    error: str | None
    created_at: str
    completed_at: str | None

    model_config = {"from_attributes": True}


def _job_response(job) -> JobResponse:  # noqa: ANN001
    return JobResponse(
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
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(body: JobCreateRequest, service: JobServiceDep) -> JobResponse:
    """Submit a new extraction job.

    Creates a job in PENDING status and pushes it onto the background queue.
    Poll GET /api/jobs/{job_id} to track progress.
    """
    coordinates = Coordinates(
        latitude=body.latitude,
        longitude=body.longitude,
        radius_km=body.radius_km,
    )
    job = await service.submit(coordinates, body.max_usd_cost)
    return _job_response(job)


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    service: JobServiceDep,
    limit: Annotated[int, Query(ge=1, le=100, description="Max jobs to return")] = 50,
) -> list[JobResponse]:
    """List recent extraction jobs, newest first."""
    jobs = await service.list(limit)
    return [_job_response(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, service: JobServiceDep) -> JobResponse:
    """Retrieve the current state of a job.

    Returns 404 if no job with the given ID exists.
    """
    job = await service.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_response(job)
