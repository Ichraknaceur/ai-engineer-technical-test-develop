"""Pipeline integration test endpoint.

Chains DiscoveryStep → Scraper → LLMExtractor → ReconcilerStep on a single
candidate to validate the full pipeline without running a real job.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.application.pipeline.discovery import DiscoveryStep
from backend.application.pipeline.reconciler import ReconcilerStep
from backend.domain.value_objects.coordinates import Coordinates
from backend.infrastructure.llm.llm_extractor import LLMExtractor
from backend.infrastructure.scraper.http_scraper import HttpScraper

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline-test"])


class PipelineTestResponse(BaseModel):
    """Response for GET /api/pipeline/test."""

    coordinates: dict
    candidates_found: int
    candidate_name: str | None
    source_urls: list[str]
    pages_scraped: int
    pages_with_errors: int
    reconciled_extraction: dict
    reconciliations: list[dict]
    total_tokens: int
    total_usd_cost: float


@router.get("/pipeline/test", response_model=PipelineTestResponse)
async def test_pipeline(
    lat: Annotated[float, Query(ge=-90, le=90, description="Centre latitude")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Centre longitude")],
    radius_km: Annotated[float, Query(gt=0, le=500, description="Search radius in km")],
    max_urls: Annotated[int, Query(ge=1, le=5, description="Max URLs to scrape per candidate")] = 2,
) -> PipelineTestResponse:
    """Run Discovery → Scrape → Extract → Reconcile on the first candidate found.

    Tests the full pipeline steps end-to-end on a single quarry candidate.
    Does NOT persist to the database — safe to call repeatedly for testing.

    Example:
        GET /api/pipeline/test?lat=45.764&lon=4.835&radius_km=30
    """
    coordinates = Coordinates(latitude=lat, longitude=lon, radius_km=radius_km)

    # Step 1 — Discovery
    discovery = DiscoveryStep()
    candidates = await discovery.run(coordinates)

    if not candidates:
        return PipelineTestResponse(
            coordinates={"latitude": lat, "longitude": lon, "radius_km": radius_km},
            candidates_found=0,
            candidate_name=None,
            source_urls=[],
            pages_scraped=0,
            pages_with_errors=0,
            reconciled_extraction={},
            reconciliations=[],
            total_tokens=0,
            total_usd_cost=0.0,
        )

    # Take the first candidate with URLs (or just the first)
    candidate = next((c for c in candidates if c.source_urls), candidates[0])
    urls = candidate.source_urls[:max_urls]

    # Step 2 — Scrape
    scraper = HttpScraper()
    pages = []
    for url in urls:
        page = await scraper.fetch(url)
        pages.append(page)

    pages_with_errors = sum(1 for p in pages if p.error)

    # Step 3 — LLM Extraction
    extractor = LLMExtractor()
    extractions = []
    sources = []
    total_tokens = 0
    total_cost = 0.0

    for page in pages:
        extraction = await extractor.extract(page)
        metrics = extraction.pop("_metrics", {})
        total_tokens += metrics.get("tokens_in", 0) + metrics.get("tokens_out", 0)
        total_cost += metrics.get("usd_cost", 0.0)
        extractions.append(extraction)
        sources.append(
            {
                "source_id": page.source_id,
                "url": page.url,
                "fetched_at": page.fetched_at.isoformat(),
                "content_hash": page.content_hash,
                "trust_tier": page.trust_tier,
            }
        )

    # Step 4 — Reconciliation
    reconciler = ReconcilerStep()
    result = reconciler.run(extractions, sources)

    return PipelineTestResponse(
        coordinates={"latitude": lat, "longitude": lon, "radius_km": radius_km},
        candidates_found=len(candidates),
        candidate_name=candidate.name,
        source_urls=urls,
        pages_scraped=len(pages),
        pages_with_errors=pages_with_errors,
        reconciled_extraction=result["extraction"],
        reconciliations=result["reconciliations"],
        total_tokens=total_tokens,
        total_usd_cost=round(total_cost, 4),
    )
