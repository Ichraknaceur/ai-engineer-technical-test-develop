"""DuckDuckGo web search adapter for enriching quarry candidates with source URLs.

For each QuarryCandidate discovered via Overpass, this module searches the web
for relevant pages (operator sites, industrial registries, news) and appends
the found URLs to the candidate's source_urls list.
"""

import logging

from duckduckgo_search import DDGS

from backend.domain.entities.quarry import QuarryCandidate

logger = logging.getLogger(__name__)

_MAX_RESULTS_PER_QUERY = 5
_SEARCH_REGION = "fr-fr"

# Domains that aggregate scraped data without adding value — skip them.
_BLOCKLIST = frozenset(
    [
        "facebook.com",
        "twitter.com",
        "linkedin.com",
        "instagram.com",
        "youtube.com",
        "wikipedia.org",
        "wikidata.org",
        "openstreetmap.org",
    ]
)


def _build_queries(candidate: QuarryCandidate) -> list[str]:
    """Build DuckDuckGo search queries for a quarry candidate.

    Generates up to two queries: one using the site name, one using the
    OSM operator tag or coordinates as a fallback.

    Args:
        candidate: The quarry candidate to build queries for.

    Returns:
        A list of query strings (1 or 2 items).
    """
    queries = []

    if candidate.name:
        queries.append(f'carrière "{candidate.name}"')

    # Coordinate-based fallback for unnamed candidates
    if not queries:
        queries.append(f"carrière extraction {candidate.latitude:.3f} {candidate.longitude:.3f}")

    return queries


def _is_blocked(url: str) -> bool:
    """Return True if the URL belongs to a blocked domain."""
    return any(domain in url for domain in _BLOCKLIST)


def _search_urls(query: str, max_results: int) -> list[str]:
    """Execute a DuckDuckGo text search and return result URLs.

    Args:
        query: The search query string.
        max_results: Maximum number of URLs to return.

    Returns:
        A list of URLs from the search results.
    """
    with DDGS() as ddgs:
        results = ddgs.text(
            query,
            region=_SEARCH_REGION,
            safesearch="off",
            max_results=max_results,
        )
    return [r["href"] for r in results if "href" in r]


class WebSearchEnricher:
    """Enriches QuarryCandidate objects with URLs found via DuckDuckGo.

    For each candidate, runs one or two targeted searches and appends any
    new URLs (not already in source_urls, not in the blocklist) to the
    candidate's source_urls list.

    Args:
        max_results: Maximum URLs to collect per query (default 5).
    """

    def __init__(self, max_results: int = _MAX_RESULTS_PER_QUERY) -> None:
        self._max_results = max_results

    async def enrich(self, candidate: QuarryCandidate) -> QuarryCandidate:
        """Search the web for URLs relevant to the candidate and append them.

        Modifies the candidate in-place and also returns it for convenience.

        Args:
            candidate: The quarry candidate to enrich.

        Returns:
            The same candidate with source_urls updated.
        """
        queries = _build_queries(candidate)
        existing = set(candidate.source_urls)
        new_urls: list[str] = []

        for query in queries:
            try:
                urls = _search_urls(query, self._max_results)
                for url in urls:
                    if url not in existing and not _is_blocked(url):
                        new_urls.append(url)
                        existing.add(url)
            except Exception as exc:
                logger.warning("DuckDuckGo search failed for query %r: %s", query, exc)

        if new_urls:
            candidate.source_urls.extend(new_urls)
            logger.info(
                "WebSearch added %d URL(s) for candidate %r",
                len(new_urls),
                candidate.name,
            )
        else:
            logger.debug("WebSearch found no new URLs for candidate %r", candidate.name)

        return candidate

    async def enrich_all(self, candidates: list[QuarryCandidate]) -> list[QuarryCandidate]:
        """Enrich a list of candidates sequentially.

        Sequential (not concurrent) to stay polite with DuckDuckGo's rate limits.

        Args:
            candidates: The list of candidates to enrich.

        Returns:
            The same list with source_urls updated on each candidate.
        """
        for candidate in candidates:
            await self.enrich(candidate)
        return candidates
