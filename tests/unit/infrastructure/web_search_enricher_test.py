"""Unit tests for WebSearchEnricher.

All DuckDuckGo calls are patched so no real network requests are made.
"""

from unittest.mock import patch

import pytest

from backend.domain.entities.quarry import QuarryCandidate
from backend.infrastructure.discovery.web_search import (
    WebSearchEnricher,
    _build_queries,
    _is_blocked,
)

_MODULE = "backend.infrastructure.discovery.web_search"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidate(
    name: str | None = "Carrière du Nord",
    lat: float = 48.9,
    lon: float = 2.4,
    urls: list[str] | None = None,
) -> QuarryCandidate:
    return QuarryCandidate(
        name=name,
        latitude=lat,
        longitude=lon,
        source_urls=urls or [],
    )


# ---------------------------------------------------------------------------
# _build_queries
# ---------------------------------------------------------------------------


class TestBuildQueries:
    def test_uses_name_when_available(self):
        candidate = _make_candidate(name="Carrière de Vignats")
        queries = _build_queries(candidate)
        assert any("Carrière de Vignats" in q for q in queries)

    def test_falls_back_to_coordinates_when_no_name(self):
        candidate = _make_candidate(name=None, lat=48.9, lon=2.4)
        queries = _build_queries(candidate)
        assert len(queries) == 1
        assert "48.900" in queries[0]
        assert "2.400" in queries[0]

    def test_returns_at_least_one_query(self):
        candidate = _make_candidate(name=None)
        assert len(_build_queries(candidate)) >= 1


# ---------------------------------------------------------------------------
# _is_blocked
# ---------------------------------------------------------------------------


class TestIsBlocked:
    def test_blocks_facebook(self):
        assert _is_blocked("https://www.facebook.com/quarry") is True

    def test_blocks_wikipedia(self):
        assert _is_blocked("https://fr.wikipedia.org/wiki/Carrière") is True

    def test_allows_operator_site(self):
        assert _is_blocked("https://www.carriere-du-nord.fr/") is False

    def test_allows_industrial_registry(self):
        assert _is_blocked("https://www.georisques.gouv.fr/sites/123") is False


# ---------------------------------------------------------------------------
# WebSearchEnricher.enrich
# ---------------------------------------------------------------------------


class TestWebSearchEnricher:
    @pytest.fixture
    def enricher(self) -> WebSearchEnricher:
        return WebSearchEnricher(max_results=3)

    async def test_appends_found_urls(self, enricher):
        candidate = _make_candidate()
        urls = ["https://example.com/quarry", "https://registry.fr/site/123"]

        with patch(f"{_MODULE}._search_urls", return_value=urls):
            result = await enricher.enrich(candidate)

        assert "https://example.com/quarry" in result.source_urls
        assert "https://registry.fr/site/123" in result.source_urls

    async def test_does_not_duplicate_existing_urls(self, enricher):
        existing = "https://example.com/quarry"
        candidate = _make_candidate(urls=[existing])

        with patch(f"{_MODULE}._search_urls", return_value=[existing, "https://new.fr"]):
            result = await enricher.enrich(candidate)

        assert result.source_urls.count(existing) == 1

    async def test_filters_blocked_domains(self, enricher):
        candidate = _make_candidate()
        urls = ["https://www.facebook.com/quarry", "https://legit-site.fr"]

        with patch(f"{_MODULE}._search_urls", return_value=urls):
            result = await enricher.enrich(candidate)

        assert "https://www.facebook.com/quarry" not in result.source_urls
        assert "https://legit-site.fr" in result.source_urls

    async def test_returns_candidate_unchanged_on_search_error(self, enricher):
        candidate = _make_candidate()
        original_urls = list(candidate.source_urls)

        with patch(f"{_MODULE}._search_urls", side_effect=Exception("rate limited")):
            result = await enricher.enrich(candidate)

        assert result.source_urls == original_urls

    async def test_returns_same_candidate_object(self, enricher):
        candidate = _make_candidate()
        with patch(f"{_MODULE}._search_urls", return_value=[]):
            result = await enricher.enrich(candidate)
        assert result is candidate

    async def test_enrich_all_processes_every_candidate(self, enricher):
        candidates = [_make_candidate(name=f"Carrière {i}") for i in range(3)]
        call_count = 0

        def fake_search(query, max_results):
            nonlocal call_count
            call_count += 1
            return [f"https://site-{call_count}.fr"]

        with patch(f"{_MODULE}._search_urls", side_effect=fake_search):
            results = await enricher.enrich_all(candidates)

        assert len(results) == 3
        assert all(len(c.source_urls) > 0 for c in results)
