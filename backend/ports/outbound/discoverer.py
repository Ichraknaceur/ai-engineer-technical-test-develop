"""Outbound port for quarry discovery.

Any adapter that finds quarry candidates within a geographic area must satisfy
this protocol. Current implementation: OverpassDiscoverer (OpenStreetMap).
"""

from typing import Protocol

from backend.domain.entities.quarry import QuarryCandidate
from backend.domain.value_objects.coordinates import Coordinates


class IDiscoverer(Protocol):
    """Contract for discovering quarry candidates within a geographic area."""

    async def discover(self, coordinates: Coordinates) -> list[QuarryCandidate]:
        """Return quarry candidates found within the given coordinates and radius.

        Args:
            coordinates: Centre point and radius of the search area.

        Returns:
            A list of QuarryCandidate objects, possibly empty if none are found.
        """
        ...
