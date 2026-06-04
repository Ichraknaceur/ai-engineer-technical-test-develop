"""Discovery debug endpoint — test Overpass API without running the full pipeline."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.domain.value_objects.coordinates import Coordinates
from backend.infrastructure.discovery.overpass import OverpassDiscoverer

router = APIRouter(tags=["discovery"])


class CandidateResponse(BaseModel):
    """A quarry candidate returned by the discovery step."""

    name: str | None
    latitude: float
    longitude: float
    osm_id: str | None
    source_urls: list[str]


class DiscoveryResponse(BaseModel):
    """Response for GET /api/discovery."""

    total: int
    candidates: list[CandidateResponse]


@router.get("/discovery", response_model=DiscoveryResponse)
async def discover_quarries(
    lat: Annotated[float, Query(ge=-90, le=90, description="Centre latitude")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Centre longitude")],
    radius_km: Annotated[float, Query(gt=0, le=500, description="Search radius in km")],
) -> DiscoveryResponse:
    """Query Overpass API and return raw quarry candidates for a given area.

    This endpoint runs only the discovery stage — no scraping, no LLM extraction.
    Useful for validating that Overpass returns the expected quarries before
    running a full extraction job.

    Example:
        GET /api/discovery?lat=48.8566&lon=2.3522&radius_km=50
    """
    coordinates = Coordinates(latitude=lat, longitude=lon, radius_km=radius_km)
    discoverer = OverpassDiscoverer()
    candidates = await discoverer.discover(coordinates)

    return DiscoveryResponse(
        total=len(candidates),
        candidates=[
            CandidateResponse(
                name=c.name,
                latitude=c.latitude,
                longitude=c.longitude,
                osm_id=c.osm_id,
                source_urls=c.source_urls,
            )
            for c in candidates
        ],
    )
