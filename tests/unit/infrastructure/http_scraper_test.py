"""Unit tests for HttpScraper.

All network calls (httpx, socket, robots.txt) are patched.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.infrastructure.scraper.http_scraper import (
    HttpScraper,
    _classify_trust_tier,
    _clean_html,
    _content_hash,
    _is_valid_url,
    _source_id,
)

_MODULE = "backend.infrastructure.scraper.http_scraper"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    status: int = 200,
    text: str = "<html><body><p>Quarry content</p></body></html>",
    headers: dict | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://example.com")
    return httpx.Response(status, text=text, headers=headers or {}, request=request)


def _patch_valid_url(valid: bool = True):
    return patch(f"{_MODULE}._is_valid_url", return_value=valid)


def _patch_robots(allowed: bool = True):
    return patch(f"{_MODULE}._is_allowed_by_robots", return_value=allowed)


# ---------------------------------------------------------------------------
# _classify_trust_tier
# ---------------------------------------------------------------------------


class TestClassifyTrustTier:
    def test_directory_domain(self):
        assert _classify_trust_tier("https://www.annuaire-industrie.fr/site/123") == "directory"

    def test_news_domain(self):
        assert _classify_trust_tier("https://actu.fr/article/carriere") == "news"

    def test_unknown_defaults_to_official(self):
        assert _classify_trust_tier("https://www.carriere-du-nord.fr") == "official"

    def test_brgm_is_directory(self):
        assert _classify_trust_tier("https://www.brgm.fr/resource/123") == "directory"


# ---------------------------------------------------------------------------
# _clean_html
# ---------------------------------------------------------------------------


class TestCleanHtml:
    def test_removes_script_tags(self):
        html = "<html><body><script>alert(1)</script><p>Text</p></body></html>"
        assert "alert" not in _clean_html(html)
        assert "Text" in _clean_html(html)

    def test_removes_style_tags(self):
        html = "<html><head><style>body{color:red}</style></head><body><p>Hi</p></body></html>"
        result = _clean_html(html)
        assert "color" not in result
        assert "Hi" in result

    def test_collapses_whitespace(self):
        html = "<p>Hello    \n\n   World</p>"
        result = _clean_html(html)
        assert "Hello World" in result

    def test_truncates_to_max_words(self):
        html = f"<p>{'word ' * 10_000}</p>"
        result = _clean_html(html)
        assert len(result.split()) <= 8_000


# ---------------------------------------------------------------------------
# _is_valid_url
# ---------------------------------------------------------------------------


class TestIsValidUrl:
    def test_rejects_ftp_scheme(self):
        assert _is_valid_url("ftp://example.com/file") is False

    def test_rejects_missing_hostname(self):
        assert _is_valid_url("https://") is False

    def test_rejects_private_ip(self):
        with patch("socket.gethostbyname", return_value="192.168.1.1"):
            assert _is_valid_url("http://internal.corp/page") is False

    def test_rejects_loopback(self):
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            assert _is_valid_url("http://localhost/page") is False

    def test_accepts_public_https(self):
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            assert _is_valid_url("https://example.com/page") is True


# ---------------------------------------------------------------------------
# _content_hash / _source_id
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_content_hash_starts_with_sha256(self):
        assert _content_hash(b"hello").startswith("sha256:")

    def test_content_hash_is_deterministic(self):
        assert _content_hash(b"hello") == _content_hash(b"hello")

    def test_content_hash_differs_for_different_content(self):
        assert _content_hash(b"hello") != _content_hash(b"world")

    def test_source_id_starts_with_src(self):
        assert _source_id("https://example.com").startswith("src_")

    def test_source_id_is_deterministic(self):
        assert _source_id("https://example.com") == _source_id("https://example.com")


# ---------------------------------------------------------------------------
# HttpScraper.fetch
# ---------------------------------------------------------------------------


class TestHttpScraper:
    @pytest.fixture
    def scraper(self) -> HttpScraper:
        return HttpScraper(base_delay=0, user_agent="TestBot/1.0", timeout=5)

    async def test_returns_scraped_page_on_success(self, scraper):
        with _patch_valid_url(), _patch_robots(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_make_response())
            mock_cls.return_value = mock_client

            page = await scraper.fetch("https://example.com")

        assert page.error is None
        assert page.url == "https://example.com"
        assert "Quarry content" in page.cleaned_text
        assert page.content_hash.startswith("sha256:")

    async def test_returns_error_on_invalid_url(self, scraper):
        with _patch_valid_url(False):
            page = await scraper.fetch("ftp://bad.url")
        assert page.error == "invalid_url"
        assert page.cleaned_text == ""

    async def test_returns_error_when_robots_disallows(self, scraper):
        with _patch_valid_url(), _patch_robots(False):
            page = await scraper.fetch("https://example.com/private")
        assert page.error == "disallowed_by_robots"

    async def test_returns_error_on_http_404(self, scraper):
        with _patch_valid_url(), _patch_robots(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "404", request=MagicMock(), response=MagicMock(status_code=404)
                )
            )
            mock_cls.return_value = mock_client

            page = await scraper.fetch("https://example.com/missing")

        assert page.error == "http_404"

    async def test_returns_error_on_network_failure(self, scraper):
        with _patch_valid_url(), _patch_robots(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            mock_cls.return_value = mock_client

            page = await scraper.fetch("https://example.com")

        assert page.error is not None
        assert "network_error" in page.error

    async def test_returns_error_on_429_with_retry_after(self, scraper):
        with _patch_valid_url(), _patch_robots(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                return_value=_make_response(status=429, headers={"Retry-After": "30"})
            )
            mock_cls.return_value = mock_client

            page = await scraper.fetch("https://example.com")

        assert page.error == "rate_limited_retry_after_30s"

    async def test_classifies_trust_tier(self, scraper):
        with _patch_valid_url(), _patch_robots(), patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_make_response())
            mock_cls.return_value = mock_client

            page = await scraper.fetch("https://www.brgm.fr/resource/123")

        assert page.trust_tier == "directory"
