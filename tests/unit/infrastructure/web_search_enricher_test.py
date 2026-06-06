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
    _is_relevant,
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
    return QuarryCandidate(name=name, latitude=lat, longitude=lon, source_urls=urls or [])


def _result(href: str, title: str = "", body: str = "") -> dict:
    return {"href": href, "title": title, "body": body}


# ---------------------------------------------------------------------------
# _build_queries
# ---------------------------------------------------------------------------


class TestBuildQueries:
    def test_uses_name_when_available(self):
        queries = _build_queries(_make_candidate(name="Carrière de Vignats"))
        assert any("Carrière de Vignats" in q for q in queries)

    def test_returns_empty_when_no_name(self):
        assert _build_queries(_make_candidate(name=None)) == []

    def test_anchors_with_quarry_terms(self):
        queries = _build_queries(_make_candidate(name="Vignats"))
        joined = " ".join(queries).lower()
        assert "carrière" in joined
        assert "granulats" in joined


# ---------------------------------------------------------------------------
# _is_blocked
# ---------------------------------------------------------------------------


class TestIsBlocked:
    def test_blocks_facebook(self):
        assert _is_blocked("https://www.facebook.com/quarry") is True

    def test_blocks_reddit(self):
        assert _is_blocked("https://www.reddit.com/r/anything") is True

    def test_allows_operator_site(self):
        assert _is_blocked("https://www.carriere-du-nord.fr/") is False


# ---------------------------------------------------------------------------
# _is_relevant
# ---------------------------------------------------------------------------


class TestIsRelevant:
    def test_keeps_result_with_quarry_keyword_in_title(self):
        result = _result("https://operator.fr/site", title="Carrière de calcaire", body="")
        assert _is_relevant(result) is True

    def test_keeps_result_with_keyword_in_body(self):
        result = _result("https://operator.fr", title="Accueil", body="exploitation de granulats")
        assert _is_relevant(result) is True

    def test_keeps_known_registry_domain(self):
        result = _result("https://www.societe.com/societe/x-123.html", title="", body="")
        assert _is_relevant(result) is True

    def test_keeps_english_quarry_result(self):
        result = _result(
            "https://operator.co.uk", title="Limestone quarry", body="aggregate supplier"
        )
        assert _is_relevant(result) is True

    def test_rejects_vintage_car_result(self):
        result = _result(
            "https://www.lesanciennes.com/",
            title="Voitures anciennes de collection",
            body="achat vente de véhicules anciens",
        )
        assert _is_relevant(result) is False

    def test_rejects_blocked_domain_even_with_keyword(self):
        result = _result(
            "https://fr.wikipedia.org/wiki/Carrière", title="Carrière", body="granulats"
        )
        assert _is_relevant(result) is False

    def test_rejects_result_without_signal(self):
        result = _result("https://random.com", title="Random page", body="nothing here")
        assert _is_relevant(result) is False

    def test_rejects_bare_career_word(self):
        # "carrière" alone is ambiguous (career) — must NOT pass on its own
        result = _result(
            "https://www.optioncarriere.com/",
            title="Option Carrière - offres d'emploi",
            body="trouvez votre carrière",
        )
        assert _is_relevant(result) is False

    def test_rejects_dictionary_definition(self):
        result = _result(
            "https://dictionnaire.lerobert.com/definition/carriere",
            title="carrière - Définition",
            body="lieu d'où l'on extrait des matériaux",
        )
        assert _is_relevant(result) is False

    def test_rejects_retirement_career_site(self):
        result = _result(
            "https://www.info-retraite.fr/voir-ma-carriere.html",
            title="Voir ma carrière",
            body="votre relevé de carrière",
        )
        assert _is_relevant(result) is False

    def test_keeps_qualified_carriere_de(self):
        result = _result(
            "https://operator.fr/carriere-de-mions",
            title="Carrière de calcaire de Mions",
            body="exploitation",
        )
        assert _is_relevant(result) is True


# ---------------------------------------------------------------------------
# WebSearchEnricher.enrich
# ---------------------------------------------------------------------------


class TestWebSearchEnricher:
    @pytest.fixture
    def enricher(self) -> WebSearchEnricher:
        return WebSearchEnricher(max_results=5)

    async def test_appends_relevant_urls(self, enricher):
        candidate = _make_candidate()
        results = [
            _result("https://example.com/quarry", title="Carrière de granulats"),
            _result("https://registry.fr/123", title="exploitation calcaire"),
        ]
        with patch(f"{_MODULE}._search_results", return_value=results):
            result = await enricher.enrich(candidate)

        assert "https://example.com/quarry" in result.source_urls
        assert "https://registry.fr/123" in result.source_urls

    async def test_filters_irrelevant_results(self, enricher):
        candidate = _make_candidate()
        results = [
            _result("https://lesanciennes.com", title="Voitures anciennes", body="collection auto"),
            _result("https://operator.fr", title="Carrière calcaire"),
        ]
        with patch(f"{_MODULE}._search_results", return_value=results):
            result = await enricher.enrich(candidate)

        assert "https://lesanciennes.com" not in result.source_urls
        assert "https://operator.fr" in result.source_urls

    async def test_skips_candidate_without_name(self, enricher):
        candidate = _make_candidate(name=None)
        with patch(f"{_MODULE}._search_results") as mock_search:
            result = await enricher.enrich(candidate)
        mock_search.assert_not_called()
        assert result.source_urls == []

    async def test_does_not_duplicate_existing_urls(self, enricher):
        existing = "https://example.com/quarry"
        candidate = _make_candidate(urls=[existing])
        results = [
            _result(existing, title="Carrière"),
            _result("https://new.fr", title="granulats"),
        ]
        with patch(f"{_MODULE}._search_results", return_value=results):
            result = await enricher.enrich(candidate)
        assert result.source_urls.count(existing) == 1

    async def test_returns_candidate_unchanged_on_search_error(self, enricher):
        candidate = _make_candidate()
        original = list(candidate.source_urls)
        with patch(f"{_MODULE}._search_results", side_effect=Exception("rate limited")):
            result = await enricher.enrich(candidate)
        assert result.source_urls == original

    async def test_caps_urls_at_max_kept(self):
        enricher = WebSearchEnricher(max_results=10, max_urls_kept=2)
        candidate = _make_candidate()
        results = [_result(f"https://site-{i}.fr", title="Carrière granulats") for i in range(10)]
        with patch(f"{_MODULE}._search_results", return_value=results):
            result = await enricher.enrich(candidate)
        assert len(result.source_urls) == 2

    async def test_returns_same_candidate_object(self, enricher):
        candidate = _make_candidate()
        with patch(f"{_MODULE}._search_results", return_value=[]):
            result = await enricher.enrich(candidate)
        assert result is candidate

    async def test_enrich_all_processes_every_candidate(self, enricher):
        candidates = [_make_candidate(name=f"Carrière {i}") for i in range(3)]

        def fake_search(query, max_results):
            return [_result("https://operator.fr/quarry", title="Carrière granulats")]

        with patch(f"{_MODULE}._search_results", side_effect=fake_search):
            results = await enricher.enrich_all(candidates)

        assert len(results) == 3
