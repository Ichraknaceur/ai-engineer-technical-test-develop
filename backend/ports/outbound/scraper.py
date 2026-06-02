"""Outbound port for web page scraping.

Any adapter that fetches and cleans a URL must satisfy this protocol.
Current implementation: HttpScraper (httpx + BeautifulSoup).
"""

from typing import Protocol

from backend.domain.entities.source import ScrapedPage


class IScraper(Protocol):
    """Contract for fetching and cleaning a single web page."""

    async def fetch(self, url: str, source_id: str) -> ScrapedPage:
        """Fetch a URL and return its cleaned content as a ScrapedPage.

        The implementation is responsible for:
        - Validating the URL (scheme, no private IPs).
        - Checking robots.txt before fetching.
        - Applying polite delays and jitter.
        - Cleaning the HTML to plain text.

        This method never raises — failures are captured in ScrapedPage.error.

        Args:
            url:       The URL to fetch.
            source_id: Stable identifier for this source (typically sha256 of the URL).

        Returns:
            A ScrapedPage. If fetching failed, error is set and cleaned_text is empty.
        """
        ...
