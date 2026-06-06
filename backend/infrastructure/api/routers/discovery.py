"""Discovery debug endpoint — test Overpass API without running the full pipeline."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.domain.value_objects.coordinates import Coordinates
from backend.infrastructure.discovery.overpass import OverpassDiscoverer
from backend.infrastructure.discovery.web_search import WebSearchEnricher

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
    enriched: int
    candidates: list[CandidateResponse]


@router.get("/discovery", response_model=DiscoveryResponse)
async def discover_quarries(
    lat: Annotated[float, Query(ge=-90, le=90, description="Centre latitude")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Centre longitude")],
    radius_km: Annotated[float, Query(gt=0, le=500, description="Search radius in km")],
    enrich: Annotated[bool, Query(description="Run web search to add source URLs")] = False,
    limit: Annotated[int, Query(ge=1, le=50, description="Max candidates to enrich")] = 10,
) -> DiscoveryResponse:
    """Query Overpass and optionally enrich candidates with web search URLs.

    No scraping, no LLM extraction — useful for validating that discovery and
    web search return relevant results before running a full job.

    - ``enrich=false`` (default): raw Overpass candidates only (fast).
    - ``enrich=true``: also run DuckDuckGo web search on the first ``limit``
      candidates and show their relevant source URLs.

    Example:
        GET /api/discovery?lat=45.764&lon=4.835&radius_km=30&enrich=true&limit=5
    """
    coordinates = Coordinates(latitude=lat, longitude=lon, radius_km=radius_km)
    discoverer = OverpassDiscoverer()
    candidates = await discoverer.discover(coordinates)

    enriched_count = 0
    shown = candidates

    if enrich:
        shown = candidates[:limit]
        enricher = WebSearchEnricher()
        await enricher.enrich_all(shown)
        enriched_count = sum(1 for c in shown if c.source_urls)

    return DiscoveryResponse(
        total=len(candidates),
        enriched=enriched_count,
        candidates=[
            CandidateResponse(
                name=c.name,
                latitude=c.latitude,
                longitude=c.longitude,
                osm_id=c.osm_id,
                source_urls=c.source_urls,
            )
            for c in shown
        ],
    )
