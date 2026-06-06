"""Unit tests for DiscoveryStep, ReconcilerStep, and ValidatorStep."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.pipeline.discovery import DiscoveryStep
from backend.application.pipeline.reconciler import ReconcilerStep
from backend.application.pipeline.validator import ValidatorStep
from backend.domain.entities.quarry import QuarryCandidate
from backend.domain.exceptions import ValidationError
from backend.domain.value_objects.coordinates import Coordinates

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coords(lat: float = 48.8566, lon: float = 2.3522, radius: float = 10.0) -> Coordinates:
    return Coordinates(latitude=lat, longitude=lon, radius_km=radius)


def _candidate(name: str = "Carrière A", urls: list[str] | None = None) -> QuarryCandidate:
    return QuarryCandidate(name=name, latitude=48.9, longitude=2.4, source_urls=urls or [])


def _grounded(
    value, confidence: float = 0.8, source_id: str = "src_1", quote: str = "quote"
) -> dict:
    if value is None:
        return {"value": None, "confidence": 0.0, "evidence": [], "abstain_reason": "no_evidence"}
    return {
        "value": value,
        "confidence": confidence,
        "evidence": [{"source_id": source_id, "char_start": 0, "char_end": 5, "quote": quote}],
        "abstain_reason": None,
    }


def _source(source_id: str = "src_1", trust_tier: str = "official") -> dict:
    return {
        "source_id": source_id,
        "url": f"https://example.com/{source_id}",
        "fetched_at": "2026-06-05T10:00:00Z",
        "content_hash": "sha256:abc",
        "trust_tier": trust_tier,
    }


def _minimal_record(site_id: str = "s_abc") -> dict:
    """Build a minimal valid record conforming to schema v2.0.0."""
    return {
        "site_id": site_id,
        "schema_version": "2.0.0",
        "input": {"latitude": 48.8566, "longitude": 2.3522, "radius_km": 10.0},
        "extraction": {},
        "provenance": {"sources": [], "reconciliations": []},
        "metrics": {
            "llm_tokens_in": 0,
            "llm_tokens_out": 0,
            "usd_cost": 0.0,
            "latency_ms": 0,
            "model_calls": [],
        },
        "run_metadata": {
            "run_id": "r_test",
            "prompt_hash": "sha256:abc",
            "scraper_version": "1.0.0",
            "created_at": "2026-06-05T10:00:00Z",
        },
    }


# ---------------------------------------------------------------------------
# DiscoveryStep
# ---------------------------------------------------------------------------


class TestDiscoveryStep:
    async def test_returns_candidates_from_discoverer(self):
        candidates = [_candidate("Carrière A"), _candidate("Carrière B")]
        discoverer = MagicMock()
        discoverer.discover = AsyncMock(return_value=candidates)
        enricher = MagicMock()
        enricher.enrich_all = AsyncMock(return_value=candidates)

        step = DiscoveryStep(discoverer=discoverer, enricher=enricher)
        result = await step.run(_coords())

        assert len(result) == 2
        discoverer.discover.assert_awaited_once()
        enricher.enrich_all.assert_awaited_once_with(candidates)

    async def test_returns_empty_list_when_no_candidates(self):
        discoverer = MagicMock()
        discoverer.discover = AsyncMock(return_value=[])
        enricher = MagicMock()
        enricher.enrich_all = AsyncMock(return_value=[])

        step = DiscoveryStep(discoverer=discoverer, enricher=enricher)
        result = await step.run(_coords())

        assert result == []
        enricher.enrich_all.assert_not_awaited()

    async def test_skips_enrichment_when_no_candidates(self):
        discoverer = MagicMock()
        discoverer.discover = AsyncMock(return_value=[])
        enricher = MagicMock()

        step = DiscoveryStep(discoverer=discoverer, enricher=enricher)
        await step.run(_coords())

        enricher.enrich_all.assert_not_called()


# ---------------------------------------------------------------------------
# ReconcilerStep
# ---------------------------------------------------------------------------


class TestReconcilerStep:
    @pytest.fixture
    def step(self) -> ReconcilerStep:
        return ReconcilerStep()

    def test_returns_empty_on_no_extractions(self, step):
        result = step.run([], [])
        assert result["extraction"] == {}
        assert result["reconciliations"] == []

    def test_picks_highest_scoring_value(self, step):
        extractions = [
            {"official_name": _grounded("Official Name", confidence=0.9, source_id="src_1")},
            {"official_name": _grounded("Other Name", confidence=0.5, source_id="src_2")},
        ]
        sources = [_source("src_1", "official"), _source("src_2", "directory")]

        result = step.run(extractions, sources)
        # src_1: 0.9 × 1.0 = 0.9 vs src_2: 0.5 × 0.6 = 0.3 → src_1 wins
        assert result["extraction"]["official_name"]["value"] == "Official Name"

    def test_directory_beats_low_confidence_official(self, step):
        extractions = [
            {"official_name": _grounded("Official", confidence=0.2, source_id="src_1")},
            {"official_name": _grounded("Directory", confidence=0.9, source_id="src_2")},
        ]
        sources = [_source("src_1", "official"), _source("src_2", "directory")]

        result = step.run(extractions, sources)
        # src_1: 0.2 × 1.0 = 0.2 vs src_2: 0.9 × 0.6 = 0.54 → src_2 wins
        assert result["extraction"]["official_name"]["value"] == "Directory"

    def test_merges_array_fields_without_duplicates(self, step):
        extractions = [
            {"materials_produced": [_grounded("limestone", source_id="src_1")]},
            {
                "materials_produced": [
                    _grounded("limestone", source_id="src_2"),
                    _grounded("granite", source_id="src_2"),
                ]
            },
        ]
        sources = [_source("src_1"), _source("src_2")]

        result = step.run(extractions, sources)
        values = [m["value"] for m in result["extraction"]["materials_produced"]]
        assert "limestone" in values
        assert "granite" in values
        assert values.count("limestone") == 1

    def test_writes_reconciliation_for_competing_values(self, step):
        extractions = [
            {"official_name": _grounded("Name A", confidence=0.9, source_id="src_1")},
            {"official_name": _grounded("Name B", confidence=0.8, source_id="src_2")},
        ]
        sources = [_source("src_1", "official"), _source("src_2", "official")]

        result = step.run(extractions, sources)
        assert len(result["reconciliations"]) == 1
        assert result["reconciliations"][0]["field"] == "official_name"
        assert result["reconciliations"][0]["winner_source_id"] == "src_1"

    def test_handles_null_values_gracefully(self, step):
        extractions = [
            {"official_name": _grounded(None, source_id="src_1")},
            {"official_name": _grounded("Real Name", confidence=0.7, source_id="src_2")},
        ]
        sources = [_source("src_1", "official"), _source("src_2", "directory")]

        result = step.run(extractions, sources)
        assert result["extraction"]["official_name"]["value"] == "Real Name"


# ---------------------------------------------------------------------------
# ValidatorStep
# ---------------------------------------------------------------------------


class TestValidatorStep:
    @pytest.fixture
    def step(self) -> ValidatorStep:
        return ValidatorStep()

    def test_returns_record_unchanged_when_valid(self, step):
        record = _minimal_record()
        result = step.run(record)
        assert result is record

    def test_raises_on_missing_required_field(self, step):
        record = _minimal_record()
        del record["site_id"]
        with pytest.raises(ValidationError):
            step.run(record)

    def test_raises_on_wrong_schema_version(self, step):
        record = _minimal_record()
        record["schema_version"] = "1.0.0"
        with pytest.raises(ValidationError):
            step.run(record)

    def test_raises_on_invalid_latitude(self, step):
        record = _minimal_record()
        record["input"]["latitude"] = 200.0
        with pytest.raises(ValidationError):
            step.run(record)

    def test_raises_on_missing_metrics_fields(self, step):
        record = _minimal_record()
        del record["metrics"]["llm_tokens_in"]
        with pytest.raises(ValidationError):
            step.run(record)

    def test_accepts_record_with_extraction_fields(self, step):
        record = _minimal_record()
        record["extraction"] = {
            "official_name": {
                "value": "Carrière du Nord",
                "confidence": 0.9,
                "evidence": [
                    {"source_id": "src_1", "char_start": 0, "char_end": 5, "quote": "Carr"}
                ],
                "abstain_reason": None,
            }
        }
        result = step.run(record)
        assert result["extraction"]["official_name"]["value"] == "Carrière du Nord"
