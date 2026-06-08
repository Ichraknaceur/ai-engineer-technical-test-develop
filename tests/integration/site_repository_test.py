"""Integration tests for PostgresSiteRepository against a real PostgreSQL.

Verifies JSONB persistence, full-record round-trip, filtering, and pagination —
the parts that cannot be covered with mocks.
"""

import pytest

from backend.domain.entities.quarry import QuarryRecord
from backend.infrastructure.db.repositories.site_repository import PostgresSiteRepository

pytestmark = pytest.mark.integration


def _make_record(
    site_id: str, name: str | None = "Carrière du Nord", status: str = "active"
) -> QuarryRecord:
    return QuarryRecord(
        site_id=site_id,
        schema_version="2.0.0",
        input={"latitude": 45.764, "longitude": 4.835, "radius_km": 30.0},
        extraction={
            "official_name": {
                "value": name,
                "confidence": 0.9,
                "evidence": [],
                "abstain_reason": None,
            },
            "operational_status": {
                "value": status,
                "confidence": 0.8,
                "evidence": [],
                "abstain_reason": None,
            },
            "materials_produced": [{"value": "limestone", "confidence": 0.9, "evidence": []}],
        },
        provenance={
            "sources": [
                {
                    "source_id": "src_1",
                    "url": "https://x.fr",
                    "fetched_at": "2026-06-06T10:00:00Z",
                    "content_hash": "sha256:a",
                    "trust_tier": "official",
                }
            ],
            "reconciliations": [],
        },
        metrics={
            "llm_tokens_in": 100,
            "llm_tokens_out": 50,
            "usd_cost": 0.01,
            "latency_ms": 1200,
            "model_calls": [],
        },
        run_metadata={
            "run_id": "r_1",
            "job_id": "j_1",
            "prompt_hash": "sha256:p",
            "scraper_version": "1.0.0",
            "created_at": "2026-06-06T10:00:00Z",
        },
    )


async def test_save_and_get_preserves_jsonb(session):
    repo = PostgresSiteRepository(session)
    record = _make_record("s_int_1")

    await repo.save(record)
    fetched = await repo.get("s_int_1")

    assert fetched is not None
    assert fetched.site_id == "s_int_1"
    assert fetched.extraction["official_name"]["value"] == "Carrière du Nord"
    assert fetched.extraction["materials_produced"][0]["value"] == "limestone"
    assert fetched.provenance["sources"][0]["trust_tier"] == "official"
    assert fetched.metrics["usd_cost"] == pytest.approx(0.01)


async def test_get_returns_none_when_absent(session):
    repo = PostgresSiteRepository(session)
    assert await repo.get("s_missing") is None


async def test_list_returns_all(session):
    repo = PostgresSiteRepository(session)
    await repo.save(_make_record("s_1", name="Alpha"))
    await repo.save(_make_record("s_2", name="Beta"))

    total, records = await repo.list()
    assert total == 2
    assert len(records) == 2


async def test_list_filters_by_name(session):
    repo = PostgresSiteRepository(session)
    await repo.save(_make_record("s_1", name="Carrière Alpha"))
    await repo.save(_make_record("s_2", name="Carrière Beta"))

    total, records = await repo.list(q="Alpha")
    assert total == 1
    assert records[0].extraction["official_name"]["value"] == "Carrière Alpha"


async def test_list_filters_by_status(session):
    repo = PostgresSiteRepository(session)
    await repo.save(_make_record("s_1", status="active"))
    await repo.save(_make_record("s_2", status="inactive"))

    total, records = await repo.list(status="inactive")
    assert total == 1
    assert records[0].extraction["operational_status"]["value"] == "inactive"


async def test_list_paginates(session):
    repo = PostgresSiteRepository(session)
    for i in range(5):
        await repo.save(_make_record(f"s_{i}", name=f"Site {i}"))

    total, page1 = await repo.list(page=1, page_size=2)
    assert total == 5
    assert len(page1) == 2
