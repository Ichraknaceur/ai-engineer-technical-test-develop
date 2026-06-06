"""DuckDuckGo web search adapter for enriching quarry candidates with source URLs.

For each QuarryCandidate discovered via Overpass, this module searches the web
for relevant pages (operator sites, industrial registries) and appends the
found URLs to the candidate's source_urls list.

Relevance strategy: rather than maintaining an ever-growing blocklist of junk
domains, results are kept only when their title/snippet/domain carries a
positive quarry signal. This rejects the "carrière" (quarry vs. career) and
"ancienne" (former quarry vs. vintage cars) ambiguities at the source.
"""

import logging

from duckduckgo_search import DDGS

from backend.domain.entities.quarry import QuarryCandidate

logger = logging.getLogger(__name__)

_MAX_RESULTS_PER_QUERY = 8
_SEARCH_REGION = "fr-fr"

# Positive signal: a result is kept only if it carries one of these terms.
# CRITICAL: the bare word "carrière" is deliberately EXCLUDED — it is ambiguous
# in French (quarry vs. professional career), so it would let job boards,
# dictionaries, and retirement sites through. Only unambiguous geological /
# industrial terms count as a quarry signal.
# French + English for now; other languages tracked as future work (see README).
_RELEVANCE_KEYWORDS = (
    # French — unambiguous quarry/aggregate terms
    "granulat",
    "gravière",
    "graviere",
    "sablière",
    "sabliere",
    "calcaire",
    "granit",
    "ballast",
    "extraction de roches",
    "exploitation de roches",
    "roches massives",
    "matériaux de construction",
    "carrière de",  # "carrière de calcaire/granit/..." — qualified, not the bare word
    # English
    "quarry",
    "quarrying",
    "aggregate",
    "limestone",
    "granite",
    "gravel pit",
    "sand and gravel",
    "crushed stone",
    "mineral extraction",
)

# Registry / industry domains that are always relevant for a named operator.
_RELEVANT_DOMAINS = (
    "societe.com",
    "annuaire-entreprises.data.gouv.fr",
    "infogreffe.fr",
    "pappers.fr",
    "verif.com",
    "brgm.fr",
    "georisques.gouv.fr",
    "infoterre.brgm.fr",
    "unicem.fr",
    "unpg.fr",
)

# Hard blocklist for domains that pollute results even when a keyword matches
# (e.g. a Wikipedia article about quarries in general, not this site).
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
        "reddit.com",
        "zhihu.com",
        "github.com",
        "larousse.fr",
        "lerobert.com",
        "onisep.fr",
        "lassuranceretraite.fr",
        "info-retraite.fr",
        "pole-emploi.fr",
        "indeed.com",
        "carriereonline.com",
        "optioncarriere.com",
        "pagesjaunes.fr",
        # Generic directory search forms / dictionary definitions (substring match)
        "rechercher-une-carriere",
        "/definition/",
    ]
)


def _build_queries(candidate: QuarryCandidate) -> list[str]:
    """Build DuckDuckGo search queries for a named quarry candidate.

    Anchors the candidate name with strong industrial terms. Unnamed
    candidates produce no queries — coordinate-only searches return pure
    noise, so those candidates are left to abstain.

    Args:
        candidate: The quarry candidate to build queries for.

    Returns:
        A list of query strings, possibly empty.
    """
    if not candidate.name:
        return []

    name = candidate.name.strip()
    return [
        f'"{name}" carrière granulats',
        f"{name} exploitation carrière France",
    ]


def _is_blocked(url: str) -> bool:
    """Return True if the URL belongs to a hard-blocked domain."""
    return any(domain in url for domain in _BLOCKLIST)


def _is_relevant(result: dict) -> bool:
    """Return True if a search result genuinely concerns a quarry site.

    A result passes if its domain is a known registry, or if its title,
    snippet, or URL carries a quarry-related keyword — and it is not blocked.

    Args:
        result: A DuckDuckGo result dict with href/title/body keys.

    Returns:
        True if the result should be kept as a source URL.
    """
    href = result.get("href", "")
    if not href or _is_blocked(href):
        return False

    if any(domain in href for domain in _RELEVANT_DOMAINS):
        return True

    haystack = " ".join([result.get("title", ""), result.get("body", ""), href]).lower()
    return any(keyword in haystack for keyword in _RELEVANCE_KEYWORDS)


def _search_results(query: str, max_results: int) -> list[dict]:
    """Execute a DuckDuckGo text search and return full result dicts.

    Args:
        query:       The search query string.
        max_results: Maximum number of results to return.

    Returns:
        A list of result dicts, each with href/title/body keys.
    """
    with DDGS() as ddgs:
        return list(
            ddgs.text(
                query,
                region=_SEARCH_REGION,
                safesearch="off",
                max_results=max_results,
            )
        )


class WebSearchEnricher:
    """Enriches QuarryCandidate objects with relevant URLs found via DuckDuckGo.

    For each named candidate, runs targeted searches and keeps only results
    that carry a positive quarry signal (title/snippet/domain). Unnamed
    candidates are skipped — they have no findable web presence.

    Args:
        max_results:   Maximum results to request per query (default 8).
        max_urls_kept: Maximum relevant URLs to keep per candidate (default 5).
    """

    def __init__(self, max_results: int = _MAX_RESULTS_PER_QUERY, max_urls_kept: int = 5) -> None:
        self._max_results = max_results
        self._max_urls_kept = max_urls_kept

    async def enrich(self, candidate: QuarryCandidate) -> QuarryCandidate:
        """Search the web for relevant URLs and append them to the candidate.

        Modifies the candidate in-place and also returns it for convenience.

        Args:
            candidate: The quarry candidate to enrich.

        Returns:
            The same candidate with source_urls updated.
        """
        queries = _build_queries(candidate)
        if not queries:
            logger.debug("Candidate %r has no name — skipping web search", candidate.name)
            return candidate

        existing = set(candidate.source_urls)
        new_urls: list[str] = []

        for query in queries:
            if len(new_urls) >= self._max_urls_kept:
                break
            try:
                results = _search_results(query, self._max_results)
            except Exception as exc:
                logger.warning("DuckDuckGo search failed for query %r: %s", query, exc)
                continue

            for result in results:
                href = result.get("href", "")
                if href and href not in existing and _is_relevant(result):
                    new_urls.append(href)
                    existing.add(href)
                    if len(new_urls) >= self._max_urls_kept:
                        break

        if new_urls:
            candidate.source_urls.extend(new_urls)
            logger.info(
                "WebSearch added %d relevant URL(s) for candidate %r",
                len(new_urls),
                candidate.name,
            )
        else:
            logger.debug("WebSearch found no relevant URLs for candidate %r", candidate.name)

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
