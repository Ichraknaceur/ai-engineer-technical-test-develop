"""Discovery pipeline step: find and enrich quarry candidates for a given search area."""

import logging

from backend.domain.entities.quarry import QuarryCandidate
from backend.domain.value_objects.coordinates import Coordinates
from backend.infrastructure.discovery.overpass import OverpassDiscoverer
from backend.infrastructure.discovery.web_search import WebSearchEnricher
from backend.ports.outbound.discoverer import IDiscoverer

logger = logging.getLogger(__name__)


class DiscoveryStep:
    """Finds quarry candidates via Overpass and enriches them with web search URLs.

    Combines two sources:
    1. OverpassDiscoverer — finds OSM-tagged quarries within the search area.
    2. WebSearchEnricher  — adds web URLs for each candidate via DuckDuckGo.

    Args:
        discoverer: Overpass adapter (or any IDiscoverer).
        enricher:   Web search enricher. Defaults to WebSearchEnricher().
    """

    def __init__(
        self,
        discoverer: IDiscoverer | None = None,
        enricher: WebSearchEnricher | None = None,
    ) -> None:
        self._discoverer = discoverer or OverpassDiscoverer()
        self._enricher = enricher or WebSearchEnricher()

    async def run(self, coordinates: Coordinates) -> list[QuarryCandidate]:
        """Discover quarry candidates and enrich them with source URLs.

        Args:
            coordinates: Centre point and radius of the search area.

        Returns:
            A list of QuarryCandidate objects with source_urls populated.
            Returns an empty list if no candidates are found.
        """
        logger.info(
            "Discovery step — centre=(%.4f, %.4f) radius=%.1fkm",
            coordinates.latitude,
            coordinates.longitude,
            coordinates.radius_km,
        )

        candidates = await self._discoverer.discover(coordinates)

        if not candidates:
            logger.info("Discovery found no candidates")
            return []

        logger.info("Discovery found %d candidate(s) — enriching with web search", len(candidates))
        candidates = await self._enricher.enrich_all(candidates)

        total_urls = sum(len(c.source_urls) for c in candidates)
        logger.info(
            "Enrichment complete — %d total source URLs across %d candidates",
            total_urls,
            len(candidates),
        )

        return candidates
