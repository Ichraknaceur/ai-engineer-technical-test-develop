"""Sites router — query enriched quarry records."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.infrastructure.api.dependencies.services import SiteServiceDep
from backend.infrastructure.api.utils.pagination import PaginationParams

router = APIRouter(tags=["sites"])


class SiteRecordResponse(dict):
    """The full QuarryRecord JSON payload (schema v2.0.0)."""


def _site_response(record) -> dict:  # noqa: ANN001
    return {
        "site_id": record.site_id,
        "schema_version": record.schema_version,
        "input": record.input,
        "extraction": record.extraction,
        "provenance": record.provenance,
        "metrics": record.metrics,
        "run_metadata": record.run_metadata,
    }


@router.get("/sites")
async def list_sites(
    service: SiteServiceDep,
    pagination: Annotated[PaginationParams, Depends()],
    q: Annotated[str | None, Query(description="Text search on official name")] = None,
    status: Annotated[str | None, Query(description="Filter by operational_status")] = None,
) -> dict:
    """List quarry site records with optional filtering and pagination.

    Query parameters:
    - **q**: substring match on the official name (case-insensitive)
    - **status**: exact match on operational_status (e.g. `active`, `inactive`)
    - **page**: 1-based page number (default 1)
    - **page_size**: results per page, 1–100 (default 20)
    """
    total, records = await service.list(
        q=q,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return {
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
        "items": [_site_response(r) for r in records],
    }


@router.get("/sites/{site_id}")
async def get_site(site_id: str, service: SiteServiceDep) -> dict:
    """Retrieve a single quarry record by its stable site ID.

    Returns 404 if no record with the given site_id exists.
    """
    record = await service.get(site_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return _site_response(record)
