"""Unit tests for GET /api/sites and GET /api/sites/{site_id}.

The application service is replaced with an in-memory fake so these tests
run without a database.
"""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from backend.domain.entities.quarry import QuarryRecord
from backend.infrastructure.api.dependencies.services import get_site_service
from backend.infrastructure.api.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(site_id: str = "s_abc", name: str = "Carrière du Nord") -> QuarryRecord:
    return QuarryRecord(
        site_id=site_id,
        schema_version="2.0.0",
        input={"latitude": 45.75, "longitude": 4.83, "radius_km": 10.0},
        extraction={
            "official_name": {"value": name, "confidence": 0.9, "evidence": []},
            "operational_status": {"value": "active", "confidence": 0.8, "evidence": []},
        },
        provenance={"sources": []},
        metrics={"total_tokens": 500, "total_usd_cost": 0.01},
        run_metadata={"run_id": "j_xyz", "schema_version": "2.0.0"},
    )


def _make_client(mock_service) -> TestClient:
    app.dependency_overrides[get_site_service] = lambda: mock_service
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /api/sites
# ---------------------------------------------------------------------------


class TestListSites:
    def test_returns_paginated_list(self):
        records = [_make_record("s_001"), _make_record("s_002")]
        svc = AsyncMock()
        svc.list = AsyncMock(return_value=(2, records))
        client = _make_client(svc)

        resp = client.get("/api/sites")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["items"]) == 2
        assert data["items"][0]["site_id"] == "s_001"

    def test_passes_q_and_status_filters(self):
        svc = AsyncMock()
        svc.list = AsyncMock(return_value=(0, []))
        client = _make_client(svc)

        client.get("/api/sites?q=nord&status=active&page=2&page_size=5")

        svc.list.assert_awaited_once_with(q="nord", status="active", page=2, page_size=5)

    def test_empty_result(self):
        svc = AsyncMock()
        svc.list = AsyncMock(return_value=(0, []))
        client = _make_client(svc)

        resp = client.get("/api/sites")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_rejects_page_size_above_100(self):
        svc = AsyncMock()
        client = _make_client(svc)

        resp = client.get("/api/sites?page_size=101")

        assert resp.status_code == 422

    def test_rejects_page_zero(self):
        svc = AsyncMock()
        client = _make_client(svc)

        resp = client.get("/api/sites?page=0")

        assert resp.status_code == 422

    def test_item_contains_expected_fields(self):
        record = _make_record("s_001", "Granite Sud")
        svc = AsyncMock()
        svc.list = AsyncMock(return_value=(1, [record]))
        client = _make_client(svc)

        resp = client.get("/api/sites")

        item = resp.json()["items"][0]
        assert item["site_id"] == "s_001"
        assert item["schema_version"] == "2.0.0"
        assert "extraction" in item
        assert "provenance" in item
        assert "metrics" in item


# ---------------------------------------------------------------------------
# GET /api/sites/{site_id}
# ---------------------------------------------------------------------------


class TestGetSite:
    def test_returns_record_when_found(self):
        record = _make_record("s_abc")
        svc = AsyncMock()
        svc.get = AsyncMock(return_value=record)
        client = _make_client(svc)

        resp = client.get("/api/sites/s_abc")

        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "s_abc"
        assert data["schema_version"] == "2.0.0"

    def test_returns_404_when_not_found(self):
        svc = AsyncMock()
        svc.get = AsyncMock(return_value=None)
        client = _make_client(svc)

        resp = client.get("/api/sites/s_notexist")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Site not found"

    def test_full_extraction_payload_is_returned(self):
        record = _make_record("s_xyz", "Carrière Est")
        svc = AsyncMock()
        svc.get = AsyncMock(return_value=record)
        client = _make_client(svc)

        resp = client.get("/api/sites/s_xyz")

        data = resp.json()
        assert data["extraction"]["official_name"]["value"] == "Carrière Est"
        assert data["extraction"]["operational_status"]["value"] == "active"
