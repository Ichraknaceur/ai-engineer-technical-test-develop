"""Outbound port for LLM-based field extraction.

Any adapter that calls an LLM to extract grounded fields from a page must
satisfy this protocol. Current implementation: OpenAIExtractor (gpt-4o).
"""

from typing import Protocol

from backend.domain.entities.source import ScrapedPage


class IExtractor(Protocol):
    """Contract for extracting grounded quarry metadata from a scraped page."""

    async def extract(self, page: ScrapedPage) -> dict:
        """Extract grounded fields from a scraped page using an LLM.

        Each returned field follows the groundedString schema:
        ``{"value": ..., "confidence": ..., "evidence": [...], "abstain_reason": ...}``

        The implementation must never invent values — if the page does not
        contain reliable evidence for a field, it must set value=None and
        provide an abstain_reason.

        Args:
            page: A successfully scraped and cleaned page.

        Returns:
            A partial extraction dict. Keys are field names from the output
            schema (e.g. "official_name", "operational_status"). Missing keys
            mean the field was not addressed for this page.
        """
        ...
