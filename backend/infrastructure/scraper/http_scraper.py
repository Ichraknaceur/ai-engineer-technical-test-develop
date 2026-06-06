"""Polite HTTP scraper using httpx and BeautifulSoup.

Responsibilities:
- Validate URLs before fetching (scheme whitelist, no private IPs).
- Check robots.txt and skip disallowed URLs.
- Apply polite delays with jitter between requests.
- Respect Retry-After headers on 429 responses.
- Clean HTML to plain text, truncate to ~8 000 words.
- Hash raw HTML for deduplication.
- Never raise — failures are returned as ScrapedPage.error.
"""

import asyncio
import hashlib
import ipaddress
import logging
import random
import re
import socket
import urllib.robotparser
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from backend.config import settings
from backend.domain.entities.source import ScrapedPage, TrustTier

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_WORDS = 8_000
_REQUEST_TIMEOUT = 15.0

# Domains that serve generic/non-quarry-specific content — skip before fetching.
_USELESS_URL_PATTERNS = re.compile(
    r"(larousse\.fr|dictionnaire|wikipedia\.org|wikidata\.org|"
    r"rechercher-une-carriere|/search[/?]|google\.|bing\.com|"
    r"duckduckgo\.com|yahoo\.com|"
    r"lassuranceretraite\.fr|pole-emploi\.fr|indeed\.com|"
    r"accenture\.com|capgemini\.com|/careers?[/?]|/emploi[/?]|"
    r"pagesjaunes\.fr)",
    re.IGNORECASE,
)

# Domains that indicate official operator sites vs directories
_DIRECTORY_PATTERNS = re.compile(
    r"(annuaire|registre|repertoire|directory|brgm|georisques|societe\.com|"
    r"verif\.com|pappers|infogreffe|kompass)",
    re.IGNORECASE,
)
_NEWS_PATTERNS = re.compile(
    r"(actu|news|presse|journal|lemonde|lefigaro|ouest-france|20minutes)",
    re.IGNORECASE,
)


def is_useful_url(url: str) -> bool:
    """Return False for URLs known to serve generic non-quarry content.

    Filters out dictionaries, generic search pages, Wikipedia, and social
    networks before spending HTTP requests or LLM tokens on them.

    Args:
        url: The URL to check.

    Returns:
        True if the URL is worth fetching, False otherwise.
    """
    return not bool(_USELESS_URL_PATTERNS.search(url))


def _classify_trust_tier(url: str) -> TrustTier:
    """Infer the trust tier of a URL from its domain.

    Args:
        url: The source URL.

    Returns:
        One of ``official``, ``directory``, ``news``, or ``unknown``.
    """
    host = urlparse(url).netloc.lower()
    if _DIRECTORY_PATTERNS.search(host):
        return "directory"
    if _NEWS_PATTERNS.search(host):
        return "news"
    return "official"


def _is_valid_url(url: str) -> bool:
    """Return True if the URL is safe to fetch.

    Rejects:
    - Non-http/https schemes.
    - Hostnames that resolve to private or loopback IP ranges.

    Args:
        url: The URL to validate.

    Returns:
        True if safe, False otherwise.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_SCHEMES:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            logger.warning("Blocked private/loopback URL: %s", url)
            return False
    except Exception:
        return False
    return True


def _is_allowed_by_robots(url: str, user_agent: str) -> bool:
    """Check robots.txt for the given URL.

    Fetches and parses robots.txt synchronously. Returns True (allow) if the
    robots.txt cannot be fetched, following the principle of assuming permission
    when the file is unavailable.

    Args:
        url:        The URL to check.
        user_agent: The User-Agent string to check against.

    Returns:
        True if crawling is allowed, False if explicitly disallowed.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        return True
    return rp.can_fetch(user_agent, url)


def _clean_html(html: str) -> str:
    """Extract visible text from HTML, stripping scripts, styles, and boilerplate.

    Args:
        html: Raw HTML string.

    Returns:
        Plain text, whitespace-normalised, truncated to _MAX_WORDS words.
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    return " ".join(words[:_MAX_WORDS])


def _content_hash(content: bytes) -> str:
    """Return the SHA-256 hex digest of raw HTML bytes.

    Args:
        content: Raw HTTP response body.

    Returns:
        ``sha256:<hex>`` string.
    """
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _source_id(url: str) -> str:
    """Return a stable short identifier for a URL.

    Args:
        url: The source URL.

    Returns:
        ``src_<hex8>`` string derived from SHA-256 of the URL.
    """
    return "src_" + hashlib.sha256(url.encode()).hexdigest()[:8]


class HttpScraper:
    """Polite async HTTP scraper backed by httpx and BeautifulSoup.

    Validates URLs, checks robots.txt, applies jitter delays, and returns
    a ScrapedPage regardless of success or failure.

    Args:
        base_delay:  Base seconds to wait between requests (default from config).
        user_agent:  User-Agent header sent with every request (default from config).
        timeout:     Per-request timeout in seconds (default 15).
    """

    def __init__(
        self,
        base_delay: float | None = None,
        user_agent: str | None = None,
        timeout: float = _REQUEST_TIMEOUT,
    ) -> None:
        self._base_delay = base_delay or settings.base_scrape_delay_s
        self._user_agent = user_agent or settings.scraper_user_agent
        self._timeout = timeout

    async def fetch(self, url: str, source_id: str | None = None) -> ScrapedPage:
        """Fetch a URL and return its cleaned content as a ScrapedPage.

        Never raises — any error is captured in ScrapedPage.error.

        Args:
            url:       The URL to fetch.
            source_id: Stable identifier for this source. Derived from the URL
                       if not provided.

        Returns:
            A ScrapedPage with cleaned_text populated on success, or error set
            on failure.
        """
        sid = source_id or _source_id(url)
        fetched_at = datetime.now(UTC)

        def _error(msg: str) -> ScrapedPage:
            return ScrapedPage(
                source_id=sid,
                url=url,
                fetched_at=fetched_at,
                content_hash="",
                cleaned_text="",
                trust_tier=_classify_trust_tier(url),
                error=msg,
            )

        if not _is_valid_url(url):
            return _error("invalid_url")

        if not _is_allowed_by_robots(url, self._user_agent):
            logger.info("robots.txt disallows %s — skipping", url)
            return _error("disallowed_by_robots")

        # Polite delay with ±50 % jitter
        jitter = self._base_delay * random.uniform(0.5, 1.5)
        await asyncio.sleep(jitter)

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    logger.warning("Rate-limited on %s — Retry-After %ds", url, retry_after)
                    return _error(f"rate_limited_retry_after_{retry_after}s")

                response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            return _error(f"http_{exc.response.status_code}")
        except httpx.HTTPError as exc:
            return _error(f"network_error: {exc}")

        raw = response.content
        cleaned = _clean_html(response.text)

        return ScrapedPage(
            source_id=sid,
            url=url,
            fetched_at=fetched_at,
            content_hash=_content_hash(raw),
            cleaned_text=cleaned,
            trust_tier=_classify_trust_tier(url),
            error=None,
        )
