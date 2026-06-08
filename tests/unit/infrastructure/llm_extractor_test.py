"""Unit tests for LLMExtractor.

All provider API calls are patched — no real LLM requests are made.
Tests are provider-agnostic: they mock ILLMProvider.complete directly.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from backend.domain.entities.source import ScrapedPage
from backend.infrastructure.llm.llm_extractor import (
    LLMExtractor,
    _abstain_all,
    _prompt_hash,
)

_MODULE = "backend.infrastructure.llm.llm_extractor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page(
    text: str = "La Carrière du Nord extrait du calcaire depuis 1985. Statut: actif.",
    error: str | None = None,
    source_id: str = "src_abc123",
    url: str = "https://example.com",
    trust_tier: str = "official",
) -> ScrapedPage:
    return ScrapedPage(
        source_id=source_id,
        url=url,
        fetched_at=datetime.now(UTC),
        content_hash="sha256:abc",
        cleaned_text=text,
        trust_tier=trust_tier,
        error=error,
    )


def _make_provider(raw_json: dict | None = None, side_effect: Exception | None = None) -> MagicMock:
    """Build a mock ILLMProvider."""
    provider = MagicMock()
    provider.model = "mock-model"
    if side_effect:
        provider.complete = AsyncMock(side_effect=side_effect)
    else:
        content = json.dumps(raw_json or {})
        provider.complete = AsyncMock(return_value=(content, 100, 50, 0.001))
    return provider


def _make_extractor(provider: MagicMock | None = None) -> LLMExtractor:
    extractor = LLMExtractor.__new__(LLMExtractor)
    extractor._provider = provider or _make_provider()
    extractor._prompt_hash = _prompt_hash("test")
    return extractor


# ---------------------------------------------------------------------------
# Helpers functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_prompt_hash_starts_with_sha256(self):
        assert _prompt_hash("hello").startswith("sha256:")

    def test_prompt_hash_is_deterministic(self):
        assert _prompt_hash("hello") == _prompt_hash("hello")


# ---------------------------------------------------------------------------
# _abstain_all
# ---------------------------------------------------------------------------


class TestAbstainAll:
    def test_returns_null_values_for_all_fields(self):
        result = _abstain_all("mock-model", "sha256:abc", "no_evidence")
        assert result["official_name"]["value"] is None
        assert result["operational_status"]["value"] is None

    def test_sets_abstain_reason(self):
        result = _abstain_all("mock-model", "sha256:abc", "stale_evidence")
        assert result["official_name"]["abstain_reason"] == "stale_evidence"

    def test_confidence_is_zero(self):
        result = _abstain_all("mock-model", "sha256:abc", "no_evidence")
        assert result["official_name"]["confidence"] == 0.0

    def test_materials_and_certifications_are_empty_lists(self):
        result = _abstain_all("mock-model", "sha256:abc", "no_evidence")
        assert result["materials_produced"] == []
        assert result["certifications"] == []

    def test_metrics_are_zero_cost(self):
        result = _abstain_all("mock-model", "sha256:abc", "no_evidence")
        assert result["_metrics"]["usd_cost"] == 0.0
        assert result["_metrics"]["tokens_in"] == 0


# ---------------------------------------------------------------------------
# LLMExtractor.extract
# ---------------------------------------------------------------------------


class TestLLMExtractor:
    async def test_returns_abstain_for_errored_page(self):
        extractor = _make_extractor()
        page = _make_page(error="http_404", text="")
        result = await extractor.extract(page)
        assert result["official_name"]["abstain_reason"] == "empty_or_errored_page"

    async def test_returns_abstain_for_empty_text(self):
        extractor = _make_extractor()
        page = _make_page(text="   ")
        result = await extractor.extract(page)
        assert result["official_name"]["abstain_reason"] == "empty_or_errored_page"

    async def test_does_not_call_provider_for_empty_page(self):
        provider = _make_provider()
        extractor = _make_extractor(provider)
        await extractor.extract(_make_page(text=""))
        provider.complete.assert_not_called()

    async def test_returns_extraction_on_success(self):
        extraction = {
            "official_name": {
                "value": "Carrière du Nord",
                "confidence": 0.92,
                "evidence": [
                    {
                        "source_id": "src_abc123",
                        "char_start": 3,
                        "char_end": 19,
                        "quote": "Carrière du Nord",
                    }
                ],
                "abstain_reason": None,
            },
            "operational_status": {
                "value": "active",
                "confidence": 0.85,
                "evidence": [
                    {"source_id": "src_abc123", "char_start": 50, "char_end": 55, "quote": "actif"}
                ],
                "abstain_reason": None,
            },
        }
        extractor = _make_extractor(_make_provider(extraction))
        result = await extractor.extract(_make_page())
        assert result["official_name"]["value"] == "Carrière du Nord"
        assert result["operational_status"]["value"] == "active"

    async def test_includes_metrics_in_result(self):
        extractor = _make_extractor(
            _make_provider(
                {
                    "official_name": {
                        "value": None,
                        "confidence": 0.0,
                        "evidence": [],
                        "abstain_reason": "no_evidence",
                    }
                }
            )
        )
        result = await extractor.extract(_make_page())
        assert "_metrics" in result
        assert result["_metrics"]["tokens_in"] == 100
        assert result["_metrics"]["tokens_out"] == 50
        assert result["_metrics"]["model"] == "mock-model"

    async def test_returns_abstain_on_provider_error(self):
        extractor = _make_extractor(_make_provider(side_effect=Exception("API timeout")))
        result = await extractor.extract(_make_page())
        assert result["official_name"]["abstain_reason"] == "llm_api_error"

    async def test_returns_abstain_on_invalid_json(self):
        provider = _make_provider()
        provider.complete = AsyncMock(return_value=("not valid json {{{", 10, 5, 0.001))
        extractor = _make_extractor(provider)
        result = await extractor.extract(_make_page())
        assert result["official_name"]["abstain_reason"] == "llm_invalid_json"

    async def test_uses_injected_provider(self):
        provider = _make_provider(
            {
                "official_name": {
                    "value": "Test",
                    "confidence": 0.9,
                    "evidence": [],
                    "abstain_reason": None,
                }
            }
        )
        extractor = LLMExtractor(provider=provider)
        await extractor.extract(_make_page())
        provider.complete.assert_called_once()
