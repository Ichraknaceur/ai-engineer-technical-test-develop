"""Unit tests for OverpassDiscoverer.

All network calls are patched at the _fetch_sync level so no real HTTP
requests are made.
"""

from unittest.mock import patch

import pytest

from backend.domain.value_objects.coordinates import Coordinates
from backend.infrastructure.discovery.overpass import (
    OverpassDiscoverer,
    _bbox_from_coordinates,
    _parse_element,
)

_MODULE = "backend.infrastructure.discovery.overpass"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinates(
    lat: float = 48.8566, lon: float = 2.3522, radius: float = 10.0
) -> Coordinates:
    return Coordinates(latitude=lat, longitude=lon, radius_km=radius)


def _node(
    osm_id: int = 1, lat: float = 48.9, lon: float = 2.4, name: str = "Carrière du Nord"
) -> dict:
    return {
        "type": "node",
        "id": osm_id,
        "lat": lat,
        "lon": lon,
        "tags": {"landuse": "quarry", "name": name},
    }


def _way(osm_id: int = 2, lat: float = 48.85, lon: float = 2.35, name: str | None = None) -> dict:
    tags: dict = {"landuse": "quarry"}
    if name:
        tags["name"] = name
    return {"type": "way", "id": osm_id, "center": {"lat": lat, "lon": lon}, "tags": tags}


# ---------------------------------------------------------------------------
# _bbox_from_coordinates
# ---------------------------------------------------------------------------


class TestBboxFromCoordinates:
    def test_south_is_less_than_north(self):
        south, west, north, east = _bbox_from_coordinates(_make_coordinates())
        assert south < north

    def test_west_is_less_than_east(self):
        south, west, north, east = _bbox_from_coordinates(_make_coordinates())
        assert west < east

    def test_centre_is_inside_bbox(self):
        coords = _make_coordinates(lat=48.8566, lon=2.3522)
        south, west, north, east = _bbox_from_coordinates(coords)
        assert south < coords.latitude < north
        assert west < coords.longitude < east

    def test_larger_radius_produces_larger_bbox(self):
        small = _bbox_from_coordinates(_make_coordinates(radius=10))
        large = _bbox_from_coordinates(_make_coordinates(radius=50))
        s_small, w_small, n_small, e_small = small
        s_large, w_large, n_large, e_large = large
        assert (n_large - s_large) > (n_small - s_small)


# ---------------------------------------------------------------------------
# _parse_element
# ---------------------------------------------------------------------------


class TestParseElement:
    def test_parses_node_with_name(self):
        candidate = _parse_element(_node(osm_id=42, lat=48.9, lon=2.4, name="Carrière A"))
        assert candidate is not None
        assert candidate.name == "Carrière A"
        assert candidate.latitude == pytest.approx(48.9)
        assert candidate.longitude == pytest.approx(2.4)
        assert candidate.osm_id == "node/42"

    def test_parses_way_via_center(self):
        candidate = _parse_element(_way(osm_id=99, lat=48.85, lon=2.35, name="Carrière B"))
        assert candidate is not None
        assert candidate.latitude == pytest.approx(48.85)
        assert candidate.osm_id == "way/99"

    def test_falls_back_to_operator_when_no_name(self):
        element = {
            "type": "node",
            "id": 1,
            "lat": 48.0,
            "lon": 2.0,
            "tags": {"operator": "Lafarge"},
        }
        candidate = _parse_element(element)
        assert candidate is not None
        assert candidate.name == "Lafarge"

    def test_name_is_none_when_no_identifying_tag(self):
        element = {"type": "node", "id": 1, "lat": 48.0, "lon": 2.0, "tags": {}}
        candidate = _parse_element(element)
        assert candidate is not None
        assert candidate.name is None

    def test_extracts_website_url(self):
        element = {
            "type": "node",
            "id": 1,
            "lat": 48.0,
            "lon": 2.0,
            "tags": {"name": "X", "website": "https://example.com"},
        }
        candidate = _parse_element(element)
        assert candidate is not None
        assert "https://example.com" in candidate.source_urls

    def test_returns_none_when_no_coordinates(self):
        element = {"type": "way", "id": 1, "tags": {}}
        assert _parse_element(element) is None


# ---------------------------------------------------------------------------
# OverpassDiscoverer.discover
# ---------------------------------------------------------------------------


class TestOverpassDiscoverer:
    @pytest.fixture
    def discoverer(self) -> OverpassDiscoverer:
        return OverpassDiscoverer(timeout=5)

    async def test_returns_candidates_from_response(self, discoverer):
        elements = [_node(1, 48.9, 2.4, "Carrière A"), _way(2, 48.85, 2.35, "Carrière B")]
        with patch(f"{_MODULE}._fetch_sync", return_value=elements):
            results = await discoverer.discover(_make_coordinates())

        assert len(results) == 2
        assert results[0].name == "Carrière A"
        assert results[1].name == "Carrière B"

    async def test_returns_empty_list_when_all_instances_fail(self, discoverer):
        with patch(f"{_MODULE}._fetch_sync", side_effect=OSError("connection refused")):
            results = await discoverer.discover(_make_coordinates())

        assert results == []

    async def test_falls_back_to_second_instance_on_failure(self, discoverer):
        elements = [_node(1, 48.9, 2.4, "Carrière A")]
        call_count = 0

        def fake_fetch(url, body, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("first instance down")
            return elements

        with patch(f"{_MODULE}._fetch_sync", side_effect=fake_fetch):
            results = await discoverer.discover(_make_coordinates())

        assert len(results) == 1
        assert call_count == 2

    async def test_skips_elements_without_coordinates(self, discoverer):
        elements = [_node(1, 48.9, 2.4, "Valid"), {"type": "way", "id": 2, "tags": {}}]
        with patch(f"{_MODULE}._fetch_sync", return_value=elements):
            results = await discoverer.discover(_make_coordinates())

        assert len(results) == 1
        assert results[0].name == "Valid"

    async def test_returns_empty_list_when_no_elements(self, discoverer):
        with patch(f"{_MODULE}._fetch_sync", return_value=[]):
            results = await discoverer.discover(_make_coordinates())

        assert results == []
