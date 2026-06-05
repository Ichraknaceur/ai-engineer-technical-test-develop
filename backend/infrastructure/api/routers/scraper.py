"""Scraper debug endpoint — test the HTTP scraper without running the full pipeline."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.infrastructure.scraper.http_scraper import HttpScraper

router = APIRouter(tags=["scraper"])


class ScrapeResponse(BaseModel):
    """Response for GET /api/scrape."""

    url: str
    source_id: str
    fetched_at: str
    content_hash: str
    trust_tier: str
    word_count: int
    preview: str
    error: str | None


@router.get("/scrape", response_model=ScrapeResponse)
async def scrape_url(
    url: Annotated[str, Query(description="URL to fetch and clean")],
) -> ScrapeResponse:
    """Fetch a URL through the polite scraper and return the cleaned content.

    Runs the full scraping pipeline on a single URL:
    robots.txt check, delay, fetch, HTML cleaning, trust tier classification.

    Example:
        GET /api/scrape?url=https://www.example.com
    """
    scraper = HttpScraper()
    page = await scraper.fetch(url)

    preview = page.cleaned_text[:500] + "..." if len(page.cleaned_text) > 500 else page.cleaned_text

    return ScrapeResponse(
        url=page.url,
        source_id=page.source_id,
        fetched_at=page.fetched_at.isoformat(),
        content_hash=page.content_hash,
        trust_tier=page.trust_tier,
        word_count=len(page.cleaned_text.split()) if page.cleaned_text else 0,
        preview=preview,
        error=page.error,
    )
