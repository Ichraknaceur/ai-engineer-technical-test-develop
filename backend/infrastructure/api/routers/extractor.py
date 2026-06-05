"""LLM extractor debug endpoint — scrape a URL and run field extraction."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.infrastructure.llm.llm_extractor import LLMExtractor
from backend.infrastructure.scraper.http_scraper import HttpScraper

router = APIRouter(tags=["extractor"])


class ExtractResponse(BaseModel):
    """Response for GET /api/extract."""

    url: str
    source_id: str
    trust_tier: str
    word_count: int
    scrape_error: str | None
    extraction: dict
    metrics: dict


@router.get("/extract", response_model=ExtractResponse)
async def extract_url(
    url: Annotated[str, Query(description="URL to scrape and extract quarry data from")],
) -> ExtractResponse:
    """Scrape a URL and run LLM extraction on its content.

    Runs the full scrape → extract pipeline on a single URL.
    Useful for validating the prompt, checking the output schema,
    and estimating token cost before running a full job.

    Example:
        GET /api/extract?url=https://www.carriere-example.fr
    """
    scraper = HttpScraper()
    page = await scraper.fetch(url)

    extractor = LLMExtractor()
    extraction = await extractor.extract(page)

    metrics = extraction.pop("_metrics", {})

    return ExtractResponse(
        url=page.url,
        source_id=page.source_id,
        trust_tier=page.trust_tier,
        word_count=len(page.cleaned_text.split()) if page.cleaned_text else 0,
        scrape_error=page.error,
        extraction=extraction,
        metrics=metrics,
    )
