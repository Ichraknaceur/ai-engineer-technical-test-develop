"""Overpass API adapter for quarry discovery.

Queries the OpenStreetMap Overpass API to find all features tagged
``landuse=quarry`` within a bounding box derived from the search coordinates.

Uses Python's built-in urllib (via asyncio.to_thread) rather than httpx
because several public Overpass instances reject httpx's default headers
while accepting standard urllib requests.
"""

import asyncio
import json
import logging
import math
import urllib.error
import urllib.parse
import urllib.request

from backend.config import settings
from backend.domain.entities.quarry import QuarryCandidate
from backend.domain.value_objects.coordinates import Coordinates

logger = logging.getLogger(__name__)

# Public fallback instances — tried in order if the primary is unavailable.
# Set OVERPASS_URL in .env to use a private instance and avoid rate limits.
_OVERPASS_FALLBACKS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]
_TIMEOUT_S = 45
_USER_AGENT = "QuarryBot/1.0 (research; contact@example.com)"


def _bbox_from_coordinates(coordinates: Coordinates) -> tuple[float, float, float, float]:
    """Compute a bounding box from a centre point and radius.

    Uses a simple equirectangular approximation — accurate for radii under ~500 km.

    Args:
        coordinates: Centre point and radius of the search area.

    Returns:
        (south, west, north, east) in decimal degrees.
    """
    lat = coordinates.latitude
    lon = coordinates.longitude
    r = coordinates.radius_km

    delta_lat = r / 111.0
    delta_lon = r / (111.0 * math.cos(math.radians(lat)))

    return (
        max(lat - delta_lat, -90.0),
        max(lon - delta_lon, -180.0),
        min(lat + delta_lat, 90.0),
        min(lon + delta_lon, 180.0),
    )


def _build_query(bbox: tuple[float, float, float, float]) -> str:
    """Build an Overpass QL query for quarries within a bounding box.

    Args:
        bbox: (south, west, north, east) bounding box.

    Returns:
        Overpass QL query string.
    """
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    return (
        f"[out:json][timeout:25];"
        f'(node["landuse"="quarry"]({bbox_str});'
        f'way["landuse"="quarry"]({bbox_str});'
        f'relation["landuse"="quarry"]({bbox_str}););'
        f"out center tags;"
    )


def _parse_element(element: dict) -> QuarryCandidate | None:
    """Parse a single Overpass API element into a QuarryCandidate.

    Handles nodes (lat/lon directly) and ways/relations (center object).

    Args:
        element: A single element dict from the Overpass JSON response.

    Returns:
        A QuarryCandidate, or None if coordinates cannot be determined.
    """
    tags = element.get("tags", {})
    element_type = element.get("type", "")
    osm_id = f"{element_type}/{element.get('id', '')}"

    if element_type == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        logger.debug("Skipping OSM element %s — no coordinates", osm_id)
        return None

    name = tags.get("name") or tags.get("operator") or tags.get("ref")

    source_urls: list[str] = []
    if website := tags.get("website") or tags.get("contact:website"):
        source_urls.append(website)

    return QuarryCandidate(
        name=name,
        latitude=float(lat),
        longitude=float(lon),
        osm_id=osm_id,
        source_urls=source_urls,
    )


def _fetch_sync(url: str, body: bytes, timeout: float) -> list[dict]:
    """Send a synchronous POST to an Overpass instance and return the elements list.

    Raises:
        urllib.error.URLError: On network or HTTP errors.
    """
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", _USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read()).get("elements", [])


class OverpassDiscoverer:
    """Discovers quarry candidates via the Overpass API (OpenStreetMap).

    Queries ``landuse=quarry`` features within the bounding box of the search
    area. Falls back across multiple public Overpass instances if the primary
    is unavailable.

    Args:
        timeout: HTTP request timeout in seconds (default 30).
    """

    def __init__(self, timeout: float = _TIMEOUT_S) -> None:
        self._timeout = timeout

    async def discover(self, coordinates: Coordinates) -> list[QuarryCandidate]:
        """Query Overpass for quarries within the search area.

        Args:
            coordinates: Centre point and radius of the search area.

        Returns:
            A list of QuarryCandidate objects, empty if none are found or
            if all Overpass instances are unreachable.
        """
        bbox = _bbox_from_coordinates(coordinates)
        query = _build_query(bbox)
        body = urllib.parse.urlencode({"data": query}).encode("utf-8")

        logger.info(
            "Querying Overpass — centre=(%.4f, %.4f) radius=%.1fkm",
            coordinates.latitude,
            coordinates.longitude,
            coordinates.radius_km,
        )

        instances = [settings.overpass_url] + _OVERPASS_FALLBACKS

        elements: list[dict] = []
        for url in instances:
            try:
                elements = await asyncio.to_thread(_fetch_sync, url, body, self._timeout)
                logger.debug("Overpass instance %s responded OK", url)
                break
            except Exception as exc:
                logger.warning("Overpass instance %s failed: %s — trying next", url, exc)
        else:
            logger.error("All Overpass instances failed — returning empty result")
            return []

        candidates = [_parse_element(el) for el in elements]
        results = [c for c in candidates if c is not None]
        logger.info("Overpass returned %d quarry candidate(s)", len(results))
        return results
